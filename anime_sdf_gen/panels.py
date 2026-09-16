"""Step-specific sidebar controls; layout remains in popup coordinates."""

from pathlib import Path
import bpy
from .core import model
from .core.model import MAP_LABELS, OUTPUT_ROUTES
from .core.files import output_layout
from .theme import TEXT, MUTED, BORDER, ACCENT
from .typography import wrap
from .i18n import iface
from .core.messages import mark, msg, raw, contour_label


class Sidebar:
    def __init__(self, session, text, button, painter, editor, x, width, unit, y):
        self.s = session
        self.text = text
        self.button = button
        self.painter = painter
        self.editor = editor
        self.x = x
        self.width = width
        self.unit = unit
        self.y = y

    def heading(self, value):
        self.text(value, self.x, self.y, 12, MUTED, self.width)
        self.y -= 19 * self.unit

    def row(self, items):
        width = (self.width - 6 * self.unit * (len(items) - 1)) / len(items)
        for i, item in enumerate(items):
            key, value, *options = item
            selected = options[0] if options else False
            enabled = options[1] if len(options) > 1 else True
            self.button(
                key,
                value,
                (
                    self.x + i * (width + 6 * self.unit),
                    self.y - 31 * self.unit,
                    width,
                    32 * self.unit,
                ),
                selected,
                enabled and not self.s.busy,
            )
        self.y -= 39 * self.unit

    def confirm(self):
        s = self.s
        text = self.text
        button = self.button
        p = self.painter
        e = self.editor
        x = self.x
        cw = self.width
        u = self.unit
        heading = self.heading
        row = self.row
        destination = Path(bpy.path.abspath(s.project["settings"]["output"]))
        heading(mark("Save location"))
        row([("DESTINATION", raw(destination.parent))])
        self.y -= 10 * u
        heading(mark("File name"))
        row([("FILENAME", raw(destination.name))])
        self.y -= 10 * u
        heading(mark("Texture resolution"))
        resolution = s.project["settings"]["resolution"]
        row([("RESOLUTION", f"{resolution} × {resolution}")])
        self.y -= 15 * u
        heading(mark("Output precision"))
        row([("BIT_DEPTH", model.BIT_DEPTH_LABELS[s.project["settings"]["bit_depth"]])])
        self.y -= 10 * u
        heading(mark("Smoothing"))
        amount = s.project["settings"]["smoothing"]
        track_width = cw - 84 * u
        button(
            "SMOOTHING_SLIDER", "", (x, self.y - 31 * u, track_width, 32 * u), enabled=not s.busy
        )
        tx, ty, tw = x + 12 * u, self.y - 15 * u, max(1, track_width - 24 * u)
        e.boxes["SMOOTHING_TRACK"] = (tx, ty, tw, 1)
        p.rectangle(tx, ty - u, tw, 2 * u, BORDER, u)
        p.rectangle(tx, ty - u, tw * amount / 8, 2 * u, ACCENT, u)
        p.rectangle(tx + tw * amount / 8 - 4 * u, ty - 4 * u, 8 * u, 8 * u, ACCENT, 4 * u)
        button(
            "SMOOTHING",
            mark("Off") if amount == 0 else f"{amount:.2f}",
            (x + cw - 76 * u, self.y - 31 * u, 76 * u, 32 * u),
            enabled=not s.busy,
            center=True,
        )
        self.y -= 54 * u
        heading(mark("Output packing"))
        for name, label in MAP_LABELS.items():
            text(label, x, self.y, 13)
            self.y -= 19 * u
            for i, route in enumerate(OUTPUT_ROUTES):
                width = 44 * u if i < 3 else cw - 150 * u
                button(
                    f"PACK:{name}:{route}",
                    mark("Separate") if route == "SEPARATE" else route,
                    (x + i * 50 * u, self.y - 31 * u, width, 32 * u),
                    selected=s.project["settings"]["packing"][name] == route,
                    enabled=not s.busy,
                    size=12,
                    center=True,
                )
            self.y -= 49 * u
        self.y -= 5 * u
        heading(mark("Files to generate"))
        textures, sidecar = output_layout(s.project, destination)
        for texture in textures:
            for line in wrap(texture["path"].name, cw, 12):
                text(raw(line), x, self.y, 12, TEXT)
                self.y -= 18 * u
            mapping = " · ".join(
                (iface("Gray") if channel == "Y" else channel) + ": " + iface(MAP_LABELS[name])
                for channel, name in texture["channels"].items()
            )
            for line in wrap(mapping, cw, 11):
                text(line, x, self.y, 11, MUTED)
                self.y -= 17 * u
            self.y -= 8 * u
        for line in wrap(sidecar.name, cw, 12):
            text(raw(line), x, self.y, 12, TEXT)
            self.y -= 18 * u
        self.y -= 24 * u
        row([("FRAME", mark("Frame face"))])

    def setup(self):
        s = self.s
        text = self.text
        button = self.button
        p = self.painter
        e = self.editor
        x = self.x
        cw = self.width
        u = self.unit
        heading = self.heading
        row = self.row
        heading(mark("Keyframes per sweep"))
        count = s.project["authoring"]["keyframe_count"]
        square = 32 * u
        gap = 8 * u
        button(
            "KEYFRAMES_LESS",
            "",
            (x, self.y - 31 * u, square, 32 * u),
            enabled=count > 2 and not s.busy,
            icon_name="MINUS",
        )
        button(
            "KEYFRAME_COUNT",
            str(count),
            (x + square + gap, self.y - 31 * u, cw - 2 * (square + gap), 32 * u),
            enabled=not s.busy,
            size=16,
            center=True,
        )
        button(
            "KEYFRAMES_MORE",
            "",
            (x + cw - square, self.y - 31 * u, square, 32 * u),
            enabled=count < 33 and not s.busy,
            icon_name="PLUS",
        )
        self.y -= 49 * u

    def fitting(self):
        s = self.s
        text = self.text
        button = self.button
        p = self.painter
        e = self.editor
        x = self.x
        cw = self.width
        u = self.unit
        heading = self.heading
        row = self.row
        heading(mark("Fitting markers"))
        for name, value in (
            ("nose", mark("Nose")),
            ("mouth", mark("Mouth Center")),
            ("chin", mark("Chin")),
        ):
            row([("LANDMARK:" + name, value, s.landmark == name)])
        self.y -= 10 * u
        heading(mark("Starting preset"))
        row(
            [
                ("PRESET_CLEAN", mark("Clean Face"), s.project["preset"] == "CLEAN"),
                ("PRESET_NOSE", mark("Nose Accent"), s.project["preset"] == "NOSE"),
            ]
        )
        row([("MIRROR", mark("Mirror Full Sweep"), s.project["mirror_sweeps"])])
        self.y -= 10 * u

    def reference(self):
        s = self.s
        text = self.text
        button = self.button
        p = self.painter
        e = self.editor
        x = self.x
        cw = self.width
        u = self.unit
        heading = self.heading
        row = self.row
        heading(mark("Reference & view"))
        ref = s.project["authoring"]["reference"]
        row(
            [
                ("REF_NEUTRAL", mark("Neutral"), ref == "NEUTRAL"),
                ("REF_MATERIAL", mark("Materials"), ref == "MATERIAL"),
            ]
        )
        row([("FRAME", mark("Frame face")), ("SOURCE", mark("Source / UV…"))])

    def navigation(self):
        s = self.s
        text = self.text
        button = self.button
        p = self.painter
        e = self.editor
        x = self.x
        cw = self.width
        u = self.unit
        heading = self.heading
        row = self.row
        row([("NAV_FRONT", mark("Front")), ("NAV_RIGHT", mark("Right")), ("NAV_TOP", mark("Top"))])

    def edit(self):
        s = self.s
        text = self.text
        button = self.button
        p = self.painter
        e = self.editor
        x = self.x
        cw = self.width
        u = self.unit
        heading = self.heading
        row = self.row
        self.y -= 10 * u
        heading(msg("Shadow keyframes · {count}", count=len(model.sweep(s.project, s.direction))))
        row(
            [
                (
                    "ADD_KEYFRAME",
                    mark("Add keyframe"),
                    False,
                    len(model.sweep(s.project, s.direction)) < 33,
                ),
                (
                    "REMOVE_KEYFRAME",
                    mark("Remove"),
                    False,
                    0 < s.key_index < len(model.sweep(s.project, s.direction)) - 1,
                ),
            ]
        )
        row([("COPY_KEYFRAME", mark("Copy previous keyframe"), False, s.key_index > 0)])
        row([("MIRROR", mark("Mirror Full Sweep"), s.project["mirror_sweeps"])])
        self.y -= 10 * u
        heading(mark("Contours"))
        for index, c in enumerate(s.keyframe["contours"]):
            sign = "+" if c["operation"] == "ADD" else "−"
            row(
                [
                    (
                        "LAYER:" + str(index),
                        raw(
                            ("· " if not c.get("enabled", True) else "")
                            + sign
                            + "  "
                            + iface(contour_label(c["name"]))
                        ),
                        index == s.contour,
                    )
                ]
            )
        row([("TRIANGLE", mark("+  Add triangle"))])
        if s.curve["closed"]:
            row(
                [
                    ("LIT", mark("Lit area"), s.curve["operation"] == "REMOVE"),
                    ("SHADOW", mark("Shadow area"), s.curve["operation"] == "ADD"),
                ]
            )
            row([("DUPLICATE", mark("Duplicate")), ("DELETE_SHAPE", mark("Delete"))])
            row(
                [
                    ("UP", mark("Up"), False, s.contour > 1),
                    ("DOWN", mark("Down"), False, s.contour < len(s.keyframe["contours"]) - 1),
                    ("TOGGLE", mark("Hide") if s.curve.get("enabled", True) else mark("Show")),
                ]
            )
            row([("TRANSFORM", mark("Move / Rotate / Scale…"))])
        self.y -= 10 * u
        heading(msg("Point {index}", index=s.point + 1))
        point = s.curve["points"][s.point]
        row([("POINT", f"X {point['co'][0]:.4f}   Y {point['co'][1]:.4f}…")])
        row(
            [
                ("SMOOTH", mark("Smooth"), point["mode"] == "AUTO"),
                ("CORNER", mark("Corner"), point["mode"] == "CORNER"),
                ("FREE", mark("Free"), point["mode"] == "FREE"),
            ]
        )
        removable = len(s.curve["points"]) > (3 if s.curve["closed"] else 2) and (
            s.curve["closed"] or s.point not in (0, len(s.curve["points"]) - 1)
        )
        row([("INSERT_POINT", mark("Insert")), ("DELETE_POINT", mark("Remove"), False, removable)])
