"""Real popup input for optional filtering, free markers and UV-free authoring."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import time
import bpy
import gpu
import numpy as np
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import anime_sdf_gen
from anime_sdf_gen import drawing, session, source, ui
from anime_sdf_gen.core import model
from anime_sdf_gen.viewport import scale
from tests.support import TestRun
from tests.ui_helpers import center, click, dialog_confirm_position, event, redraw, shot, wait_for
from tests.ui_runner import run

RUN = TestRun("permissive-ui-2k").prepare(blender=True)
active = {}
original_invoke = ui.ANIME_SDF_GEN_OT_settings.invoke
original_execute = ui.ANIME_SDF_GEN_OT_settings.execute


def invoke(self, context, event):
    active[self.section] = self
    return original_invoke(self, context, event)


def execute(self, context):
    active.pop(self.section, None)
    return original_execute(self, context)


ui.ANIME_SDF_GEN_OT_settings.invoke = invoke
ui.ANIME_SDF_GEN_OT_settings.execute = execute


def mouse_click(xy):
    event("MOUSEMOVE", "NOTHING", xy)
    yield 0.1
    event("LEFTMOUSE", xy=xy)
    yield 0.1
    event("LEFTMOUSE", "RELEASE", xy)
    yield 0.2


def toggle_filter(value):
    redraw()
    xy = center("SOURCE")
    event("MOUSEMOVE", "NOTHING", xy)
    event("LEFTMOUSE", xy=xy)
    yield 0.5
    assert "SOURCE" not in active
    event("LEFTMOUSE", "RELEASE", xy)
    yield from wait_for(lambda: "SOURCE" in active)
    yield 0.4
    assert active["SOURCE"].front_only != value
    ok = dialog_confirm_position(RUN.out, "filter-" + str(value))
    RUN.report["toggle_position"] = dict(ok=ok.tolist(), scale=scale())
    checkbox = ok + np.array([-115, 30]) * scale()
    yield from mouse_click(checkbox)
    shot(RUN.out, "filter-after-click.png")
    assert active["SOURCE"].front_only == value
    yield from mouse_click(ok)
    assert "SOURCE" not in active
    assert session.ACTIVE.project["authoring"]["front_only"] == value


def gpu_pixels(s):
    offscreen = gpu.types.GPUOffScreen(256, 256)
    blend, depth, mask = gpu.state.blend_get(), gpu.state.depth_test_get(), gpu.state.depth_mask_get()
    try:
        with offscreen.bind():
            gpu.state.active_framebuffer_get().clear(color=(0.1, 0.1, 0.1, 1), depth=1)
            drawing.draw_face(s, SimpleNamespace(perspective_matrix=Matrix(
                ((1, 0, 0, -1), (0, 0, 2, -1), (0, -1, 0, 0), (0, 0, 0, 1)))))
        return np.asarray(offscreen.texture_color.read(), dtype=np.float32).reshape(256, 256, 4) / 255
    finally:
        offscreen.free()
        gpu.state.blend_set(blend)
        gpu.state.depth_test_set(depth)
        gpu.state.depth_mask_set(mask)


def workflow():
    anime_sdf_gen.register()
    mesh = bpy.data.meshes.new("Permissive UI mesh")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 0, 1),
                      (1, 0, 0), (1, 0, 1), (2, 0, 0)], [], [(0, 1, 2), (3, 4, 5)])
    obj = bpy.data.objects.new("Permissive UI source", mesh)
    bpy.context.scene.collection.objects.link(obj)
    mesh.update()
    face = source.extract(obj, "", selected=[0, 1])
    p = model.new_project(face.reference, face.alignment, keyframes=3, resolution=512,
                          output=str(RUN.out / ("empty-" + str(time.time_ns()))))
    p["authoring"]["stage"] = "ORIENT"
    s = session.start(bpy.context, p, face)
    yield from wait_for(lambda: s.editor.ready and s.editor.widgets)
    RUN.report["window_dimensions"] = [s.editor.window.width, s.editor.window.height]
    assert not s.project["authoring"]["front_only"] and s.face.uvs is None
    yield from toggle_filter(True)
    click("NEXT")
    yield 0.3
    assert s.stage == "FIT" and len(s.face.triangles) == 1
    click("BACK")
    yield 0.3
    yield from toggle_filter(False)
    click("NEXT")
    yield 0.3
    assert s.stage == "FIT" and len(s.face.triangles) == 2
    redraw()
    view = s.editor.views["AUTHOR"]
    xy = view.project(s.landmark_world("nose"))
    target = (view.region.x + 25 * scale(), view.region.y + 25 * scale())
    event("MOUSEMOVE", "NOTHING", xy)
    event("LEFTMOUSE", xy=xy)
    yield 0.15
    event("MOUSEMOVE", "NOTHING", target)
    yield 0.15
    event("LEFTMOUSE", "RELEASE", target)
    yield 0.2
    assert "nose" not in p["authoring"]["anchors"]
    assert s.safe_write_draft()
    shot(RUN.out, "01-free-marker.png")
    click("NEXT")
    yield 0.3
    assert s.stage == "EDIT" and not s.error
    # Endpoint pixels prove that the projected GPU preview also shades the
    # reversed triangle; a removed normal cutoff must not hide it.
    s.project["landmarks"] = deepcopy(model.DEFAULT_LANDMARKS)
    model.refit(s.project, 3)
    s.flat = True
    for index, expected in ((0, 1), (2, 0)):
        s.select_keyframe(model.LTR, index)
        s.preview.render()
        redraw()
        pixels = gpu_pixels(s)
        np.testing.assert_allclose(pixels[30, [20, 150], :3], expected, atol=1 / 255)
    shot(RUN.out, "02-full-shadow.png")
    RUN.report["checks"].append("native checkbox off/on/off; triangle inclusion; free-plane marker drag; front and reversed GPU endpoints")

    assert s.safe_write_draft()
    draft = session.draft_root() / (s.project["id"] + ".sdfproject.json")
    session.end_session(False)
    with bpy.context.temp_override(window=RUN.origin):
        assert bpy.ops.anime_sdf_gen.open_project(filepath=str(draft)) == {"FINISHED"}
    yield from wait_for(lambda: session.ACTIVE and session.ACTIVE.editor.ready)
    s = session.ACTIVE
    assert s.face.uvs is None and not s.project["authoring"]["front_only"]
    click("NEXT")
    yield 0.3
    assert s.stage == "CONFIRM"
    click("GENERATE")
    yield from wait_for(lambda: bool(s.error))
    assert not s.closed and not s.busy
    uv = mesh.uv_layers.new(name="Collapsed")
    uv.data.foreach_set("uv", np.zeros(len(uv.data) * 2))
    mesh.update()
    with s.origin.override():
        bpy.context.view_layer.update()
    s.set_bake_uv("Collapsed")
    click("GENERATE")
    yield from wait_for(lambda: s.closed)
    assert session.LAST_EXPORT and session.LAST_COVERAGE_TEXELS == 0
    RUN.report["checks"].append("UV-free popup draft/reopen; missing-map export retains editing; collapsed-map export closes successfully with zero-coverage notice")
    anime_sdf_gen.unregister()


run(workflow, RUN, "permissive-ui.json")
