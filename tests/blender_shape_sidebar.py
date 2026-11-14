"""Real full-height sidebar selection, curve/point controls, and nested scrolling."""

from copy import deepcopy
import hashlib
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import anime_sdf_gen
from anime_sdf_gen import canvas, commands, session, source
from anime_sdf_gen.core import model
from tests.fixture import fixture_face
from tests.support import TestRun
from tests.ui_helpers import click, event, redraw, shot, wait_for, widget, metadata
from tests.ui_runner import run

RUN = TestRun("shape-sidebar-2k").prepare(blender=True)


def center(rect):
    return rect.x + rect.width / 2, rect.y + rect.height / 2


def click_xy(xy):
    event("MOUSEMOVE", "NOTHING", xy)
    event("LEFTMOUSE", xy=xy)
    yield 0.1
    event("LEFTMOUSE", "RELEASE", xy)
    yield 0.15


def contained(item, bounds):
    x, y, w, h = item["box"]
    assert bounds.x <= x and bounds.y <= y
    assert x + w <= bounds.x + bounds.width + 1 and y + h <= bounds.y + bounds.height + 1, item


def workflow():
    hashes = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest()
              for n in ("bugs.blend", "test_sdf.blend")}
    anime_sdf_gen.register()
    face = fixture_face(source)
    s = session.start(bpy.context, model.new_project(face.reference, face.alignment, keyframes=5), face)
    yield from wait_for(lambda: s.editor.ready and s.editor.widgets)
    e = s.editor
    click("KEYFRAME:left_to_right:2")
    yield 0.2
    assert e.boxes["PANEL"].y == 0
    assert e.boxes["PANEL"].height == e.boxes["TOP"].y
    assert e.boxes["SHELF"].width == e.boxes["PANEL"].x
    assert widget("LAYER:0")["style"] == "LIST_ROW"
    assert not any(w["key"] == "DELETE_SHAPE" for w in e.widgets)
    shot(RUN.out, "01-main-boundary.png")

    for _ in range(12):
        click("TRIANGLE")
        yield 0.07
    redraw()
    assert e.shape_scroll > 0 and e.shape_scroll_max > 0 and s.contour == 12
    contained(widget("LAYER:12"), e.boxes["SHAPE_LIST"])
    for key in ("TRIANGLE", "LIT", "SHADOW", "SHAPE_NAME", "TRANSFORM", "DUPLICATE", "DELETE_SHAPE", "UP", "DOWN", "TOGGLE"):
        contained(widget(key), e.boxes["PANEL"])
    for key in ("ADD_KEYFRAME", "REMOVE_KEYFRAME", "COPY_KEYFRAME", "MIRROR", "PLAY"):
        contained(widget(key), e.boxes["TIMELINE"])
    for key in ("POINT", "SMOOTH", "CORNER", "FREE", "INSERT_POINT", "DELETE_POINT"):
        contained(widget(key), e.boxes["PANEL"])
    metadata()
    saved = deepcopy(s.project)
    selected = (s.contour, s.point, set(s.selected))
    frame_scroll = s.keyframe_scroll
    xy = center(e.shape_list)
    previous = e.shape_scroll
    event("WHEELUPMOUSE", xy=xy)
    yield 0.15
    assert e.shape_scroll == previous - 1 and s.keyframe_scroll == frame_scroll
    assert s.project == saved and selected == (s.contour, s.point, set(s.selected))
    # The visible scrollbar is interactive, including track clicks and dragging.
    track = e.shape_scroll_track
    yield from click_xy((track.x + track.width / 2, track.y + track.height - 1))
    assert e.shape_scroll == 0 and s.contour == 12
    thumb = e.shape_scroll_thumb
    event("LEFTMOUSE", xy=center(thumb))
    yield 0.1
    event("MOUSEMOVE", "NOTHING", (track.x + track.width / 2, track.y))
    yield 0.1
    event("LEFTMOUSE", "RELEASE", (track.x + track.width / 2, track.y))
    yield 0.15
    assert e.shape_scroll == e.shape_scroll_max
    yield from click_xy((track.x + track.width / 2, track.y + track.height - 1))
    click("LAYER:1")
    yield 0.15
    assert s.contour == 1 and len(s.selected) == 3
    click("LIT")
    yield 0.15
    click("TOGGLE")
    yield 0.15
    assert s.curve["operation"] == "REMOVE" and not s.curve["enabled"]
    assert not model.sweep(s.project, model.RTL)[2]["contours"][1]["enabled"]
    click("UNDO")
    yield 0.15
    assert s.curve["enabled"]
    click("REDO")
    yield 0.15
    assert not s.curve["enabled"]
    click("TOGGLE")
    yield 0.15
    commands.rename_shape(s, "Cheek / 颧骨 · a deliberately long descriptive shape name")
    click("DUPLICATE")
    yield 0.15
    clone = deepcopy(s.curve)
    index = s.contour
    click("UP")
    yield 0.15
    assert s.contour == index - 1 and s.curve == clone
    click("DOWN")
    yield 0.15
    assert s.contour == index and s.curve == clone
    click("DELETE_SHAPE")
    yield 0.15
    assert len(s.keyframe["contours"]) == 13
    click("UNDO")
    yield 0.15
    assert len(s.keyframe["contours"]) == 14
    shot(RUN.out, "02-shape-stack.png")
    RUN.report["checks"].append("full-height sidebar groups the list, shape actions and point properties; wheel/track/drag scrolling preserves selection and artwork; shape actions, mirroring and undo/redo work")

    # A canvas selection reveals the matching row even after scrolling away.
    e.shape_scroll = e.shape_scroll_max
    redraw()
    view = e.views["AUTHOR"]
    q = canvas.to_view(s, s.keyframe["contours"][0]["points"][2]["co"], view)
    yield from click_xy((view.region.x + q.x, view.region.y + q.y))
    assert s.contour == 0 and e.shape_scroll == 0
    click("KEYFRAME:left_to_right:1")
    yield 0.15
    assert e.shape_scroll == 0 and e.shape_scroll_max == 0 and e.shape_scroll_track is None
    click("KEYFRAME:left_to_right:2")
    yield 0.15
    click("LAYER:1")
    yield 0.15
    # Errors stay above the dock, and dismissing them cannot select a shape.
    s.notify_error("Select a closed curve first.")
    redraw()
    assert e.warning_bounds.y == 0
    contained(widget("DISMISS_ERROR"), e.boxes["PANEL"])
    click("DISMISS_ERROR")
    yield 0.15
    assert not s.error and s.contour == 1
    # A tall warning forces property scrolling. List clips remain nested inside
    # the visible sidebar body, so hidden rows and scrollbars cannot take input.
    from anime_sdf_gen.core.messages import raw
    s.error = raw("A long validation message to exercise the sidebar footer. " * 60)
    redraw()
    assert e.panel_scroll_max > 0
    artwork = deepcopy(s.project)
    list_scroll = e.shape_scroll
    body = e.boxes["PANEL_BODY"]
    xy = (body.x + body.width / 2, body.y + 5)
    assert not e.shape_list.contains(xy)
    for _ in range(24):
        event("WHEELDOWNMOUSE", xy=xy)
        yield 0.025
    redraw()
    assert e.panel_scroll > 0 and e.shape_scroll == list_scroll and s.project == artwork
    for item in e.widgets:
        if item.get("style") == "LIST_ROW":
            cx, cy, cw, ch = item["clip"]
            assert cw == 0 or ch == 0 or (body.x <= cx and body.y <= cy
                    and cx + cw <= body.x + body.width and cy + ch <= body.y + body.height)
    click("CORNER")
    yield 0.15
    assert all(point["mode"] == "CORNER" for point in s.curve["points"])
    click("UNDO")
    yield 0.15
    assert s.project == artwork
    s.error = ""
    e.panel_scroll = 0
    redraw()
    click("FOCUS_AUTHOR")
    yield 0.15
    redraw()
    contained(widget("LAYER:1"), e.boxes["SHAPE_LIST"])
    click("FOCUS_AUTHOR")
    yield 0.15
    redraw()
    view = bpy.context.preferences.view
    view.language = "zh_HANS"
    view.use_translate_interface = view.use_translate_tooltips = True
    s.refresh_language()
    shot(RUN.out, "03-shapes-chinese.png")
    metadata()
    view.language = "en_US"
    s.refresh_language()
    # Stage changes restore the sidebar without persisting UI scroll state in the project.
    click("NEXT")
    yield 0.2
    redraw()
    assert s.stage == "CONFIRM" and "SHAPE_LIST" not in e.boxes
    click("BACK")
    yield 0.2
    redraw()
    assert s.stage == "EDIT" and "SHAPE_LIST" in e.boxes
    RUN.report["checks"].append("canvas/frame selection reveals the active row; nested list clips and independent property scrolling preserve input; point editing, focus, errors, language and stage changes retain correct sidebar hit regions")
    RUN.report["window_dimensions"] = [e.window.width, e.window.height]
    session.end_session(remove_draft=True)
    anime_sdf_gen.unregister()
    assert hashes == {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in hashes}
    RUN.report["model_hashes"] = hashes


run(workflow, RUN, "shape-sidebar.json", timeout=180)
