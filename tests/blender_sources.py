"""Generic source capture checks, independent of the character fixture."""

from pathlib import Path
import json
import sys
import traceback
import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from anime_sdf_gen import source
from tests.support import TestRun

RUN = TestRun("sources").prepare(blender=True)
OUT = RUN.out
DRAFTS = OUT / "drafts"
report = RUN.report


def failure(call, fragment):
    try:
        call()
    except ValueError as exc:
        assert fragment.lower() in str(exc).lower(), str(exc)
    else:
        raise AssertionError("Expected " + fragment)


try:
    mesh = bpy.data.meshes.new("Arbitrary topology")
    verts = [(x, 0, z) for z in range(3) for x in range(3)]
    faces = [
        (x + 3 * z, x + 1 + 3 * z, x + 4 + 3 * z, x + 3 + 3 * z) for z in range(2) for x in range(2)
    ]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    uv = mesh.uv_layers.new(name="Character Atlas")
    for p in mesh.polygons:
        for li in p.loop_indices:
            co = mesh.vertices[mesh.loops[li].vertex_index].co
            uv.data[li].uv = (co.x / 2, co.z / 2)
    obj = bpy.data.objects.new("Any Mesh Name", mesh)
    bpy.context.scene.collection.objects.link(obj)
    for o in bpy.context.view_layer.objects:
        o.select_set(o == obj)
    bpy.context.view_layer.objects.active = obj
    failure(lambda: source.capture(obj), "Edit Mode")
    group = obj.vertex_groups.new(name="Artist Face Region")
    group.add(list(faces[0]), 1, "REPLACE")
    group.add([2, 5], 0, "REPLACE")
    f = source.capture(obj, "VERTEX_GROUP", group.name)
    assert f.reference["faces"] == [0] and f.reference["uv_map"] == "Character Atlas"
    assert len(f.materials) == 0
    report["checks"].append(
        "arbitrary mesh/group/UV names; all vertices need strictly positive group weights"
    )
    group.add([2, 5], 0.0001, "REPLACE")
    failure(lambda: source.from_reference(f.reference, f.alignment), "membership changed")
    failure(lambda: source.capture(obj, "VERTEX_GROUP", "Missing Group"), "missing")
    empty = obj.vertex_groups.new(name="Empty Group")
    failure(lambda: source.capture(obj, "VERTEX_GROUP", empty.name), "empty")
    report["checks"].append("changed, missing, and empty vertex groups rejected")
    for mode in ((True, False, False), (False, True, False), (False, False, True)):
        bpy.context.tool_settings.mesh_select_mode = mode
        bpy.ops.object.mode_set(mode="EDIT")
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        for face in bm.faces:
            face.select_set(False)
        for edge in bm.edges:
            edge.select_set(False)
        for vertex in bm.verts:
            vertex.select_set(False)
        if mode[0]:
            for vertex in bm.faces[0].verts:
                vertex.select_set(True)
        elif mode[1]:
            for edge in bm.faces[0].edges:
                edge.select_set(True)
        else:
            bm.faces[0].select_set(True)
        bm.select_flush_mode()
        bmesh.update_edit_mesh(mesh)
        f = source.capture(obj)
        assert obj.mode == "EDIT" and f.reference["faces"] == [0], (mode, f.reference)
        # Reopening uses captured IDs, not a later live selection.
        bm = bmesh.from_edit_mesh(mesh)
        for face in bm.faces:
            face.select_set(False)
        for edge in bm.edges:
            edge.select_set(False)
        for vertex in bm.verts:
            vertex.select_set(False)
        bmesh.update_edit_mesh(mesh)
        again = source.from_reference(f.reference, f.alignment)
        assert again.reference["faces"] == [0] and obj.mode == "EDIT"
        failure(lambda: source.capture(obj), "empty")
        bpy.ops.object.mode_set(mode="OBJECT")
    report["checks"].append(
        "vertex/edge/face selections, Edit Mode restoration, and immutable captured polygon IDs"
    )
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.faces[0].select_set(True)
    bm.faces[0].hide_set(True)
    bmesh.update_edit_mesh(mesh)
    failure(lambda: source.capture(obj), "empty")
    bpy.ops.object.mode_set(mode="OBJECT")
    report["checks"].append("hidden selected geometry excluded")
    mesh2 = mesh.copy()
    obj2 = bpy.data.objects.new("Another Mesh", mesh2)
    bpy.context.scene.collection.objects.link(obj2)
    obj2.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    for target in (obj, obj2):
        bm = bmesh.from_edit_mesh(target.data)
        for face in bm.faces:
            face.hide_set(False)
            face.select_set(True)
        bmesh.update_edit_mesh(target.data)
    f = source.capture(obj)
    assert f.reference["object"] == obj.name and len(f.reference["faces"]) == 4
    assert obj.mode == obj2.mode == "EDIT"
    assert obj.select_get() and obj2.select_get() and bpy.context.view_layer.objects.active == obj
    report["checks"].append(
        "multi-object Edit Mode captures only active mesh and preserves both edit states"
    )
    bpy.ops.object.mode_set(mode="OBJECT")
    uv_name = mesh.uv_layers.active.name
    mesh.uv_layers.remove(mesh.uv_layers.active)
    failure(lambda: source.capture(obj, "VERTEX_GROUP", group.name), "UV map")
    report["checks"].append("missing UVs rejected")
    report["status"] = "PASS"
except Exception:
    report["status"] = "FAIL"
    report["traceback"] = traceback.format_exc()
    traceback.print_exc()
(OUT / "sources.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
if report["status"] != "PASS":
    sys.exit(1)
