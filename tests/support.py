"""Shared validation configuration. Importing this module has no side effects."""

from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def version():
    return tomllib.loads((ROOT / "anime_sdf_gen/blender_manifest.toml").read_text())["version"]


def runtime_digest():
    digest = hashlib.sha256()
    for path in sorted((ROOT / "anime_sdf_gen").rglob("*")):
        if path.is_file() and (path.suffix == ".py" or path.name == "blender_manifest.toml"):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


class TestRun:
    __test__ = False

    def __init__(self, name, argv=None):
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            "--output-dir", type=Path, default=ROOT / "build/validation" / version()
        )
        parser.add_argument("--fixture", type=Path, default=ROOT / "test_sdf.blend")
        parser.add_argument("--case", default=None)
        parser.add_argument("--ui-scale", type=float, default=1.0)
        parser.add_argument(
            "--archive", type=Path, default=ROOT / "dist" / f"anime_sdf_gen-{version()}.zip"
        )
        if argv is None:
            argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
        self.args, self.extra = parser.parse_known_args(argv)
        self.root = self.args.output_dir.resolve()
        self.out = self.root / (self.args.case or name)
        self.fixture = self.args.fixture.resolve()
        self.started = time.perf_counter()
        self.report = {"status": "RUNNING", "version": version(), "checks": []}
        self.origin = None

    def prepare(self, blender=False):
        self.out.mkdir(parents=True, exist_ok=True)
        if blender:
            import bpy
            from anime_sdf_gen import session

            self.origin = bpy.context.window
            self.report["blender"] = bpy.app.version_string
            bpy.context.preferences.use_preferences_save = False
            bpy.context.preferences.view.ui_scale = self.args.ui_scale
            for name in ("drafts", "temp"):
                (self.out / name).mkdir(exist_ok=True)
            session.draft_root = lambda: self.out / "drafts"
            bpy.context.preferences.filepaths.temporary_directory = str(self.out / "temp")
        return self

    def write(self, name, report=None):
        data = self.report if report is None else report
        data["version"] = version()
        data["elapsed_seconds"] = time.perf_counter() - self.started
        (self.out / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def fixture_hash(self):
        return hashlib.sha256(self.fixture.read_bytes()).hexdigest()
