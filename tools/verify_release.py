"""Verify current archives and behavioral evidence without Git or old releases."""

from pathlib import Path
import argparse
import hashlib
import json
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.support import runtime_digest

REQUIRED = {
    "numerical",
    "guards",
    "sources",
    "integration",
    "saved-file",
    "window-lifecycle",
    "preview-reference",
    "curve-controls-2k",
    "full-sweeps-2k",
    "preview-interaction",
    "output-controls-2k",
    "output-controls-4k",
    "precision",
    "full-export",
    "large-output",
    "package",
    "manifest",
    "archive",
    "i18n-catalog",
    "i18n-runtime",
    "i18n-2k",
    "i18n-4k",
}


def main(argv=None):
    version = tomllib.loads((ROOT / "anime_sdf_gen/blender_manifest.toml").read_text())["version"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "build/validation" / version)
    parser.add_argument("--fixture", type=Path, default=ROOT / "test_sdf.blend")
    args = parser.parse_args(argv)
    out = args.evidence_dir.resolve()
    digest = runtime_digest()
    checks = {}
    for path in sorted(out.glob("run-*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        if run["status"] != "PASS" or run.get("runtime_sha256") != digest:
            continue
        for check in run["checks"]:
            if check.get("runtime_sha256") == digest:
                checks[check["name"]] = check
    assert (
        REQUIRED <= checks.keys()
    ), f"Missing current successful checks: {sorted(REQUIRED-checks.keys())}"
    for check in checks.values():
        for name in check["reports"]:
            report = json.loads((out / name).read_text(encoding="utf-8"))
            assert report["status"] == "PASS", name
    fixture = hashlib.sha256(args.fixture.read_bytes()).hexdigest()
    integration = json.loads((out / "integration/blender_integration.json").read_text())
    assert integration["fixture_sha256"] == fixture
    baseline_path = out / "baseline/baseline.json"
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text())
        for name, expected in baseline["preserved"].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    imported = Path(json.loads((out / "archive/archive_import.json").read_text())["source"])
    artifacts = []
    for suffix in ("", "-source"):
        path = ROOT / "dist" / f"anime_sdf_gen-{version}{suffix}.zip"
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        assert path.with_name(path.name + ".sha256").read_text().split()[0] == checksum
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            for name in archive.namelist():
                assert not name.startswith(("/", "\\")) and ".." not in Path(name).parts, name
                assert (
                    not name.endswith((".blend", ".blend1", ".pyc"))
                    and "__pycache__" not in name
                    and "README.draft" not in name
                ), name
                actual = archive.read(name)
                expected = (
                    ROOT / name
                    if suffix
                    else (
                        ROOT / Path(name).name
                        if name.startswith("docs/")
                        else ROOT / "anime_sdf_gen" / name
                    )
                )
                assert actual == expected.read_bytes(), name
                if not suffix:
                    assert actual == (imported / name).read_bytes(), name
            if not suffix:
                manifest = tomllib.loads(archive.read("blender_manifest.toml").decode())
                assert manifest["version"] == version and manifest["name"] == "Anime SDF Gen"
            else:
                assert "tests/data/preview-reference.npz" in archive.namelist()
                assert "tools/validate.py" in archive.namelist()
        artifacts.append({"file": str(path), "bytes": path.stat().st_size, "sha256": checksum})
    report = {
        "status": "PASS",
        "version": version,
        "schema": 4,
        "runtime_sha256": digest,
        "numerical_tests": checks["numerical"]["tests"],
        "checks": sorted(REQUIRED),
        "fixture_sha256": fixture,
        "artifacts": artifacts,
    }
    (out / "release.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
