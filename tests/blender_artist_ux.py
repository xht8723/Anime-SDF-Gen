"""Artist workflow: safe setup return, named shapes, frame cues and export handoff."""

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
from anime_sdf_gen.ui_guard import bind
from anime_sdf_gen.viewport import scale
from tests.fixture import fixture_face
from tests.support import TestRun
from tests.ui_helpers import (
    center, click, dialog_confirm_position, event, labels, metadata, redraw, shot,
    wait_for, widget,
)
from tests.ui_runner import run

RUN = TestRun("artist-ux-2k").prepare(blender=True)
active = {}


def track(cls, key):
    original_invoke, original_execute = cls.invoke, cls.execute
    original_cancel = getattr(cls, "cancel", None)

    def invoke(self, context, event):
        active[getattr(self, "section", key)] = self
        return original_invoke(self, context, event)

    def execute(self, context):
        active.pop(getattr(self, "section", key), None)
        return original_execute(self, context)

    def cancel(self, context):
        active.pop(getattr(self, "section", key), None)
        if original_cancel:
            original_cancel(self, context)

    cls.invoke, cls.execute, cls.cancel = invoke, execute, cancel


track(ui.ANIME_SDF_GEN_OT_settings, "SETTINGS")
track(ui.ANIME_SDF_GEN_OT_refit, "REFIT")


def keypress(kind, xy=(2, 2), **kwargs):
    event(kind, xy=xy, **kwargs)
    kwargs.pop("unicode", None)
    event(kind, "RELEASE", xy, **kwargs)


def mouse_click(xy):
    event("MOUSEMOVE", "NOTHING", xy)
    yield 0.08
    event("LEFTMOUSE", xy=xy)
    yield 0.08
    event("LEFTMOUSE", "RELEASE", xy)
    yield 0.2


def open_dialog(key):
    redraw()
    xy = center(key)
    event("MOUSEMOVE", "NOTHING", xy)
    event("LEFTMOUSE", xy=xy)
    yield 0.6
    assert key not in active and session.ACTIVE.native_ui.pending
    event("LEFTMOUSE", "RELEASE", xy)
    yield from wait_for(lambda: key in active)
    yield 0.6
    assert key in active, "Dialog dismissed on release or idle"


def texts():
    return [value for value, *_ in labels()]


def reopen(path):
    with bpy.context.temp_override(window=RUN.origin):
        result = bpy.ops.anime_sdf_gen.open_project(filepath=str(path))
    assert result == {"FINISHED"}
    yield from wait_for(lambda: session.ACTIVE and session.ACTIVE.editor.ready)


