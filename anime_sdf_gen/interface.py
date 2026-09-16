"""Quiet, rounded popup controls; view layout remains owned by Editor."""

import bpy
import gpu
from .viewport import scale, Rect
from .tooltips import describe
from .core import model
from . import commands
from .theme import (
    BG,
    PANEL,
    BUTTON,
    HOVER,
    BORDER,
    SELECT,
    SELECT_HOVER,
    ACCENT,
    PRIMARY,
    PRIMARY_HOVER,
    TEXT,
    MUTED,
    WARN,
)
from .typography import measure, shorten, wrap, button_height
from .i18n import iface, report
from .core.messages import mark, msg, raw
from .panels import Sidebar


def icon(p, name, box, color, u):
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    paths = []
    if name in ("UNDO", "REDO"):
        sign = -1 if name == "REDO" else 1
        paths = [
            [(sign * a, b) for a, b in [(-7, 4), (0, 4), (5, 1), (5, -5)]],
            [(sign * a, b) for a, b in [(-2, 9), (-7, 4), (-2, -1)]],
        ]
    elif name == "BACK":
        paths = [[(7, 0), (-7, 0)], [(-2, 5), (-7, 0), (-2, -5)]]
    elif name == "CLOSE":
        paths = [[(-4, -4), (4, 4)], [(-4, 4), (4, -4)]]
    elif name == "PLUS":
        paths = [[(-5, 0), (5, 0)], [(0, -5), (0, 5)]]
    elif name == "MINUS":
        paths = [[(-5, 0), (5, 0)]]
    elif name == "SHADING":
        p.rectangle(cx - 7 * u, cy - 7 * u, 14 * u, 14 * u, BUTTON, 7 * u, color, 1.3 * u)
        paths = [[(0, 6), (0, -6)], [(-3, 4), (-3, -4)]]
    for path in paths:
        for a, b in zip(path, path[1:]):
            p.line((cx + a[0] * u, cy + a[1] * u), (cx + b[0] * u, cy + b[1] * u), color, 1.5 * u)


