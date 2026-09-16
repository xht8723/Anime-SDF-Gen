"""Fixed-camera GPU and numerical references, independent of old releases."""

from pathlib import Path
from types import SimpleNamespace
import json
import sys
import time
import traceback
import bpy
import gpu
import numpy as np
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from anime_sdf_gen.core import editing
import anime_sdf_gen
from anime_sdf_gen import session, source, drawing
from anime_sdf_gen.core import model, compile
from tests.fixture import fixture_face
from tests.support import TestRun

RUN = TestRun("preview-reference").prepare(blender=True)
OUT = RUN.out
DRAFTS = OUT / "drafts"
REFERENCE = ROOT / "tests/data/preview-reference.npz"
CAPTURE = "--capture" in RUN.extra
origin = RUN.origin
started = RUN.started


def render(s, matrix):
    buffer = gpu.types.GPUOffScreen(256, 256)
    blend = gpu.state.blend_get()
    depth = gpu.state.depth_test_get()
    mask = gpu.state.depth_mask_get()
    try:
        with buffer.bind():
            gpu.state.active_framebuffer_get().clear(color=(0.055, 0.065, 0.083, 1), depth=1.0)
            drawing.draw_face(s, SimpleNamespace(perspective_matrix=Matrix(matrix)))
        a = np.asarray(buffer.texture_color.read(), dtype=np.float32).reshape(256, 256, 4)
        return a.copy()
    finally:
        buffer.free()
        gpu.state.blend_set(blend)
        gpu.state.depth_test_set(depth)
        gpu.state.depth_mask_set(mask)


def workflow():
    anime_sdf_gen.register()
    counts = {
        k: len(getattr(bpy.data, k))
        for k in (
            "objects",
            "meshes",
            "materials",
            "images",
            "scenes",
            "worlds",
            "screens",
            "workspaces",
        )
    }
    face = fixture_face(source)
    p = model.new_project(
        face.reference, face.alignment, resolution=512, output=str(OUT / "reference")
    )
    s = session.start(bpy.context, p, face)
    deadline = time.perf_counter() + 30
    while not s.editor.ready or not s.editor.widgets:
        assert time.perf_counter() < deadline
        yield 0.1
    e = s.editor
    yield 0.5

    def redraw():
        from anime_sdf_gen.viewport import window_region

        with bpy.context.temp_override(
            window=e.window, area=e.native_area, region=window_region(e.native_area)
        ):
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

    redraw()
    old = np.load(REFERENCE) if not CAPTURE else None
    matrix = np.asarray(e.views["PREVIEW"].perspective_matrix) if CAPTURE else old["matrix"]
    data = {"matrix": matrix, "fingerprint": np.array(face.reference["fingerprint"])}
    samples = []
    for i, index in enumerate((0, 4, 8)):
        s.select_keyframe(model.LTR, index)
        for flat in (False, True):
            s.flat = flat
            s.preview.render()
            redraw()
            name = f"key_{index}_{int(flat)}"
            data[name + "_mask"] = s.preview.rgba.copy()
            data[name + "_gpu"] = render(s, matrix)
            samples.append(s.preview.last_render_ms)
    s.select_keyframe(model.LTR, 6)
    c = model.triangle()
    editing.transform_contour(c, dx=-0.14)
    c["operation"] = "REMOVE"
    s.keyframe["contours"].append(c)
    s.changed()
    fields = compile.compile_project(s.project, s.size, s.preview.domain)
    data["thresholds"] = fields
    s.preview.thresholds = fields
    for angle in (0, 45, 90, 135, 180, 225, 270, 315, 360):
        s.rotation = angle
        s.orbit_preview = True
        for flat in (False, True):
            s.flat = flat
            s.preview.render()
            redraw()
            name = f"orbit_{angle}_{int(flat)}"
            data[name + "_mask"] = s.preview.rgba.copy()
            data[name + "_gpu"] = render(s, matrix)
            samples.append(s.preview.last_render_ms)
    if CAPTURE:
        REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(REFERENCE, **data)
    else:
        assert set(old.files) == set(data)
        for key, value in data.items():
            np.testing.assert_array_equal(value, old[key], err_msg=key)
        old.close()
    session.end_session(True)
    assert counts == {k: len(getattr(bpy.data, k)) for k in counts}
    anime_sdf_gen.unregister()
    report = {
        "status": "PASS",
        "capture": CAPTURE,
        "samples": len(samples),
        "reference": str(REFERENCE),
        "render_mask_median_ms": float(np.median(samples)),
        "render_mask_p95_ms": float(np.percentile(samples, 95)),
        "blender": bpy.app.version_string,
        "elapsed": time.perf_counter() - started,
    }
    (OUT / "preview-reference.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


steps = workflow()


def tick():
    try:
        return next(steps)
    except StopIteration:
        pass
    except Exception:
        traceback.print_exc()
        (OUT / "preview-reference.json").write_text(
            json.dumps({"status": "FAIL", "traceback": traceback.format_exc()})
        )
        if session.ACTIVE:
            session.end_session(False)
    with bpy.context.temp_override(window=origin):
        bpy.ops.wm.quit_blender()


bpy.app.timers.register(tick, first_interval=1)
