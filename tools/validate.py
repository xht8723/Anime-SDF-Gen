"""Run reproducible numerical, Blender, UI and package validation."""

from pathlib import Path
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.support import runtime_digest


def main(argv=None):
    version = tomllib.loads((ROOT / "anime_sdf_gen/blender_manifest.toml").read_text())["version"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", default=shutil.which("blender"))
    parser.add_argument("--fixture", type=Path, default=ROOT / "test_sdf.blend")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/validation" / version)
    parser.add_argument(
        "--suite",
        choices=("core", "guards", "lifecycle", "ui", "i18n", "export", "package", "all"),
        default="all",
    )
    args = parser.parse_args(argv)
    if args.suite != "core" and not args.blender:
        parser.error("Supply --blender with the Blender executable path.")
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "status": "RUNNING",
        "version": version,
        "suite": args.suite,
        "runtime_sha256": runtime_digest(),
        "checks": [],
    }
    manifest_path = out / f"run-{args.suite}.json"
    started = time.perf_counter()

    def command(name, cmd, reports=(), timeout=420):
        print("Running " + name, flush=True)
        record = {
            "runtime_sha256": runtime_digest(),
            "name": name,
            "command": list(map(str, cmd)),
            "reports": list(reports),
        }
        log = out / (name + ".log")
        info = None
        if os.name == "nt":
            info = subprocess.STARTUPINFO()
            info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            info.wShowWindow = 0
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=str(ROOT))
        before = time.perf_counter()
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run(
                list(map(str, cmd)),
                cwd=ROOT,
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                startupinfo=info,
            )
        record.update(
            exit_code=result.returncode, seconds=time.perf_counter() - before, log=str(log)
        )
        for report in reports:
            data = json.loads((out / report).read_text(encoding="utf-8"))
            if data.get("status") != "PASS":
                raise RuntimeError(name + " failed; see " + str(out / report))
        if result.returncode:
            raise RuntimeError(name + " failed; see " + str(log))
        if name == "numerical":
            match = re.search(r"Ran (\d+) tests", log.read_text(encoding="utf-8"))
            if not match or not log.read_text(encoding="utf-8").rstrip().endswith("OK"):
                raise RuntimeError("Numerical suite did not report success.")
            record["tests"] = int(match[1])
        if record["runtime_sha256"] != runtime_digest():
            raise RuntimeError(
                "Runtime changed during " + name + "; rerun against a stable revision."
            )
        manifest["checks"].append(record)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print("Passed " + name, flush=True)

    def blender(name, script, reports=(), gui=False, size=(2560, 1600), extra=(), scene=None):
        cmd = [args.blender]
        if not gui:
            cmd += ["--background"]
        cmd += ["--factory-startup", "--disable-autoexec", str(scene or args.fixture.resolve())]
        if gui:
            cmd += [
                "--enable-event-simulate",
                "--window-geometry",
                "60",
                "60",
                str(size[0]),
                str(size[1]),
            ]
        cmd += [
            "--python-exit-code",
            "1",
            "--python",
            str(ROOT / "tests" / script),
            "--",
            "--fixture",
            str(args.fixture.resolve()),
            "--output-dir",
            str(out),
        ]
        cmd += list(extra)
        command(name, cmd, reports)

    try:
        suite = args.suite
        if suite in ("core", "all"):
            command(
                "numerical",
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    "test_*.py",
                ],
            )
        if suite in ("guards", "all"):
            blender("guards", "blender_guards.py", ("guards/guards.json",))
        if suite in ("lifecycle", "all"):
            blender("sources", "blender_sources.py", ("sources/sources.json",))
            blender(
                "integration", "blender_integration.py", ("integration/blender_integration.json",)
            )
            blender(
                "saved-file",
                "blender_saved_check.py",
                ("integration/saved_file.json",),
                scene=out / "integration/save_while_editing.blend",
            )
            blender(
                "window-lifecycle",
                "blender_window_lifecycle.py",
                ("window-lifecycle/window-lifecycle.json",),
                gui=True,
            )
        if suite in ("ui", "all"):
            blender(
                "preview-reference",
                "blender_preview_reference.py",
                ("preview-reference/preview-reference.json",),
                gui=True,
            )
            for name, script, report in (
                ("curve-controls-2k", "blender_curve_controls.py", "curve-controls.json"),
                ("full-sweeps-2k", "blender_full_sweeps.py", "full-sweeps.json"),
                ("preview-interaction", "blender_preview_restore.py", "preview-interaction.json"),
                ("output-controls-2k", "blender_output_controls.py", "output-controls.json"),
            ):
                blender(name, script, (name + "/" + report,), gui=True)
            blender(
                "output-controls-4k",
                "blender_output_controls.py",
                ("output-controls-4k/output-controls.json",),
                gui=True,
                size=(3840, 2160),
                extra=("--case", "output-controls-4k", "--ui-scale", "1.5"),
            )
        if suite in ("i18n", "all"):
            command("i18n-catalog", [sys.executable, "-B", "tools/check_i18n.py"])
            blender("i18n-runtime", "blender_i18n_runtime.py", ("i18n-runtime/i18n-runtime.json",))
            for name, size, scale in (
                ("i18n-2k", (2560, 1600), "1.0"),
                ("i18n-4k", (3840, 2160), "1.5"),
            ):
                blender(
                    name,
                    "blender_i18n.py",
                    (name + "/i18n-ui.json",),
                    gui=True,
                    size=size,
                    extra=("--case", name, "--ui-scale", scale),
                )
        if suite in ("export", "all"):
            blender("precision", "blender_precision.py", ("precision/precision.json",))
            blender(
                "full-export",
                "blender_export_full.py",
                ("full-export/export_2048_32_8.json",),
                extra=("2048", "32", "8"),
            )
            command(
                "large-output",
                [sys.executable, "-B", "tests/benchmark_output.py", "--", "--output-dir", str(out)],
                ("large-output/large-output.json",),
            )
        if suite in ("package", "all"):
            command("package", [sys.executable, "-B", "tools/package.py"])
            archive = ROOT / "dist" / f"anime_sdf_gen-{version}.zip"
            command(
                "manifest",
                [
                    args.blender,
                    "--background",
                    "--factory-startup",
                    "--command",
                    "extension",
                    "validate",
                    archive,
                ],
            )
            blender(
                "archive",
                "blender_archive.py",
                ("archive/archive_import.json",),
                extra=("--archive", str(archive)),
            )
        manifest["status"] = "PASS"
    except Exception as exc:
        manifest.update(status="FAIL", error=str(exc))
        raise
    finally:
        manifest["elapsed_seconds"] = time.perf_counter() - started
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    main()
