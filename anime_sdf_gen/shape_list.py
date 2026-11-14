"""Flat shape rows and their independent scrollbar inside the sidebar."""

from .core.messages import mark, contour_label
from .theme import BG, BORDER, SELECT, HOVER, TEXT, MUTED, ACCENT
from .tooltips import describe
from .viewport import Rect, scale


def draw_shape_list(s, text, body):
    e, u = s.editor, scale()
    p = e.painter
    e.boxes["SHAPE_LIST"] = body
    panel = e.boxes["PANEL_BODY"]
    left, bottom = max(body.x, panel.x), max(body.y, panel.y)
    right = min(body.x + body.width, panel.x + panel.width)
    top = min(body.y + body.height, panel.y + panel.height)
    clip = Rect(left, bottom, max(0, right - left), max(0, top - bottom))
    e.shape_list = clip
    e.shape_scroll_track = e.shape_scroll_thumb = None
    p.rectangle(*body.box, BG, 3 * u, BORDER, 0.7 * u)
    contours = s.keyframe["contours"]
    row_height = 38 * u
    slots = max(1, int((body.height - 4 * u) / row_height))
    e.shape_scroll_max = max(0, len(contours) - slots)
    selection = (s.direction, s.key_index, s.contour, len(contours))
    if selection != e.shape_selection:
        # Changes from the canvas, undo, or a new frame reveal the active shape.
        e.shape_scroll = min(e.shape_scroll, s.contour)
        e.shape_scroll = max(e.shape_scroll, s.contour - slots + 1)
        e.shape_selection = selection
    e.shape_scroll = max(0, min(e.shape_scroll, e.shape_scroll_max))
    row_width = body.width - (16 if e.shape_scroll_max else 4) * u
    for index in range(e.shape_scroll, min(len(contours), e.shape_scroll + slots)):
        curve = contours[index]
        key = f"LAYER:{index}"
        y = body.y + body.height - 2 * u - (index - e.shape_scroll + 1) * row_height
        box = (body.x + 2 * u, y, row_width, row_height)
        selected = index == s.contour
        if selected or e.hover == key:
            p.rectangle(*box, SELECT if selected else HOVER)
        if selected:
            p.rectangle(box[0], y, 3 * u, row_height, ACCENT)
        color = TEXT if curve["enabled"] else MUTED
        text(contour_label(curve["name"]), box[0] + 12 * u,
             y + (22 if curve["closed"] else 14) * u, 12, color, row_width - 24 * u)
        if curve["closed"]:
            effect = mark("Lit cutout") if curve["operation"] == "REMOVE" else mark("Shadow patch")
            text(mark("Hidden") if not curve["enabled"] else effect,
                 box[0] + 12 * u, y + 7 * u, 10, MUTED, row_width - 24 * u)
        p.line((box[0] + 8 * u, y), (box[0] + row_width - 8 * u, y), BORDER, 0.5 * u)
        e.widgets.append({"key": key, "box": box, "clip": clip.box,
                          "enabled": not s.busy, "style": "LIST_ROW",
                          "tooltip": describe(s, key, not s.busy)})
    if e.shape_scroll_max:
        track = Rect(round(body.x + body.width - 12 * u), body.y + 3,
                     max(1, round(10 * u)), max(1, body.height - 6))
        thumb = max(22 * u, track.height * slots / len(contours))
        ty = track.y + (track.height - thumb) * (1 - e.shape_scroll / e.shape_scroll_max)
        e.boxes["SHAPE_SCROLL_TRACK"] = track
        e.boxes["SHAPE_SCROLL_THUMB"] = Rect(track.x, ty, track.width, thumb)
        e.shape_scroll_track = track
        e.shape_scroll_thumb = e.boxes["SHAPE_SCROLL_THUMB"]
        p.rectangle(track.x + 3 * u, track.y, 3 * u, track.height, BORDER, u)
        p.rectangle(track.x + 2 * u, ty, 5 * u, thumb, MUTED, 2 * u)

