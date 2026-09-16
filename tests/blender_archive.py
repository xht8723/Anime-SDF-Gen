"""Import the actual ZIP under a Blender extension namespace in an isolated process."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import importlib.util
import json
import types
import time
import zipfile
import bpy
from math import pi
from mathutils import Quaternion

ROOT = Path(__file__).resolve().parents[1]
from tests.support import TestRun, version
import uuid

RUN = TestRun("archive").prepare(blender=True)
OUT = RUN.out
DEST = OUT / ("installed-" + uuid.uuid4().hex) / "anime_sdf_gen"
DEST.mkdir(parents=True, exist_ok=True)
ZIP = RUN.args.archive
with zipfile.ZipFile(ZIP) as archive:
    assert all(
        not n.startswith(("/", "\\")) and ".." not in Path(n).parts for n in archive.namelist()
    )
    archive.extractall(DEST)
for name in ("bl_ext", "bl_ext.sdf_qa"):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module
name = "bl_ext.sdf_qa.anime_sdf_gen"
spec = importlib.util.spec_from_file_location(
    name, DEST / "__init__.py", submodule_search_locations=[str(DEST)]
)
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
assert importlib.import_module(name + ".curve_input").CurveInput
module.register()
translation = importlib.import_module(name + ".i18n")
view = bpy.context.preferences.view
original_language = (view.language, view.use_translate_interface)
try:
    view.language = "zh_HANS"
    view.use_translate_interface = True
    assert translation.iface("Next Step  →") == "下一步  →"
    assert translation._registered
finally:
    view.language, view.use_translate_interface = original_language
before = {
    k: len(getattr(bpy.data, k))
    for k in ("objects", "meshes", "materials", "images", "scenes", "worlds")
}
session = sys.modules[name + ".session"]
model = sys.modules[name + ".core.model"]
drafts = OUT / "archive-drafts"
drafts.mkdir(exist_ok=True)
session.draft_root = lambda: drafts
p = bpy.context.window_manager.anime_sdf_gen
obj = bpy.data.objects["body"]
for o in bpy.context.view_layer.objects:
    o.select_set(o == obj)
bpy.context.view_layer.objects.active = obj
slots = {i for i, m in enumerate(obj.data.materials) if m and m.name == "head"}
for polygon in obj.data.polygons:
    polygon.select = polygon.material_index in slots
bpy.context.tool_settings.mesh_select_mode = (False, False, True)
bpy.ops.object.mode_set(mode="EDIT")
p.source_method = "SELECTED"
assert bpy.ops.anime_sdf_gen.create() == {"FINISHED"}
assert session.ACTIVE and type(session.ACTIVE).__module__.startswith("bl_ext.sdf_qa.")
assert session.ACTIVE.stage == "ORIENT"
assert session.ACTIVE.project["format_version"] == 4
assert (
    session.ACTIVE.project["settings"]["bit_depth"] == 16
    and session.ACTIVE.project["settings"]["smoothing"] == 0
)
assert module.bl_info["name"] == "Anime SDF Gen" and module.bl_info["author"] == "xht8723"
assert module.bl_info["version"] == tuple(map(int, version().split(".")))
assert p.bl_rna.properties["keyframes"].name == "Shadow keyframes"
session.ACTIVE.set_front(Quaternion((1, 0, 0), pi / 2))
assert session.ACTIVE.stage == "FIT" and len(session.ACTIVE.project["authoring"]["anchors"]) == 3
session.ACTIVE.fit()
assert session.ACTIVE.stage == "EDIT" and session.ACTIVE.key_index == 0
assert len({p["co"][0] for p in session.ACTIVE.curve["points"]}) == 1
bpy.ops.anime_sdf_gen.keyframe(direction=model.LTR, index=6)
bpy.ops.anime_sdf_gen.action(action="TRIANGLE")
assert session.ACTIVE.curve["name"] == "Triangle"
assert session.ACTIVE.selected == {(1, 0), (1, 1), (1, 2)}
assert all(p["mode"] == "AUTO" for p in session.ACTIVE.curve["points"])
importlib.import_module(name + ".commands").operation(session.ACTIVE, "REMOVE")
bpy.ops.anime_sdf_gen.transform(dx=-0.14)
assert importlib.import_module(name + ".core.compile").compile_project(
    session.ACTIVE.project, 64
).shape == (64, 64, 2)
active = session.ACTIVE
deadline = time.perf_counter() + 45
while active.preview.thresholds is None:
    active.tick()
    assert not active.error, active.error
    assert time.perf_counter() < deadline, "Packaged sweep interpolation timed out"
assert active.preview.rgba.shape == (512, 512, 4)
assert active.preview.thresholds.shape == (512, 512, 2)
assert active.preview.rgba.shape == (512, 512, 4)
session.ACTIVE.confirm()
assert session.ACTIVE.stage == "CONFIRM" and session.ACTIVE.playing and session.ACTIVE.rotation == 0
assert bpy.ops.anime_sdf_gen.packing(map_name="character_left", route="B") == {"FINISHED"}
assert bpy.ops.anime_sdf_gen.packing(map_name="character_right", route="SEPARATE") == {"FINISHED"}
assert session.ACTIVE.project["settings"]["packing"] == dict(
    character_left="B", character_right="SEPARATE", face_coverage="R"
)
assert session.ACTIVE.playing
active.project["settings"]["bit_depth"] = 32
active.preview.set_smoothing(2)
assert (
    active.project["settings"]["bit_depth"] == 32 and active.project["settings"]["smoothing"] == 2
)
deadline = time.perf_counter() + 45
while active.preview.filtered_key != (id(active.preview.raw_thresholds), 2, True):
    active.tick()
    assert not active.error, active.error
    assert time.perf_counter() < deadline
assert active.preview.thresholds is not active.preview.raw_thresholds
assert importlib.import_module(name + ".core.files").output_extension(active.project) == ".exr"
session.end_session(True)
assert (
    active.preview.job is None and not active.preview.field_cache and not active.preview.mask_cache
)
module.unregister()
assert {k: len(getattr(bpy.data, k)) for k in before} == before
report = {
    "status": "PASS",
    "module": name,
    "source": str(DEST),
    "zip_bytes": ZIP.stat().st_size,
    "simplified_chinese_in_extension_namespace": True,
}
(OUT / "archive_import.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
