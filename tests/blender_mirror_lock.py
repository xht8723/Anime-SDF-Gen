"""Locked mirrored row, one-way synchronization, history and persistence in the real popup."""

from copy import deepcopy
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import anime_sdf_gen
from anime_sdf_gen import commands, session, source, ui
from anime_sdf_gen.core import files, model
from anime_sdf_gen.core.thresholds import decode
from anime_sdf_gen.ui_guard import bind
from tests.fixture import fixture_face
from tests.support import TestRun
from tests.ui_helpers import (
    await_tooltip,
    center,
    click,
    event,
    hover,
    metadata,
    redraw,
    shot,
    wait_for,
    widget,
)
from tests.ui_runner import run

RUN = TestRun("mirror-lock-2k").prepare(blender=True)


def action(name, **kwargs):
    e = session.ACTIVE.editor
    with bpy.context.temp_override(window=e.window, area=e.native_area):
        return getattr(bpy.ops.anime_sdf_gen, name)(**kwargs)


def mirrored(s):
    left = model.sweep(s.project, model.LTR)
    right = model.sweep(s.project, model.RTL)
    assert right == [model.mirror_keyframe(k) for k in left]
    redraw()
    for direction in model.SWEEP_LABELS:
        buttons = [w for w in s.editor.widgets if w["key"].startswith("KEYFRAME:" + direction)]
        assert len(buttons) == len(left)
        assert all(w["enabled"] == (direction == model.LTR) for w in buttons)
    metadata()