def build(s, region):
    e = s.editor
    u = scale()
    w, h = region.width, region.height
    p = e.painter
    p.begin(w, h)
    e.widgets = []
    setup = s.stage in ("ORIENT", "FIT")
    confirm = s.stage == "CONFIRM"

    def text(value, x, y, size=13, color=TEXT, max_width=None, center=False):
        value = iface(value)
        if max_width is not None:
            value = shorten(value, max_width, size)
        if center:
            x -= measure(value, size) / 2
        p.label(value, x, y, size, color)

    def button(
        key,
        value,
        box,
        selected=False,
        enabled=True,
        primary=False,
        size=13,
        icon_name=None,
        center=False,
    ):
        x, y, bw, bh = box
        hover = enabled and e.hover == key
        fill = (
            (PRIMARY_HOVER if hover else PRIMARY)
            if primary
            else (SELECT_HOVER if hover else SELECT) if selected else HOVER if hover else BUTTON
        )
        edge = PRIMARY_HOVER if primary else (0.27, 0.43, 0.46, 1) if selected else BORDER
        foreground = (0.065, 0.13, 0.15, 1) if primary else TEXT
        if not enabled:
            fill = tuple(v * 0.76 for v in fill[:3]) + (1,)
            foreground = (0.41, 0.46, 0.51, 1)
            edge = BUTTON
        p.rectangle(x, y, bw, bh, fill, 7 * u, edge, 0.7 * u)
        if icon_name:
            icon(p, icon_name, box, foreground, u)
        else:
            height = button_height(iface(value), size)
            text(
                value,
                x + bw / 2 if center else x + 12 * u,
                y + (bh - height) / 2 + 1 * u,
                size,
                foreground,
                bw - 24 * u,
                center,
            )
        e.widgets.append(
            {"key": key, "box": box, "enabled": enabled, "tooltip": describe(s, key, enabled)}
        )

    p.rectangle(*e.boxes["TOP"].box, PANEL)
    text("Anime SDF Gen", 20 * u, h - 27 * u, 18)
    primary_key = "CANCEL_GENERATION" if s.busy else "GENERATE" if confirm else "NEXT"
    primary_text = (
        mark("Cancel generation")
        if s.busy
        else mark("Generate & Finish") if confirm else mark("Next Step  →")
    )
    bw = min(230 * u, w * 0.30)
    primary_x = w - 16 * u - bw
    back_x = primary_x - 46 * u
    button(
        primary_key,
        primary_text,
        (primary_x, h - 80 * u, bw, 42 * u),
        primary=True,
        size=15,
        center=True,
    )
    button(
        "BACK",
        "",
        (back_x, h - 76 * u, 38 * u, 34 * u),
        enabled=s.stage != "ORIENT" and not s.busy,
        icon_name="BACK",
    )
    actions = [
        ("UNDO", "", 36, bool(s.history.undo_stack)),
        ("REDO", "", 36, bool(s.history.redo_stack)),
        ("DRAFT", mark("Save draft & close"), 148, True),
        ("CLOSE", mark("Discard & close"), 130, True),
    ]
    x = 16 * u
    for key, value, b, enabled in actions:
        if w < 1040 * u:
            value = {"DRAFT": mark("Save & close"), "CLOSE": mark("Close")}.get(key, value)
            b = min(b, 110)
        if x + b * u > back_x - 12 * u:
            break
        button(
            key,
            value,
            (x, h - 77 * u, b * u, 34 * u),
            enabled=(not s.busy and enabled) or key == "CLOSE",
            icon_name=key if key in ("UNDO", "REDO") else None,
        )
        x += (b + 7) * u

    for name in ("AUTHOR", "PREVIEW"):
        if name not in e.boxes:
            continue
        x, y, vw, vh = e.boxes[name].box
        top = y + vh
        p.rectangle(x, top - 56 * u, vw, 56 * u, PANEL)
        controls = 0
        if not setup:
            focus_x = x + vw - 12 * u if confirm else x + vw - 96 * u
            if not confirm:
                button(
                    "FOCUS_" + name,
                    mark("Split views") if e.focus == name else mark("Focus"),
                    (focus_x, top - 41 * u, 84 * u, 28 * u),
                    enabled=not s.busy,
                    size=12,
                    center=True,
                )
            controls = (12 if confirm else 108) * u
            if name == "PREVIEW":
                compact = vw < 370 * u
                flat_w = (34 if compact else 124) * u
                flat_x = focus_x - flat_w - (0 if confirm else 8) * u
                button(
                    "FLAT",
                    mark("Flat mask") if s.flat else mark("Shaded preview"),
                    (flat_x, top - 41 * u, flat_w, 28 * u),
                    selected=s.flat,
                    enabled=not s.busy,
                    size=12,
                    icon_name="SHADING" if compact else None,
                    center=True,
                )
                controls += flat_w + 8 * u
        if name == "AUTHOR" or e.focus == "PREVIEW" or confirm:
            number, guide = {
                "ORIENT": ("1 / 4", mark("Orient the face to front view.")),
                "FIT": ("2 / 4", mark("Place markers.")),
                "EDIT": ("3 / 4", mark("Adjust curves.")),
                "CONFIRM": ("4 / 4", mark("Confirm.")),
            }[s.stage]
            p.rectangle(x + 16 * u, top - 41 * u, 44 * u, 25 * u, SELECT, 8 * u)
            text(number, x + 38 * u, top - 34 * u, 12, ACCENT, center=True)
            text(
                guide,
                x + 76 * u,
                top - 34 * u,
                17,
                TEXT,
                max(0, vw - 76 * u - max(controls, 16 * u)),
            )
        else:
            text(
                mark("Live shadow preview"),
                x + 18 * u,
                top - 33 * u,
                13,
                MUTED,
                max(0, vw - 18 * u - controls),
            )
    if "DIVIDER" in e.boxes:
        d = e.boxes["DIVIDER"]
        p.rectangle(d.x, d.y, d.width, d.height, BG)
        p.rectangle(d.x + d.width / 2, d.y, 1, d.height, BORDER)
    p.flush()

    panel = e.boxes["PANEL"]
    px, py, pw, ph = panel.box
    x = px + 16 * u
    cw = pw - 32 * u
    p.rectangle(*panel.box, PANEL)
    p.flush()
    notice = report(s.error or s.seam_warning)
    if e.warning_text != notice:
        e.warning_text = notice
        e.warning_scroll = 0
    warning_lines = wrap(notice, cw - 12 * u) if notice else []
    footer = min(ph * 0.48, (len(warning_lines) * 18 + 78) * u) if warning_lines else 0
    footer = int(footer)
    body = Rect(px, footer, pw, max(1, ph - footer))
    e.boxes["PANEL_BODY"] = body
    e.boxes["WARNING"] = Rect(px, 0, pw, footer)
    e.warning_bounds = e.boxes["WARNING"]
    old_scissor = gpu.state.scissor_get()
    gpu.state.scissor_test_set(True)
    gpu.state.scissor_set(*body.box)
    panel_start = len(e.widgets)
    scroll = max(0, e.panel_scroll)
    y = ph - 29 * u + scroll
    sidebar = Sidebar(s, text, button, p, e, x, cw, u, y)
    if confirm:
        sidebar.confirm()
    else:
        if setup:
            sidebar.setup()
        if s.stage == "FIT":
            sidebar.fitting()
        sidebar.reference()
        if setup:
            sidebar.navigation()
        else:
            sidebar.edit()
    y = sidebar.y
    extent = (ph - 29 * u) - (y - scroll)
    e.panel_scroll_max = max(0, extent - body.height + 32 * u)
    e.panel_scroll = min(e.panel_scroll, e.panel_scroll_max)
    for widget in e.widgets[panel_start:]:
        widget["clip"] = body.box
    if e.panel_scroll_max:
        thumb = max(24 * u, body.height * body.height / (body.height + e.panel_scroll_max))
        thumb_y = body.y + (body.height - thumb) * (1 - e.panel_scroll / e.panel_scroll_max)
        p.rectangle(px + pw - 5 * u, thumb_y, 3 * u, thumb, MUTED, 1.5 * u)
    p.flush()
    gpu.state.scissor_set(px, py, pw, ph)
    if warning_lines:
        card = (px + 12 * u, 12 * u, pw - 24 * u, footer - 18 * u)
        p.rectangle(*card, (0.15, 0.119, 0.111, 1), 8 * u, (0.30, 0.235, 0.20, 1), 0.7 * u)
        text(mark("Needs attention"), x + 6 * u, footer - 30 * u, 12, WARN, cw - 38 * u)
        button(
            "DISMISS_ERROR",
            "",
            (px + pw - 48 * u, footer - 38 * u, 24 * u, 24 * u),
            icon_name="CLOSE",
        )
        p.flush()
        message = Rect(
            round(x + 6 * u), round(24 * u), round(cw - 12 * u), max(1, round(footer - 71 * u))
        )
        e.boxes["WARNING_TEXT"] = message
        e.warning_scroll_max = max(0, len(warning_lines) * 18 * u - message.height)
        e.warning_scroll = min(e.warning_scroll, e.warning_scroll_max)
        gpu.state.scissor_set(*message.box)
        for i, line in enumerate(warning_lines):
            text(
                raw(line),
                message.x,
                message.y + message.height - 14 * u - i * 18 * u + e.warning_scroll,
                12.5,
                WARN,
            )
        p.flush()
        gpu.state.scissor_set(px, py, pw, ph)
        if e.warning_scroll_max:
            thumb = max(15 * u, message.height**2 / (message.height + e.warning_scroll_max))
            p.rectangle(
                px + pw - 20 * u,
                message.y
                + (message.height - thumb) * (1 - e.warning_scroll / e.warning_scroll_max),
                2 * u,
                thumb,
                WARN,
                u,
            )
            p.flush()
    else:
        e.warning_scroll_max = 0
    gpu.state.scissor_set(*old_scissor)
    gpu.state.scissor_test_set(False)

    if not setup:
        shelf = e.boxes["SHELF"]
        sx, sy, sw, sh = shelf.box
        p.rectangle(*shelf.box, BG)
        direction, progress = model.rotation_sample(s.rotation)
        if not confirm:
            label_width = 145 * u
            start_x = label_width + 16 * u
            columns = max(2, int((sw - start_x - 16 * u) / (48 * u)))
            max_count = max(len(model.sweep(s.project, d)) for d in model.SWEEP_LABELS)
            s.keyframe_scroll = max(
                0, min(getattr(s, "keyframe_scroll", 0), max(0, max_count - columns))
            )
            for row_index, (row_direction, title) in enumerate(model.SWEEP_LABELS.items()):
                frames = model.sweep(s.project, row_direction)
                start = min(s.keyframe_scroll, max(0, len(frames) - columns))
                shown = list(enumerate(frames))[start : start + columns]
                bw = (sw - start_x - 16 * u) / len(shown)
                row_y = sh - (34 + 33 * row_index) * u
                active = (direction if s.orbit_preview else s.direction) == row_direction
                text(
                    title,
                    16 * u,
                    row_y + 7 * u,
                    13,
                    ACCENT if active else MUTED,
                    label_width - 8 * u,
                )
                nearest = min(
                    range(len(frames)), key=lambda i: abs(frames[i]["progress"] - progress)
                )
                for column, (index, frame) in enumerate(shown):
                    chosen = active and index == (nearest if s.orbit_preview else s.key_index)
                    button(
                        f"KEYFRAME:{row_direction}:{index}",
                        str(index + 1),
                        (start_x + column * bw, row_y, bw - 6 * u, 25 * u),
                        chosen,
                        not s.busy,
                        size=12,
                        center=True,
                    )
        text(
            msg("Light rotation · {rotation:.0f}°", rotation=s.rotation), 16 * u, 67 * u, 12, MUTED
        )
        button(
            "PLAY",
            mark("Pause") if s.playing else mark("Play 360°"),
            (16 * u, 32 * u, 95 * u, 26 * u),
            enabled=not s.busy,
            size=12,
            center=True,
        )
        slider = (130 * u, 34 * u, max(1, sw - 152 * u), 22 * u)
        e.boxes["SLIDER"] = slider
        x, y, ww, hh = slider
        p.rectangle(x, y + hh / 2 - u, ww, 2 * u, BORDER, u)
        p.rectangle(
            x + s.rotation / 360 * ww - 5 * u, y + hh / 2 - 5 * u, 10 * u, 10 * u, ACCENT, 5 * u
        )
        for fraction, caption in (
            (0, mark("Front")),
            (0.25, mark("Character left")),
            (0.5, mark("Back")),
            (0.75, mark("Character right")),
            (1, mark("Front")),
        ):
            tx = x + fraction * ww
            if fraction == 1:
                tx -= measure(iface(caption), 10)
            text(caption, tx, y - 13 * u, 10, MUTED, center=0 < fraction < 1)
        if s.busy:
            text(raw(report(s.export.message)), 16 * u, 7 * u, 11, MUTED, sw - 32 * u)
        p.flush()
    draw_tooltip(s, region)


