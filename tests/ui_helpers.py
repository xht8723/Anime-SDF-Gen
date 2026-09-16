"""Real Blender event, redraw and screenshot helpers for the current popup."""

import time
import bpy
import numpy as np
from anime_sdf_gen import session
from anime_sdf_gen.viewport import window_region


def redraw():
    e = session.ACTIVE.editor
    with bpy.context.temp_override(
        window=e.window, area=e.native_area, region=window_region(e.native_area)
    ):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    assert not session.ACTIVE._draw_error, session.ACTIVE._draw_error


def shot(output, name, pixels=False):
    redraw()
    e = session.ACTIVE.editor
    with bpy.context.temp_override(
        window=e.window, area=e.native_area, region=window_region(e.native_area)
    ):
        bpy.ops.screen.screenshot(filepath=str(output / name))
    if pixels:
        img = bpy.data.images.load(str(output / name), check_existing=False)
        try:
            a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
            img.pixels.foreach_get(a)
            a = a.reshape(img.size[1], img.size[0], 4)
            r = e.views["PREVIEW"].region
            n = window_region(e.native_area)
            return a[r.y + n.y : r.y + n.y + r.height, r.x + n.x : r.x + n.x + r.width, :3].copy()
        finally:
            bpy.data.images.remove(img)


def labels():
    found = []
    painter = session.ACTIVE.editor.painter
    original = painter.label

    def record(value, x, y, *args):
        found.append((value, x, y))
        return original(value, x, y, *args)

    painter.label = record
    try:
        redraw()
    finally:
        painter.label = original
    return found


def widget(key):
    return next(w for w in session.ACTIVE.editor.widgets if w["key"] == key)


def center(key):
    x, y, w, h = widget(key)["box"]
    return (x + w / 2, y + h / 2)


def event(kind, value="PRESS", xy=(2, 2), **kwargs):
    e = session.ACTIVE.editor
    n = window_region(e.native_area)
    e.window.event_simulate(
        type=kind, value=value, x=int(xy[0] + n.x), y=int(xy[1] + n.y), **kwargs
    )


def hover(key):
    redraw()
    event("MOUSEMOVE", "NOTHING", center(key))


def click(key):
    redraw()
    item = widget(key)
    assert item["enabled"], key
    xy = center(key)
    if "clip" in item:
        x, y, w, h = item["clip"]
        assert x <= xy[0] < x + w and y <= xy[1] < y + h, (key, item)
    event("MOUSEMOVE", "NOTHING", xy)
    event("LEFTMOUSE", xy=xy)
    event("LEFTMOUSE", "RELEASE", xy)


def metadata():
    for item in session.ACTIVE.editor.widgets:
        tip = item["tooltip"]
        assert tip["title"] != "Control" and tip["body"], item
        if not item["enabled"]:
            assert tip["reason"], item


def tooltip_visible():
    redraw()
    e = session.ACTIVE.editor
    box = e.tooltip_box
    assert box and e.tooltip_ready, {
        "hover": e.hover,
        "ready": e.tooltip_ready,
        "age": time.perf_counter() - e.hover_since,
        "pos": e.hover_pos,
        "box": box,
    }
    x, y, w, h = box
    n = window_region(e.native_area)
    assert 0 <= x < x + w <= n.width and 0 <= y < y + h <= n.height, box
    return box


def await_tooltip(key):
    # Allow the first large GPU draw to finish before judging the hover timer.
    deadline = time.perf_counter() + 10
    while time.perf_counter() < deadline:
        redraw()
        if session.ACTIVE.editor.tooltip_box and session.ACTIVE.editor.hover == key:
            break
        yield 0.1
    tooltip_visible()
    assert session.ACTIVE.editor.hover == key


def wait_for(predicate, timeout=20):
    deadline = time.perf_counter() + timeout
    while not predicate():
        assert time.perf_counter() < deadline, "Timed out waiting for UI state"
        yield 0.1
