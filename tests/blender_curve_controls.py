"""Real keymap/input regression with the restored shadow preview."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anime_sdf_gen import canvas
import bpy
import numpy as np
import anime_sdf_gen
from anime_sdf_gen import session, source
from anime_sdf_gen.core import model
from tests.fixture import fixture_face
from tests.ui_helpers import shot, center, event, click, wait_for
from tests.support import TestRun
from tests.ui_runner import run as run_ui

RUN = TestRun("curve-controls-2k").prepare(blender=True)
ROOT = Path(__file__).resolve().parents[1]
OUT = RUN.out
report = RUN.report
origin = RUN.origin
started = RUN.started
from tests.preview_checks import appearance
from anime_sdf_gen.core import editing


def pos(ci, pi):
    s = session.ACTIVE
    v = s.editor.views["AUTHOR"]
    r = v.region
    q = canvas.to_view(s, s.keyframe["contours"][ci]["points"][pi]["co"], v)
    return (r.x + q.x, r.y + q.y)


def key(kind, **kwargs):
    r = session.ACTIVE.editor.views["AUTHOR"].region
    xy = (r.x + r.width * 0.75, r.y + r.height * 0.6)
    event(kind, xy=xy, **kwargs)
    event(kind, "RELEASE", xy, **kwargs)
    yield 0.065


def number(value):
    digits = dict(
        zip(
            "0123456789",
            ("ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"),
        )
    )
    for ch in value:
        yield from key(digits.get(ch, {"-": "MINUS", ".": "PERIOD"}.get(ch)))


def box(points, subtract=False):
    xy = np.array([pos(*p) for p in points])
    low = xy.min(axis=0) - 12
    high = xy.max(axis=0) + 12
    yield from key("B")
    assert session.ACTIVE.curve_edit.state == "BOX_WAIT"
    event("MOUSEMOVE", "NOTHING", low)
    event("LEFTMOUSE", xy=low, shift=subtract)
    yield 0.07
    event("MOUSEMOVE", "NOTHING", high, shift=subtract)
    yield 0.12
    event("LEFTMOUSE", "RELEASE", high, shift=subtract)
    yield 0.15


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
    click("KEYFRAME:left_to_right:4")
    yield 0.2
    report["window_dimensions"] = [e.window.width, e.window.height]
    report["ui_scale_preference"] = bpy.context.preferences.view.ui_scale
    original = model.dumps(s.project)
    yield from box([(0, 3), (0, 4)])
    assert s.selected == {(0, 3), (0, 4)}, s.selected
    shot(OUT, "01-box-selected-boundary.png")
    initial = np.array([p["co"] for p in s.curve["points"]])
    yield from key("G")
    assert s.curve_edit.active and s.dragging
    yield from key("X")
    yield from number(".05")
    yield from key("RET")
    changed = np.array([p["co"] for p in s.curve["points"]])
    expected = initial.copy()
    expected[[3, 4], 0] += 0.05
    np.testing.assert_allclose(changed, expected)
    opposite = model.get_keyframe(s.project, model.RTL, 4)["contours"][0]
    np.testing.assert_allclose([p["co"][0] for p in opposite["points"]], 1 - changed[:, 0])
    yield from key("Z", ctrl=True)
    assert model.dumps(s.project) == original
    yield from key("Z", ctrl=True, shift=True)
    np.testing.assert_allclose([p["co"] for p in s.curve["points"]], changed)
    assert s.selected == {(0, 3), (0, 4)}
    saved = model.dumps(s.project)
    history = len(s.history.undo_stack)
    yield from key("G")
    yield from key("Y")
    yield from number("-.03")
    assert model.dumps(s.project) != saved
    yield from key("ESC")
    assert model.dumps(s.project) == saved and len(s.history.undo_stack) == history
    # Direct dragging retains the selected group and cancels as one edit.
    start = pos(0, 3)
    event("MOUSEMOVE", "NOTHING", start)
    event("LEFTMOUSE", xy=start)
    yield 0.08
    event("MOUSEMOVE", "NOTHING", (start[0] + 24, start[1] + 12))
    yield 0.15
    delta = np.array([p["co"] for p in s.curve["points"]]) - changed
    np.testing.assert_allclose(delta[3], delta[4])
    assert np.linalg.norm(delta[3]) > 0.001
    event("ESC")
    event("ESC", "RELEASE")
    yield 0.15
    assert model.dumps(s.project) == saved and s._modal_running
    # Shift-click toggles a point; native B + Shift subtracts the box contents.
    xy = pos(0, 3)
    event("LEFTMOUSE", xy=xy, shift=True)
    event("LEFTMOUSE", "RELEASE", xy, shift=True)
    yield 0.15
    assert s.selected == {(0, 4)}
    yield from box([(0, 3), (0, 4)])
    yield from box([(0, 4)], subtract=True)
    assert s.selected == {(0, 3)}, s.selected
    report["checks"].append(
        "box selection, Shift toggle/subtract, numeric constrained group move, linked mirroring, undo/redo and direct/keyboard cancellation"
    )

    # Modifier events use Blender's modal bindings, not only numeric math tests.
    for precise, expected in ((False, 0.04), (True, 0.004)):
        saved = model.dumps(s.project)
        initial = np.array(s.curve["points"][3]["co"])
        yield from key("G")
        yield from key("X")
        t = s.curve_edit.transform
        v = e.views["AUTHOR"]
        r = v.region
        target = (t.last - t.delta) / t.metric + np.array([0.043, 0])
        q = canvas.to_view(s, target, v)
        xy = (r.x + q.x, r.y + q.y)
        if precise:
            event("LEFT_SHIFT", xy=xy, shift=True)
        event("LEFT_CTRL", xy=xy, ctrl=True, shift=precise)
        yield 0.08
        event("MOUSEMOVE", "NOTHING", xy, ctrl=True, shift=precise)
        yield 0.15
        assert s.curve_edit.snap and s.curve_edit.precise == precise
        np.testing.assert_allclose(
            np.array(s.curve["points"][3]["co"]) - initial, [expected, 0], atol=1e-12
        )
        yield from key("ESC")
        event("LEFT_CTRL", "RELEASE")
        if precise:
            event("LEFT_SHIFT", "RELEASE")
        yield 0.1
        assert model.dumps(s.project) == saved
    report["checks"].append(
        "real Ctrl snapping and Shift precision events constrain group movement to coarse/fine increments"
    )

    click("KEYFRAME:left_to_right:6")
    yield 0.15
    click("TRIANGLE")
    yield 0.15
    assert s.selected == {(1, 0), (1, 1), (1, 2)}
    click("LIT")
    yield 0.15
    click("FREE")
    yield 0.15
    assert all(p["mode"] == "FREE" for p in s.curve["points"])
    old = np.array([p["co"] for p in s.curve["points"]])
    center = old.mean(axis=0)
    metric = np.array([1, s.project["alignment"]["height"] / s.project["alignment"]["width"]])
    yield from key("R")
    yield from number("90")
    yield from key("RET")
    rotated = np.array([p["co"] for p in s.curve["points"]])
    v = (old - center) * metric
    np.testing.assert_allclose(
        (rotated - center) * metric, np.column_stack([-v[:, 1], v[:, 0]]), atol=1e-12
    )
    yield from key("S")
    yield from number("1.2")
    yield from key("RET")
    scaled = np.array([p["co"] for p in s.curve["points"]])
    np.testing.assert_allclose(scaled - center, (rotated - center) * 1.2, atol=1e-12)
    yield from key("G")
    yield from key("X")
    yield from number("-.15")
    yield from key("RET")
    yield from wait_for(lambda: s.preview.thresholds is not None or bool(s.error))
    assert not s.error, s.error
    shot(OUT, "02-transformed-lit-triangle.png")
    yield from key("I", ctrl=True)
    assert s.selected == editing.available(s.keyframe) - {(1, 0), (1, 1), (1, 2)}
    yield from key("I", ctrl=True)
    assert s.selected == {(1, 0), (1, 1), (1, 2)}
    yield from key("A")
    assert len(s.selected) == 10, (s.selected, editing.available(s.keyframe), s.error)
    yield from key("A", alt=True)
    assert not s.selected
    yield from key("G")
    yield 0.1
    assert s.error and not s.curve_edit.active
    click("DISMISS_ERROR")
    yield 0.1
    click("LAYER:1")
    yield 0.1
    assert len(s.selected) == 3
    report["checks"].append(
        "new triangles and layers select whole curves; numeric aspect-correct rotation/scale preserve free handles; select-all/deselect and empty-selection errors stay usable"
    )

    # Use remapped bindings from Blender, including its modal axis binding.
    cfg = bpy.context.window_manager.keyconfigs.user
    move = next(
        i
        for i in cfg.keymaps["Curve"].keymap_items
        if i.idname == "transform.translate" and i.type == "G"
    )
    axis = next(
        i for i in cfg.keymaps["Transform Modal Map"].keymap_items if i.propvalue == "AXIS_X"
    )
    old_move, old_axis = move.type, axis.type
    try:
        move.type = "J"
        axis.type = "U"
        yield 0.2
        yield from key("G")
        assert not s.curve_edit.active
        saved = model.dumps(s.project)
        initial = np.array([p["co"] for p in s.curve["points"]])
        yield from key("J")
        assert s.curve_edit.active
        yield from key("U")
        yield from number(".02")
        yield from key("RET")
        np.testing.assert_allclose(
            np.array([p["co"] for p in s.curve["points"]]) - initial, [[0.02, 0]] * 3, atol=1e-12
        )
        yield from key("Z", ctrl=True)
        assert model.dumps(s.project) == saved
    finally:
        # Blender rebuilds keymap items after user overrides; reacquire them.
        cfg = bpy.context.window_manager.keyconfigs.user
        next(
            i
            for i in cfg.keymaps["Curve"].keymap_items
            if i.idname == "transform.translate" and i.type == "J"
        ).type = old_move
        next(
            i
            for i in cfg.keymaps["Transform Modal Map"].keymap_items
            if i.propvalue == "AXIS_X" and i.type == "U"
        ).type = old_axis
    yield 0.2
    report["checks"].append(
        "active Blender keymap overrides honored for transform shortcuts and modal axis constraints"
    )

    # The restored smooth lighting follows yaw without changing mask classes.
    yield from wait_for(lambda: s.preview.thresholds is not None or bool(s.error))
    assert not s.error, s.error
    s.orbit_preview = s.playing = False
    s.flat = False
    s.redraw()
    yield 0.15
    colored, lit, shadow = appearance()
    report["shaded_pixels"] = [int(lit.sum()), int(shadow.sum())]
    assert min(report["shaded_pixels"]) > 1000
    variations = []
    for angle in (0, 90, 180, 270):
        s.rotation = angle
        s.redraw()
        yield 0.1
        rgb, current_lit, current_shadow = appearance()
        np.testing.assert_array_equal(current_lit, lit)
        np.testing.assert_array_equal(current_shadow, shadow)
        variations.append(np.any(rgb != colored))
    assert any(variations)
    s.rotation = model.keyframe_rotation(s.direction, s.keyframe["progress"])
    s.sync_launcher()
    click("FLAT")
    yield 0.15
    _, mask_lit, mask_shadow = appearance(flat=True)
    np.testing.assert_array_equal(mask_lit, lit)
    np.testing.assert_array_equal(mask_shadow, shadow)
    report["black_white_pixels"] = [int(mask_lit.sum()), int(mask_shadow.sum())]
    shot(OUT, "03-black-white-mask.png")
    click("FLAT")
    yield 0.15
    shot(OUT, "04-shaded-preview.png")
    report["checks"].append(
        "smooth preview lighting follows yaw while mask classes stay fixed; shaded and flat classifications match"
    )

    # Saving a separate file cancels the unconfirmed transform before serialization.
    saved = model.dumps(s.project)
    selected = s.selected.copy()
    old_id = s.registry.id
    yield from key("G")
    yield from key("X")
    yield from number(".01")
    assert s.curve_edit.active and model.dumps(s.project) != saved
    with bpy.context.temp_override(window=e.window, area=e.native_area):
        bpy.ops.wm.save_as_mainfile(
            filepath=str(OUT / "save-during-transform.blend"), check_existing=False
        )
    yield from wait_for(
        lambda: session.ACTIVE is not None
        and session.ACTIVE.registry.id != old_id
        and session.ACTIVE.editor.ready
    )
    s = session.ACTIVE
    e = s.editor
    yield 0.25
    assert model.dumps(s.project) == saved and s.selected == selected and not s.curve_edit.active
    yield from wait_for(lambda: s.preview.thresholds is not None or bool(s.error))
    assert not s.error, s.error
    shot(OUT, "05-resumed-selection.png")
    yield from key("G")
    yield from key("Y")
    yield from number(".02")
    assert s.curve_edit.active
    session.end_session(True)
    yield 0.2
    assert before == {k: len(getattr(bpy.data, k)) for k in before}
    assert fixture_face(source).reference["fingerprint"] == face.reference["fingerprint"]
    report["checks"].append(
        "save cancels unconfirmed edits and restores selection; closing during a transform leaves no owned data and preserves the source"
    )
    anime_sdf_gen.unregister()


run_ui(workflow, RUN, "curve-controls.json", timeout=240)