def workflow():
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
              for name in ("bugs.blend", "test_sdf.blend")}
    anime_sdf_gen.register()
    face = fixture_face(source)
    p = model.new_project(face.reference, face.alignment, keyframes=5, resolution=512,
                          output=str(RUN.out / "artist"))
    p["authoring"]["stage"] = "ORIENT"
    s = session.start(bpy.context, p, face)
    yield from wait_for(lambda: s.editor.ready and s.editor.widgets)
    click("NEXT")
    yield 0.3
    assert s.stage == "FIT" and not s.revisiting_setup
    click("NEXT")
    yield 0.3
    assert s.stage == "EDIT" and s.key_index == 0
    assert any("Choose a middle keyframe" in t for t in texts())
    assert "Boundary movement in front view" in texts()
    assert "Mirrored from Left → Right" in texts()
    metadata()
    shot(RUN.out, "01-first-edit.png")

    click("KEYFRAME:left_to_right:2")
    yield 0.2
    click("TRIANGLE")
    yield 0.2
    assert len(s.selected) == 3
    assert any("3 points selected" in t for t in texts())
    yield from open_dialog("SHAPE_NAME")
    ok = dialog_confirm_position(RUN.out, "rename")
    xy = ok + np.array([70, 27]) * scale()
    yield from mouse_click(xy)
    keypress("A", xy, ctrl=True)
    for character in "cheek":
        keypress(character.upper(), xy, unicode=character)
    keypress("RET", xy)
    yield 0.1
    yield from mouse_click(ok)
    assert "SHAPE_NAME" not in active and s.curve["name"] == "cheek", (list(active), s.curve["name"])
    assert model.sweep(p, model.RTL)[2]["contours"][1]["name"] == "cheek"
    commands.action(s, "UNDO")
    assert s.curve["name"] == "Shape"
    commands.action(s, "REDO")
    assert s.curve["name"] == "cheek"
    before = deepcopy(s.project)
    try:
        commands.rename_shape(s, " \n ")
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid shape name accepted")
    assert s.project == before
    stale = SimpleNamespace(section="SHAPE_NAME", shape_name="Stale")
    bind(stale, s, target=True)
    s.select_keyframe(model.LTR, 1)
    assert ui.ANIME_SDF_GEN_OT_settings.execute(stale, bpy.context) == {"CANCELLED"}
    s.select_keyframe(model.LTR, 2)
    s.contour = 1
    s.reset_selection(whole_curve=True)
    shot(RUN.out, "02-named-shape.png")
    RUN.report["checks"].append("real rename press/release, native text edit, mirror, undo/redo and stale/invalid rejection")

    commands.action(s, "ADD_KEYFRAME")
    redraw()
    progress = s.keyframe["progress"]
    tip = widget("KEYFRAME:left_to_right:3")["tooltip"]["body"]
    assert f"{model.keyframe_rotation(model.LTR, progress):.2f}°" in tip
    commands.action(s, "MIRROR")
    s.select_keyframe(model.RTL, 0)
    assert any("Preview: Right → Left" in t for t in texts())
    commands.action(s, "MIRROR")
    s.select_keyframe(model.LTR, 3)
    authored = deepcopy(s.project["sweeps"])
    selected = (s.direction, s.key_index)
    s.orbit_preview = True
    s.rotation = 270
    s.preview.render()
    values = texts()
    assert any("Editing: Left → Right" in t for t in values)
    assert any("Preview: Right → Left" in t for t in values)
    assert (s.direction, s.key_index) == selected
    assert not widget("KEYFRAME:right_to_left:3")["enabled"]
    shot(RUN.out, "03-preview-vs-edit.png")

    click("BACK")
    yield 0.2
    assert s.revisiting_setup and s.stage == "FIT"
    click("PRESET_NOSE")
    yield 0.15
    click("KEYFRAMES_MORE")
    yield 0.15
    click("NEXT")
    yield 0.2
    assert s.stage == "EDIT" and s.project["sweeps"] == authored
    click("BACK")
    yield 0.2
    draft = RUN.out / "return-to-setup.sdfproject.json"
    files.atomic_text(draft, model.dumps(s.project))
    session.end_session(remove_draft=False)
    yield 0.2
    yield from reopen(draft)
    s = session.ACTIVE
    assert s.revisiting_setup and s.stage == "FIT"
    shot(RUN.out, "04-safe-return.png")
    yield from open_dialog("REFIT")
    keypress("ESC")
    yield 0.25
    assert "REFIT" not in active and s.project["sweeps"] == authored
    stale = SimpleNamespace()
    bind(stale, s, snapshot=True)
    s.project["preset"] = "CLEAN"
    assert ui.ANIME_SDF_GEN_OT_refit.execute(stale, bpy.context) == {"CANCELLED"}
    s.project["preset"] = "NOSE"
    yield from open_dialog("REFIT")
    ok = dialog_confirm_position(RUN.out, "refit-confirmation")
    yield from mouse_click(ok)
    assert s.stage == "EDIT" and s.project["sweeps"] != authored
    refitted = deepcopy(s.project)
    assert any(c["name"] == "cheek" for frame in model.sweep(s.project, model.LTR)
               for c in frame["contours"])
    commands.action(s, "UNDO")
    assert s.revisiting_setup and s.project["sweeps"] == authored
    commands.action(s, "REDO")
    assert s.project == refitted
    click("BACK")
    yield 0.2
    click("BACK")
    yield 0.2
    assert s.stage == "ORIENT" and s.revisiting_setup
    click("NEXT")
    yield 0.2
    assert s.stage == "FIT" and s.revisiting_setup
    click("NEXT")
    yield 0.2
    assert s.project["sweeps"] == refitted["sweeps"]
    RUN.report["checks"].append("return preserves authored curves after setup changes, draft/reopen, orientation revisit; explicit refit cancels, rejects stale input, and supports undo/redo")

    view = bpy.context.preferences.view
    view.language = "zh_HANS"
    view.use_translate_interface = view.use_translate_tooltips = True
    s.refresh_language()
    shot(RUN.out, "05-edit-chinese.png")
    assert "由“左 → 右”镜像生成" in texts()
    view.language = "en_US"
    s.refresh_language()
    # A clean preset ensures handoff validation is independent of test artwork.
    commands.action(s, "BACK")
    for frames in s.project["sweeps"].values():
        for frame in frames:
            frame["contours"] = frame["contours"][:1]
    s.fit(5)
    s.confirm()
    yield from wait_for(lambda: s.preview.thresholds is not None or bool(s.error), 90)
    assert not s.error, str(s.error)
    assert session.LAST_EXPORT is None
    s.export.start()
    s.export.cancel()
    assert session.LAST_EXPORT is None
    replacing = any(Path(path).exists() for path in files.output_paths(
        s.project, s.project["settings"]["output"]
    ))
    click("GENERATE")
    if replacing:
        yield 0.6
        ok = dialog_confirm_position(RUN.out, "replace-export")
        yield from mouse_click(ok)
    yield from wait_for(lambda: session.ACTIVE is None, 120)
    paths = session.LAST_EXPORT
    assert paths and all(Path(path).is_file() for path in paths)
    assert paths[-1].endswith("artist.sdfproject.json")
    with bpy.context.temp_override(window=RUN.origin):
        area = next(a for a in RUN.origin.screen.areas if a.type == "VIEW_3D")
        area.spaces.active.show_region_ui = True
        with bpy.context.temp_override(area=area):
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
            bpy.ops.screen.screenshot(filepath=str(RUN.out / "06-export-complete.png"))
    yield from reopen(paths[-1])
    assert session.LAST_EXPORT == paths and session.ACTIVE.stage == "CONFIRM"
    session.end_session(remove_draft=True)
    RUN.report["checks"].append("cancel leaves completion unchanged; successful export keeps verified paths after closure and project reopening")
    anime_sdf_gen.unregister()
    assert hashes == {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in hashes}
    RUN.report["model_hashes"] = hashes


run(workflow, RUN, "artist-ux.json", timeout=300)
