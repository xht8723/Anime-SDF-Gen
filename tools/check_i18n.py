"""Audit translation coverage and named placeholders without importing Blender."""

import ast
from pathlib import Path
from string import Formatter
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from anime_sdf_gen.catalog import ENTRIES

UNTRANSLATED = {"", "Anime SDF Gen", "R", "G", "B", "X", "Y", "Z"}
CALLS = {
    "msg",
    "mark",
    "iface",
    "tip",
    "report",
    "UserError",
    "FileError",
    "AppError",
    "notify_error",
}


def _strings(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _strings(node.body) + _strings(node.orelse)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "mark":
        return _strings(node.args[0])
    return []


def source_messages(root=ROOT):
    found = {}

    def add(values, path, line):
        for text in values:
            if text not in UNTRANSLATED:
                found.setdefault(text, set()).add(f"{path}:{line}")

    for path in sorted((root / "anime_sdf_gen").rglob("*.py")):
        if path.name in ("catalog.py",):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        relative = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else getattr(node.func, "attr", "")
                )
                if name in CALLS and node.args:
                    add(_strings(node.args[0]), relative, node.lineno)
                if name == "report" and isinstance(node.func, ast.Attribute) and len(node.args) > 1:
                    add(_strings(node.args[1]), relative, node.lineno)
                if name == "wrapped" and len(node.args) > 1:
                    add(_strings(node.args[1]), relative, node.lineno)
                if name.endswith("Property"):
                    for kw in node.keywords:
                        if kw.arg in ("name", "description"):
                            add(_strings(kw.value), relative, node.lineno)
                        if kw.arg == "items":
                            for item in ast.walk(kw.value):
                                if isinstance(item, ast.Tuple) and len(item.elts) >= 3:
                                    for value in item.elts[1:3]:
                                        add(_strings(value), relative, item.lineno)
            if isinstance(node, ast.Assign):
                names = {target.id for target in node.targets if isinstance(target, ast.Name)}
                if names & {"bl_label", "bl_description", "SMOOTHING_HELP"}:
                    add(_strings(node.value), relative, node.lineno)
                if "DEPTH_ITEMS" in names:
                    for item in ast.walk(node.value):
                        if isinstance(item, ast.Tuple) and len(item.elts) >= 3:
                            add(_strings(item.elts[2]), relative, item.lineno)
    return found


def fields(template):
    return {
        (field, spec, conversion)
        for _, field, spec, conversion in Formatter().parse(template)
        if field is not None
    }


def audit():
    sources = source_messages()
    catalog = {}
    failures = []
    for source, target in ENTRIES:
        if source in catalog:
            failures.append(f"Duplicate translation: {source}")
        catalog[source] = target
        if not target.strip():
            failures.append(f"Empty translation: {source}")
        if fields(source) != fields(target):
            failures.append(f"Placeholder mismatch: {source}")
    for source in sorted(sources.keys() - catalog.keys()):
        failures.append(f"Missing translation: {source} ({', '.join(sorted(sources[source]))})")
    for source in sorted(catalog.keys() - sources.keys()):
        failures.append(f"Unused translation: {source}")
    return failures


def main():
    failures = audit()
    if failures:
        print("\n".join(failures))
        return 1
    print(f"Translation audit passed: {len(ENTRIES)} templates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
