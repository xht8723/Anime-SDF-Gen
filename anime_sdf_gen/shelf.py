"""Bottom sweep timeline and light playback controls."""

from .core import model
from .core.messages import mark, msg, raw
from .i18n import iface, report
from .theme import PANEL, BORDER, MUTED, ACCENT
from .typography import measure
from .viewport import scale


def timeline(s, text, button, bounds):
    e, u = s.editor, scale()
    p = e.painter
    x, y, width, height = bounds.box
    confirm = s.stage == "CONFIRM"
    direction, progress = model.rotation_sample(s.rotation)
    if not confirm:
        inline = width >= 920 * u
        gap = 32 if inline else 0
        text(msg("Shadow keyframes · {count}", count=len(model.sweep(s.project, s.direction))),
             x + 16 * u, y + height - 26 * u, 13)
        items = [
            ("ADD_KEYFRAME", mark("Add keyframe"), 138, len(model.sweep(s.project, s.direction)) < 33),
            ("REMOVE_KEYFRAME", mark("Remove"), 92, 0 < s.key_index < len(model.sweep(s.project, s.direction)) - 1),
            ("COPY_KEYFRAME", mark("Copy previous keyframe"), 206, s.key_index > 0),
            ("MIRROR", mark("Mirror Full Sweep"), 174, True),
        ]
        factor = min(1, (width - (246 if inline else 32) * u) / (628 * u))
        bx = x + (230 if inline else 16) * u
        for key, label, nominal, enabled in items:
            bw = nominal * u * factor
            button(key, label, (bx, y + height - (64 - gap) * u, bw, 28 * u),
                   selected=key == "MIRROR" and s.project["mirror_sweeps"],
                   enabled=enabled and not s.busy, size=12, center=True)
            bx += bw + 6 * u * factor
        text(mark("Boundary movement in front view"), x + 16 * u, y + height - (86 - gap) * u, 11, MUTED)
        label_width = min(180 * u, width * 0.26)
        start_x = x + label_width + 16 * u
        columns = max(2, int((width - label_width - 32 * u) / (48 * u)))
        max_count = max(len(model.sweep(s.project, d)) for d in model.SWEEP_LABELS)
        s.keyframe_scroll = max(0, min(s.keyframe_scroll, max(0, max_count - columns)))
        for row_index, (row_direction, title) in enumerate(model.SWEEP_LABELS.items()):
            frames = model.sweep(s.project, row_direction)
            start = min(s.keyframe_scroll, max(0, len(frames) - columns))
            shown = range(start, min(len(frames), start + columns))
            bw = (x + width - start_x - 16 * u) / len(shown)
            row_y = y + height - (124 - gap + 33 * row_index) * u
            active = (direction if s.orbit_preview else s.direction) == row_direction
            locked = row_direction == model.RTL and s.project["mirror_sweeps"]
            text(title, x + 16 * u, row_y + (14 if locked else 7) * u,
                 13, ACCENT if active else MUTED, label_width - 8 * u)
            if locked:
                text(mark("Mirrored from Left → Right"), x + 16 * u, row_y + u,
                     9, MUTED, label_width - 8 * u)
            nearest = min(range(len(frames)), key=lambda i: abs(frames[i]["progress"] - progress))
            for column, index in enumerate(shown):
                button(f"KEYFRAME:{row_direction}:{index}", str(index + 1),
                       (start_x + column * bw, row_y, bw - 6 * u, 25 * u),
                       selected=row_direction == s.direction and index == s.key_index,
                       enabled=not s.busy and not locked, size=12, center=True)
                if s.orbit_preview and active and index == nearest:
                    p.rectangle(start_x + column * bw + 8 * u, row_y + 2 * u,
                                max(1, bw - 22 * u), 2 * u, ACCENT, u)
    text(msg("Light rotation · {rotation:.0f}°", rotation=s.rotation), x + 16 * u, y + 67 * u, 12, MUTED)
    button("PLAY", mark("Pause") if s.playing else mark("Play 360°"),
           (x + 16 * u, y + 32 * u, 95 * u, 26 * u),
           enabled=not s.busy, size=12, center=True)
    sx, sy, sw, sh = e.boxes["SLIDER"]
    p.rectangle(sx, sy + sh / 2 - u, sw, 2 * u, BORDER, u)
    p.rectangle(sx + s.rotation / 360 * sw - 5 * u, sy + sh / 2 - 5 * u,
                10 * u, 10 * u, ACCENT, 5 * u)
    for fraction, caption in ((0, mark("Front")), (0.25, mark("Character left")),
                              (0.5, mark("Back")), (0.75, mark("Character right")), (1, mark("Front"))):
        tx = sx + fraction * sw
        if fraction == 1:
            tx -= measure(iface(caption), 10)
        text(caption, tx, sy - 13 * u, 10, MUTED, center=0 < fraction < 1)
    if s.busy:
        text(raw(report(s.export.message)), x + 16 * u, y + 7 * u, 11, MUTED, width - 32 * u)


def draw_shelf(s, text, button):
    e, u = s.editor, scale()
    p = e.painter
    shelf = e.boxes["SHELF"]
    p.rectangle(*shelf.box, PANEL)
    p.rectangle(shelf.x, shelf.y + shelf.height - u, shelf.width, u, BORDER)
    timeline(s, text, button, shelf)
    p.flush()
