"""Disposable integration checks for permissive source/fitting/save workflows."""
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace

import bpy
import numpy as np
from mathutils import Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import anime_sdf_gen
from anime_sdf_gen import commands, session, source
from anime_sdf_gen.core import files, model
from anime_sdf_gen.core.image_io import read_png
from tests.support import TestRun

RUN = TestRun("permissive").prepare(blender=True)
FRONT = Quaternion((1, 0, 0), math.pi / 2)


def new_session(obj, uv="", front_only=False, selected=None, stage="ORIENT"):
    face = source.extract(obj, uv, selected=selected or list(range(len(obj.data.polygons))),
                          front_only=front_only)
    p = model.new_project(face.reference, face.alignment, keyframes=3, resolution=512,
                          output=str(RUN.out / "face"))
    p["authoring"]["stage"] = stage
    return session.start(bpy.context, p, face, handlers=False)


def finish_export(s, name):
    s.project["settings"]["output"] = str(RUN.out / name)
    s.export.start()
    while s.busy:
        s.export.advance(0.05, finish=False)
    assert s.export.paths, s.error
    return read_png(s.export.paths[0])


try:
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
              for name in ("bugs.blend", "test_sdf.blend")}
    anime_sdf_gen.register()
    mesh = bpy.data.meshes.new("Permissive mesh")
    # A front triangle, a reverse-facing triangle, and a collapsed 3D triangle.
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 0, 1),
                      (1, 0, 0), (1, 0, 1), (2, 0, 0),
                      (0.5, 0, 0.5), (0.5, 0, 0.5), (0.5, 0, 0.5)],
                     [], [(0, 1, 2), (3, 4, 5), (6, 7, 8)])
    mesh.update()
    obj = bpy.data.objects.new("Permissive source", mesh)
    bpy.context.scene.collection.objects.link(obj)
    s = new_session(obj)
    assert s.face.uvs is None and not s.project["authoring"]["front_only"]
    s.set_front(FRONT)
    assert s.stage == "FIT" and len(s.face.triangles) == 3
    # A click missing the mesh projects onto the drawing plane.
    view = SimpleNamespace(ray=lambda _: (Vector((3, -3, 3)), Vector((0, 1, 0))))
    assert s.pick_landmark(view, (0, 0), "chin")
    assert "chin" not in s.project["authoring"]["anchors"]
    np.testing.assert_allclose(s.landmark_world("chin"), (3, 0, 3), atol=1e-6)
    before = deepcopy(s.project["landmarks"])
    parallel = SimpleNamespace(ray=lambda _: (Vector((3, -3, 3)), Vector((1, 0, 0))))
    assert not s.pick_landmark(parallel, (0, 0), "chin")
    assert s.project["landmarks"] == before
    s.project["landmarks"].update(nose=[0.5, 0.1], mouth=[0.5, 0.5], chin=[0.5, 0.9])
    s.project["authoring"]["anchors"].clear()
    s.fit()
    assert s.stage == "EDIT" and s.project["landmarks"]["chin"][1] == 0.9
    assert s.safe_write_draft()
    draft = session.draft_root() / (s.project["id"] + ".sdfproject.json")
    p = files.load_project(draft)
    session.end_session(False)
    s = session.start(bpy.context, p, source.from_reference(p["source"], p["alignment"]), handlers=False)
    assert s.face.uvs is None and not s.project["authoring"]["anchors"]
    s.confirm()
    s.export.start()
    while s.busy:
        s.export.advance(0.05, finish=False)
    assert s.error and not s.export.paths and not s.closed
    assert s.safe_write_draft()
    RUN.report["checks"].append("UV-free creation/fitting/draft/reopen; free markers and unusual ordering; missing-map export stays editable")

    uv = mesh.uv_layers.new(name="Bake")
    coords = np.array([[[0.02, 0.1], [0.3, 0.1], [0.02, 0.9]],
                       [[0.35, 0.1], [0.63, 0.1], [0.35, 0.9]],
                       [[0.68, 0.1], [0.96, 0.1], [0.68, 0.9]]])
    uv.data.foreach_set("uv", coords.ravel())
    mesh.update()
    s.set_bake_uv("Bake")
    assert s.face.uvs is not None
    # Use default valid artwork to test coverage independently of marker order.
    s.project["landmarks"] = deepcopy(model.DEFAULT_LANDMARKS)
    model.refit(s.project, 3)
    s.confirm()
    image = finish_export(s, "all-surfaces")
    for x in (30, 200, 365):
        assert image[100, x, 2] > 0, x
    saved = files.load_project(s.export.paths[-1])
    mesh.uv_layers.remove(uv)
    mesh.update()
    bpy.context.view_layer.update()
    assert source.from_reference(saved["source"], saved["alignment"]).uvs is None
    old = mesh.vertices[0].co.copy()
    mesh.vertices[0].co.x += 0.2
    mesh.update()
    bpy.context.view_layer.update()
    try:
        source.from_reference(saved["source"], saved["alignment"])
        raise AssertionError("Missing UV concealed changed geometry")
    except ValueError:
        pass
    mesh.vertices[0].co = old
    mesh.update()
    bpy.context.view_layer.update()
    session.end_session(True)
    # The same named map can be assigned after a missing-map reopen.
    s = session.start(bpy.context, saved, source.from_reference(saved["source"], saved["alignment"]), handlers=False)
    uv = mesh.uv_layers.new(name="Bake")
    uv.data.foreach_set("uv", np.zeros(len(uv.data) * 2))
    mesh.update()
    bpy.context.view_layer.update()
    s.set_bake_uv("Bake")
    image = finish_export(s, "collapsed")
    assert s.export.coverage_texels == 0 and not image[..., 2].any()
    assert s.safe_write_draft()
    session.end_session(True)
    RUN.report["checks"].append("later UV assignment; back/degenerate surface coverage; missing saved map reopens without masking geometry changes; collapsed map exports empty")

    s = new_session(obj, "Bake", True, selected=[1], stage="FIT")
    assert len(s.face.triangles) == 0
    assert not s.project["authoring"]["anchors"]
    s.fit()
    s.confirm()
    image = finish_export(s, "filtered-empty")
    assert not image[..., 2].any()
    session.end_session(True)
    RUN.report["checks"].append("fully filtered source remains editable, preserves plane markers and exports empty")

    s = new_session(obj, "Bake", stage="EDIT")
    s.keyframe["contours"].extend(model.triangle() for _ in range(127))
    commands.action(s, "TRIANGLE")
    assert len(s.keyframe["contours"]) == 129
    s.curve["points"] = [model.point(i / 256, 0.5, mode="CORNER") for i in range(256)]
    commands.action(s, "INSERT_POINT")
    assert len(s.curve["points"]) == 257 and s.safe_write_draft()
    commands.action(s, "UNDO")
    assert len(s.curve["points"]) == 256
    commands.action(s, "REDO")
    assert len(s.curve["points"]) == 257 and s.safe_write_draft()
    restored = files.load_project(session.draft_root() / (s.project["id"] + ".sdfproject.json"))
    assert restored == s.project
    session.end_session(True)
    RUN.report["checks"].append("operator additions beyond old caps, undo/redo and recovery roundtrip")

    edge = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 1]], float)
    a = source.fit_frame(edge, (0, -1, 0), (0, 0, 1))
    assert a["width"] > 0 and a["height"] > 0
    assert all(np.isfinite(v).all() for v in a.values())
    assert hashes == {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in hashes}
    RUN.report.update(status="PASS", model_hashes=hashes)
except Exception:
    RUN.report.update(status="FAIL", traceback=traceback.format_exc())
    traceback.print_exc()
finally:
    anime_sdf_gen.unregister()
    RUN.write("permissive.json")
if RUN.report["status"] != "PASS":
    raise RuntimeError(RUN.report["traceback"])