def workflow():
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("bugs.blend", "test_sdf.blend")
    }
    anime_sdf_gen.register()
    face = fixture_face(source)
    project = model.new_project(
        face.reference,
        face.alignment,
        keyframes=5,
        resolution=512,
        output=str(RUN.out / "mirrored"),
    )
    s = session.start(bpy.context, project, face)
    yield from wait_for(lambda: s.editor.ready and s.editor.widgets)
    RUN.report["window_dimensions"] = [s.editor.window.width, s.editor.window.height]
    mirrored(s)
    before = s.checkpoint()
    locked = "KEYFRAME:right_to_left:2"
    xy = center(locked)
    event("MOUSEMOVE", "NOTHING", xy)
    event("LEFTMOUSE", xy=xy)
    event("LEFTMOUSE", "RELEASE", xy)
    yield 0.15
    assert s.checkpoint() == before
    assert action("keyframe", direction=model.RTL, index=2) == {"CANCELLED"}
    assert s.checkpoint() == before
    s.error = ""
    hover(locked)
    yield from await_tooltip(locked)
    assert widget(locked)["tooltip"]["reason"] == (
        "Mirrored from Left → Right. Turn off Mirror Full Sweep to edit."
    )
    shot(RUN.out, "01-locked-row.png")
    view = bpy.context.preferences.view
    view.language = "zh_HANS"
    view.use_translate_interface = view.use_translate_tooltips = True
    s.refresh_language()
    hover(locked)
    yield from await_tooltip(locked)
    assert "关闭“镜像同步关键帧”" in widget(locked)["tooltip"]["reason"]
    shot(RUN.out, "02-locked-row-zh.png")
    view.language = "en_US"
    s.refresh_language()

    # Direct editing entry points also reject a stale right-side target.
    s.direction, s.key_index = model.RTL, 2
    before = s.checkpoint()
    for name, kwargs in (
        ("action", {"action": "ADD_KEYFRAME"}),
        ("action", {"action": "REMOVE_KEYFRAME"}),
        ("action", {"action": "TRIANGLE"}),
        ("layer", {"index": 0}),
        ("transform", {"dx": 0.1}),
        ("settings", {"section": "POINT", "point_xy": (0.1, 0.2)}),
    ):
        assert action(name, **kwargs) == {"CANCELLED"}
        assert s.checkpoint() == before
    try:
        commands.action(s, "ADD_KEYFRAME")
        raise AssertionError("locked command accepted")
    except ValueError:
        pass
    s.normalize_selection()
    assert (s.direction, s.key_index, s.contour, s.point, s.selected) == (
        model.LTR, 2, 0, 0, {(0, 0)}
    )
    RUN.report["checks"].append(
        "disabled row ignores real clicks; direct selection/edit calls are atomic; "
        "restored selection normalizes to left; English/Chinese lock tooltips render"
    )

    click("KEYFRAME:left_to_right:1")
    yield 0.1
    click("ADD_KEYFRAME")
    yield 0.15
    assert s.key_index == 2 and len(model.sweep(s.project, model.LTR)) == 6
    commands.handle_mode(s, "CORNER")
    mirrored(s)
    click("COPY_KEYFRAME")
    yield 0.15
    mirrored(s)
    six = deepcopy(s.project)
    click("REMOVE_KEYFRAME")
    yield 0.15
    assert len(model.sweep(s.project, model.RTL)) == 5
    mirrored(s)
    five = deepcopy(s.project)
    click("UNDO")
    yield 0.15
    assert s.project == six
    mirrored(s)
    click("REDO")
    yield 0.15
    assert s.project == five
    mirrored(s)
    RUN.report["checks"].append(
        "left insert/delete/copy/handle edits update mirrored data and row buttons immediately; "
        "undo/redo restore matching counts and artwork"
    )

    click("MIRROR")
    yield 0.15
    assert not s.project["mirror_sweeps"] and s.project["sweeps"] == five["sweeps"]
    click("KEYFRAME:right_to_left:2")
    yield 0.15
    click("ADD_KEYFRAME")
    yield 0.15
    assert s.keyframe["progress"] == 0.625
    click("TRIANGLE")
    yield 0.15
    independent = deepcopy(s.project)
    left = deepcopy(model.sweep(s.project, model.LTR))
    assert len(model.sweep(s.project, model.RTL)) == 6 and len(left) == 5
    pending = SimpleNamespace(dx=0.1, dy=0, angle=0, scale=1)
    bind(pending, s, target=True)
    history_count = len(s.history.undo_stack)
    click("MIRROR")
    yield 0.15
    assert s.project["mirror_sweeps"] and model.sweep(s.project, model.LTR) == left
    assert (s.direction, s.key_index, s.contour, s.point, s.selected) == (
        model.LTR, 2, 0, 0, {(0, 0)}
    )
    assert len(s.history.undo_stack) == history_count + 1
    mirrored(s)
    linked = deepcopy(s.project)
    assert ui.ANIME_SDF_GEN_OT_transform.execute(pending, bpy.context) == {"CANCELLED"}
    assert s.project == linked
    click("UNDO")
    yield 0.15
    assert s.project == independent
    click("KEYFRAME:right_to_left:3")
    yield 0.1
    click("REDO")
    yield 0.15
    assert s.project == linked and (s.direction, s.key_index) == (model.LTR, 2)
    mirrored(s)
    # Re-enable from left without changing its existing curve/point selection.
    click("MIRROR")
    yield 0.1
    s.point, s.selected = 2, {(0, 2)}
    click("MIRROR")
    yield 0.1
    assert s.point == 2 and s.selected == {(0, 2)} and s.project == linked
    RUN.report["checks"].append(
        "unlock preserves mirrored artwork; unequal independent right data never replaces left; "
        "enable/redo choose the earlier left frame on a tie; stale dialogs are rejected"
    )

    s.write_draft()
    draft = session.draft_root() / (s.project["id"] + ".sdfproject.json")
    saved = files.load_project(draft)
    explicit = RUN.out / "mirror.draft.sdfproject.json"
    files.atomic_text(explicit, model.dumps(saved))
    old_owner = s.registry.id
    e = s.editor
    with bpy.context.temp_override(window=e.window, area=e.native_area):
        bpy.ops.wm.save_as_mainfile(
            filepath=str(RUN.out / "save-with-mirror.blend"), check_existing=False
        )
    yield from wait_for(
        lambda: session.ACTIVE
        and session.ACTIVE.registry.id != old_owner
        and session.ACTIVE.editor.ready,
        60,
    )
    s = session.ACTIVE
    assert s.project == saved and s.direction == model.LTR and s.point == 2
    mirrored(s)
    session.end_session(True)
    yield 0.2
    with bpy.context.temp_override(window=RUN.origin):
        assert bpy.ops.anime_sdf_gen.open_project(filepath=str(explicit)) == {"FINISHED"}
    yield from wait_for(lambda: session.ACTIVE and session.ACTIVE.editor.ready)
    s = session.ACTIVE
    assert s.project == saved
    mirrored(s)
    yield from wait_for(lambda: s.preview.thresholds is not None or bool(s.error), 60)
    assert not s.error, s.error
    np.testing.assert_array_equal(s.preview.thresholds[..., 1], s.preview.thresholds[:, ::-1, 0])
    s.rotation, s.orbit_preview = 270, True
    s.preview.render()
    np.testing.assert_array_equal(s.preview.rgba[..., 0], decode(s.preview.thresholds[..., 1], 0.5))
    redraw()
    assert not widget(locked)["enabled"]
    shot(RUN.out, "03-right-half-playback.png")
    click("PLAY")
    yield from wait_for(lambda: s.playing and s.rotation != 270, 10)
    click("NEXT")
    yield 0.1
    s.export.start()
    yield from wait_for(lambda: s.closed or bool(s.error), 90)
    assert s.closed, s.error
    exported = files.load_project(RUN.out / "mirrored.sdfproject.json")
    assert exported["mirror_sweeps"] and exported["sweeps"] == saved["sweeps"]
    RUN.report["checks"].append(
        "draft/reopen and save/resume retain the lock and artwork; both preview halves play; "
        "512px export retains both mirrored sweeps"
    )
    anime_sdf_gen.unregister()
    after = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in hashes}
    assert after == hashes
    RUN.report["model_hashes"] = after


run(workflow, RUN, "mirror-lock.json")