def draw_tooltip(s, region):
    e = s.editor
    e.tooltip_box = None
    if not e.tooltip_ready or not e.hover or s.dragging or e.navigation.running():
        return
    widget = next((item for item in e.widgets if item["key"] == e.hover), None)
    if not widget:
        return
    x, y, w, h = widget["box"]
    mx, my = e.hover_pos

    def inside(box):
        return box[0] <= mx < box[0] + box[2] and box[1] <= my < box[1] + box[3]

    if not inside(widget["box"]) or ("clip" in widget and not inside(widget["clip"])):
        return
    u = scale()
    tip = widget["tooltip"]
    width = min(320 * u, region.width - 24 * u)
    body = wrap(tip["body"], width - 28 * u, 12)
    reason = wrap(tip["reason"], width - 28 * u, 12) if tip["reason"] else []
    height = (48 + 18 * (len(body) + len(reason)) + (8 if reason else 0)) * u
    tx = max(12 * u, min(x, region.width - width - 12 * u))
    ty = y - height - 10 * u
    if ty < 12 * u:
        ty = y + h + 10 * u
    ty = max(12 * u, min(ty, region.height - height - 12 * u))
    e.tooltip_box = (tx, ty, width, height)
    p = e.painter
    p.rectangle(tx, ty - 3 * u, width, height, (0.015, 0.02, 0.026, 0.4), 8 * u)
    p.rectangle(
        tx, ty, width, height, (0.105, 0.125, 0.153, 1), 8 * u, (0.26, 0.32, 0.38, 1), 0.8 * u
    )
    p.label(shorten(tip["title"], width - 28 * u, 13), tx + 14 * u, ty + height - 24 * u, 13, TEXT)
    yy = ty + height - 45 * u
    for line in body:
        p.label(line, tx + 14 * u, yy, 12, (0.71, 0.77, 0.83, 1))
        yy -= 18 * u
    if reason:
        yy -= 8 * u
        for line in reason:
            p.label(line, tx + 14 * u, yy, 12, WARN)
            yy -= 18 * u
    p.flush()


