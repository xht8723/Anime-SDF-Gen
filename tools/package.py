"""Deterministic extension and source bundles; importing does not write files."""

from pathlib import Path
import hashlib
import json
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = (
    "README.md",
    "usage.md",
    "output-format.md",
    "validation.md",
    "architecture.md",
    "cleanup-audit.md",
    "usage.zh-Hans.md",
    "i18n-development.md",
)
TOOLS = ("package.py", "validate.py", "verify_release.py", "check_i18n.py")
EXCLUDED_TESTS = {"blender_character_toon.py"}


def write_archive(target, entries):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, path in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 14, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_name(target.name + ".sha256").write_text(
        digest + "  " + target.name + "\n", encoding="ascii"
    )
    return {"file": str(target), "bytes": target.stat().st_size, "sha256": digest}


def main():
    package = ROOT / "anime_sdf_gen"
    version = tomllib.loads((package / "blender_manifest.toml").read_text())["version"]
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    package_files = [
        p
        for p in package.rglob("*")
        if p.is_file()
        and (p.suffix == ".py" or p.name in ("blender_manifest.toml", "LICENSE", "NOTICE"))
    ]
    extension = [(p.relative_to(package).as_posix(), p) for p in package_files]
    extension.extend(
        ("docs/" + name, ROOT / name)
        for name in ("usage.md", "usage.zh-Hans.md", "output-format.md")
    )
    tests = [p for p in (ROOT / "tests").glob("*.py") if p.name not in EXCLUDED_TESTS]
    tests.extend((ROOT / "tests/data").glob("*.npz"))
    source = (
        package_files
        + tests
        + [ROOT / "tools" / name for name in TOOLS]
        + [ROOT / name for name in DOCS]
    )
    results = [
        write_archive(out / f"anime_sdf_gen-{version}.zip", extension),
        write_archive(
            out / f"anime_sdf_gen-{version}-source.zip",
            [(p.relative_to(ROOT).as_posix(), p) for p in source],
        ),
    ]
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    main()
