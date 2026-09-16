"""Preview interaction and failure recovery; fixed pixels are checked separately."""

from pathlib import Path
import sys
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anime_sdf_gen.core.thresholds import decode
from anime_sdf_gen import canvas
import bpy
import numpy as np
import anime_sdf_gen
from anime_sdf_gen import session, source
from anime_sdf_gen.core import model
from tests.fixture import fixture_face
from tests.ui_helpers import redraw, shot, event, hover, click, metadata, await_tooltip, wait_for
from tests.support import TestRun
from tests.ui_runner import run as run_ui

RUN = TestRun("preview-interaction").prepare(blender=True)
ROOT = Path(__file__).resolve().parents[1]
OUT = RUN.out
report = RUN.report
origin = RUN.origin
started = RUN.started
from tests.preview_checks import appearance, pixels
from anime_sdf_gen.core import curves


def current_preview():
    s = session.ACTIVE
    s.preview.render()
    return pixels()


def compare_modes():
    s = session.ACTIVE
    s.flat = False
    current_preview()
    _, lit, shadow = appearance()
    s.flat = True
    current_preview()
    _, mask_lit, mask_shadow = appearance(flat=True)
    np.testing.assert_array_equal(lit, mask_lit)
    np.testing.assert_array_equal(shadow, mask_shadow)
    s.flat = False
    s.sync_launcher()
    s.redraw()


def workflow():
    anime_sdf_gen.register()
    before = {
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
    p = model.new_project(face.reference, face.alignment, resolution=512, output=str(OUT / "face"))
    s = session.start(bpy.context, p, face)
    yield from wait_for(lambda: s.editor.ready and s.editor.widgets)
    e = s.editor
    yield 0.3
    report["window_dimensions"] = [e.window.width, e.window.height]
    report["blender"] = bpy.app.version_string
    assert s.preview.rgba.shape == (512, 512, 4)
    assert np.isin(s.preview.rgba[..., :3], (0, 1)).all()
    for index in (0, 4, 8):
        click(f"KEYFRAME:left_to_right:{index}")
        yield 0.15
        compare_modes()
    shot(OUT, "01-restored-shadow.png")
    report["checks"].append(
        "projected 512-pixel masks and shaded/flat GPU frames exactly match frozen baseline at first, middle and last keyframes"
    )

    click("KEYFRAME:left_to_right:4")
    yield 0.15
    saved = deepcopy(s.project)
    original = s.preview.rgba.copy()
    view = e.views["AUTHOR"]
    r = view.region
    q = canvas.to_view(s, s.curve["points"][3]["co"], view)
    start = (r.x + q.x, r.y + q.y)
    event("MOUSEMOVE", "NOTHING", start)
    event("LEFTMOUSE", xy=start)
    yield 0.1
    revisions = []
    s.frame_times = []
    for i in range(20):
        event("MOUSEMOVE", "NOTHING", (start[0] + (i + 1) * 2, start[1]))
        yield 0.025
        revisions.append(s.preview.mask_revision)
        expected = curves.raster_keyframe(s.project, s.keyframe, s.direction, s.size, False)
        np.testing.assert_array_equal(s.preview.rgba[..., 0], expected)
    assert s.dragging and not np.array_equal(s.preview.rgba, original)
    assert len(set(revisions)) > 10
    event("ESC")
    event("ESC", "RELEASE")
    yield 0.15
    assert s.project == saved and s._modal_running
    np.testing.assert_array_equal(s.preview.rgba, original)
    current_preview()
    shot(OUT, "02-cancelled-drag.png")
    report["checks"].append(
        "mask follows the current curve during real dragging, without waiting for SDF compilation; Escape restores the project and mask immediately"
    )

    click("KEYFRAME:left_to_right:6")
    yield 0.1
    click("TRIANGLE")
    yield 0.1
    with bpy.context.temp_override(window=e.window, area=e.native_area):
        bpy.ops.anime_sdf_gen.transform(dx=-0.14)
    click("LIT")
    yield 0.15
    compare_modes()
    shot(OUT, "03-restored-lit-cutout.png")
    yield from wait_for(lambda: s.preview.thresholds is not None or bool(s.error), 60)
    assert not s.error, s.error
    for angle in (0, 45, 90, 135, 180, 225, 270, 315, 360):
        s.rotation = angle
        s.orbit_preview = True
        s.preview.render()
        yield 0.05
        direction, progress = model.rotation_sample(angle)
        np.testing.assert_array_equal(
            s.preview.rgba[..., 0],
            decode(s.preview.thresholds[..., 0 if direction == model.LTR else 1], progress),
        )
        compare_modes()
    report["checks"].append(
        "lit cutouts, both sweep directions and all sampled 360-degree angles match the shaded preview and mask decoding"
    )

    # Compilation errors must remain recoverable with the restored data path.
    saved = deepcopy(s.project)
    s.select_keyframe(model.LTR, 4)
    model.sweep(s.project, model.LTR)[4]["contours"] = deepcopy(
        model.sweep(s.project, model.LTR)[0]["contours"]
    )
    s.changed()
    yield from wait_for(lambda: bool(s.error), 60)
    assert s.conflict is not None and s.preview.rgba[..., 1].any()
    current_preview()
    redraw()
    assert e.warning_bounds.y == 0
    s.restore_project(saved)
    yield from wait_for(lambda: s.preview.thresholds is not None or bool(s.error), 60)
    assert not s.error and not s.preview.rgba[..., 1].any(), s.error
    report["checks"].append(
        "invalid keyframe ordering displays the original magenta conflict overlay; restoring artwork clears the error and recompiles"
    )

    projection = s.face.projected.copy()
    r = e.views["PREVIEW"].region
    xy = (r.x + r.width / 2, r.y + r.height / 2)
    event("NUMPAD_6", xy=xy)
    event("NUMPAD_6", "RELEASE", xy)
    yield 0.2
    compare_modes()
    np.testing.assert_array_equal(s.face.projected, projection)
    click("FRAME")
    yield 0.15
    click("NEXT")
    yield 0.15
    assert s.stage == "CONFIRM" and s.playing
    angle = s.rotation
    revision = s.preview.mask_revision
    yield 0.5
    assert s.rotation > angle and s.preview.mask_revision > revision
    click("PLAY")
    yield 0.1
    compare_modes()
    shot(OUT, "04-restored-confirm.png")
    metadata()
    hover("FLAT")
    yield from await_tooltip("FLAT")
    shot(OUT, "05-preview-tooltip.png")
    report["checks"].append(
        "native orbit preserves fixed projection; Confirm starts a 360-degree sweep with the restored shaded/flat toggle"
    )
    session.end_session(True)
    yield 0.2
    assert (
        s.preview._face_shader is None
        and s.preview._face_batch is None
        and s.preview._mask_texture is None
    )
    assert s.preview.job is None and not s.preview.field_cache and not s.preview.mask_cache
    assert before == {k: len(getattr(bpy.data, k)) for k in before}
    assert fixture_face(source).reference["fingerprint"] == face.reference["fingerprint"]
    report["checks"].append(
        "closing releases all preview resources and preserves the original model and datablock counts"
    )
    anime_sdf_gen.unregister()


run_ui(workflow, RUN, "preview-interaction.json", timeout=240)