def dispatch(s, key):
    ops = bpy.ops.anime_sdf_gen
    if key.startswith("PACK:"):
        _, name, route = key.split(":")
        return ops.packing(map_name=name, route=route)
    if key in (
        "RESOLUTION",
        "BIT_DEPTH",
        "SMOOTHING",
        "FILENAME",
        "SOURCE",
        "KEYFRAME_COUNT",
        "POINT",
    ):
        return ops.settings("INVOKE_DEFAULT", section=key)
    if key == "DESTINATION":
        return ops.destination("INVOKE_DEFAULT")
    if key == "DRAFT":
        return ops.save_draft("INVOKE_DEFAULT")
    if key == "CLOSE":
        return ops.close()
    if key == "GENERATE":
        return ops.generate("INVOKE_DEFAULT")
    if key == "CANCEL_GENERATION":
        return ops.cancel_generation()
    if key == "TRANSFORM":
        return ops.transform("INVOKE_DEFAULT")
    if key.startswith("NAV_"):
        return s.editor.navigation.command("AUTHOR", "view_axis", type=key[4:])
    if key == "DISMISS_ERROR":
        s.error = s.seam_warning = ""
        s.redraw()
        return
    if key.startswith("PRESET_"):
        with s.edit(invalidate=False, stages=("FIT",)):
            s.project["preset"] = key[7:]
        return
    if key.startswith("LAYER:"):
        return ops.layer(index=int(key.split(":")[1]))
    if key.startswith("KEYFRAME:"):
        _, direction, index = key.split(":")
        return ops.keyframe(direction=direction, index=int(index))
    if key.startswith("LANDMARK:"):
        return ops.landmark(name=key.split(":")[1])
    if key.startswith("REF_"):
        commands.reference(s, key[4:])
        return
    if key == "FLAT":
        commands.flat(s)
        return
    if key in ("LIT", "SHADOW"):
        commands.operation(s, "REMOVE" if key == "LIT" else "ADD")
        return
    if key in ("SMOOTH", "CORNER", "FREE"):
        commands.handle_mode(s, "AUTO" if key == "SMOOTH" else key)
        return
    return ops.action(action=key)
