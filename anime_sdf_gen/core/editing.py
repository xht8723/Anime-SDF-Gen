"""Selection and affine edits on the fixed face plane; no Blender dependencies."""

from .messages import UserError, msg, Joined, mark

from copy import deepcopy
import math
import numpy as np
from .curves import handles


def available(frame):
    return {
        (ci, pi)
        for ci, c in enumerate(frame["contours"])
        if c.get("enabled", True)
        for pi in range(len(c["points"]))
    }


def box_selection(projected, start, end):
    low, high = np.minimum(start, end), np.maximum(start, end)
    return {
        key
        for key, xy in projected.items()
        if xy is not None and np.all(np.asarray(xy) >= low) and np.all(np.asarray(xy) <= high)
    }


def combine_selection(selected, hits, operation):
    return (
        selected | hits
        if operation == "ADD"
        else selected - hits if operation == "SUB" else set(hits)
    )


def affine(frame, selected, matrix, delta, pivot, handle="co"):
    """Apply a face-plane affine transform with one validation path."""
    result = deepcopy(frame)
    for ci, pi in selected:
        old = frame["contours"][ci]["points"][pi]
        pt = result["contours"][ci]["points"][pi]
        co = np.asarray(old["co"])
        offset = delta
        if handle == "co":
            pt["co"] = (pivot + matrix @ (co - pivot) + offset).tolist()
            for side in ("left", "right"):
                pt[side] = (matrix @ np.asarray(old[side])).tolist()
        else:
            left, right = handles(frame["contours"][ci], pi)
            pt.update(mode="FREE", left=(left - co).tolist(), right=(right - co).tolist())
            pt[handle] = (matrix @ np.asarray(pt[handle]) + offset).tolist()
        if any(
            not math.isfinite(v) or abs(v) > 100 for key in ("co", "left", "right") for v in pt[key]
        ):
            raise UserError("Curve coordinates must be finite and within ±100 face units.")
    return result


def transform_contour(contour, dx=0, dy=0, angle=0, scale=1, aspect=1):
    """Numeric closed-shape transform using the same physical metric as shortcuts."""
    if not contour["closed"]:
        raise UserError("Shape transforms apply to closed shapes.")
    if dx == 0 and dy == 0 and angle == 0 and scale == 1:
        return
    metric = np.array([1.0, float(aspect)])
    radians = math.radians(angle)
    c, s = math.cos(radians), math.sin(radians)
    matrix = scale * np.array([[c, -s], [s, c]]) * metric[None, :] / metric[:, None]
    selected = {(0, i) for i in range(len(contour["points"]))}
    pivot = np.mean([p["co"] for p in contour["points"]], axis=0)
    result = affine({"contours": [contour]}, selected, matrix, np.array([dx, dy]), pivot)[
        "contours"
    ][0]
    contour.clear()
    contour.update(result)


class Transform:
    """Always evaluate from the captured artwork, avoiding accumulated drift."""

    def __init__(self, frame, selected, kind, mouse, aspect=1.0, handle="co"):
        self.selected = set(selected) & available(frame)
        if not self.selected:
            raise UserError("Select curve points first.")
        self.original = deepcopy(frame)
        self.kind = kind
        self.axis = None
        self.number = ""
        self.handle = handle
        self.metric = np.array([1.0, float(aspect)])
        self.coords = np.array(
            [frame["contours"][ci]["points"][pi]["co"] for ci, pi in sorted(self.selected)]
        )
        self.pivot = self.coords.mean(axis=0)
        self.last = np.asarray(mouse, dtype=float) * self.metric
        self.delta = np.zeros(2)
        self.angle = 0.0
        self.factor = 1.0
        self.base_distance = max(np.linalg.norm(self.last - self.pivot * self.metric), 0.05)

    def move(self, mouse, precise=False):
        current = np.asarray(mouse, dtype=float) * self.metric
        precision = 0.1 if precise else 1.0
        self.delta += (current - self.last) * precision
        center = self.pivot * self.metric
        old, new = self.last - center, current - center
        if np.linalg.norm(old) > 1e-9 and np.linalg.norm(new) > 1e-9:
            self.angle += (
                math.atan2(old[0] * new[1] - old[1] * new[0], float(old @ new)) * precision
            )
        self.factor += (np.linalg.norm(new) - np.linalg.norm(old)) / self.base_distance * precision
        self.last = current

    def numeric(self, character):
        if character == "BACK_SPACE":
            self.number = self.number[:-1]
        elif character == "-":
            self.number = self.number[1:] if self.number.startswith("-") else "-" + self.number
        elif character == ".":
            if "." not in self.number:
                self.number += "."
        elif character.isdigit() and len(character) == 1 and len(self.number) < 24:
            self.number += character

    def values(self, snap=False, precise=False):
        typed = None
        if self.number:
            try:
                typed = float(self.number)
            except ValueError:
                typed = 0.0 if self.kind != "SCALE" else 1.0
        delta = self.delta / self.metric
        angle = self.angle
        factor = self.factor
        if self.kind == "MOVE":
            if self.axis in ("X", "Y", "Z"):
                component = 0 if self.axis == "X" else 1
                delta = (
                    np.array([delta[0], 0.0])
                    if self.axis == "X"
                    else np.array([0.0, delta[1]]) if self.axis == "Y" else np.zeros(2)
                )
                if typed is not None and self.axis != "Z":
                    delta[component] = typed
            elif typed is not None:
                length = np.linalg.norm(self.delta)
                direction = self.delta / length if length > 1e-9 else np.array([1.0, 0.0])
                delta = direction * typed / self.metric
            if snap and typed is None:
                step = 0.001 if precise else 0.01
                delta = np.round(delta / step) * step
        elif self.kind == "ROTATE":
            if typed is not None:
                angle = math.radians(typed)
            elif snap:
                angle = math.radians(
                    round(math.degrees(angle) / (1 if precise else 5)) * (1 if precise else 5)
                )
            if self.axis in ("X", "Y"):
                angle = 0.0
        else:
            if typed is not None:
                factor = typed
            elif snap:
                step = 0.01 if precise else 0.1
                factor = round(factor / step) * step
        return delta, angle, factor

    def evaluate(self, snap=False, precise=False):
        delta, angle, factor = self.values(snap, precise)
        if (
            (self.kind == "MOVE" and not delta.any())
            or (self.kind == "ROTATE" and angle == 0)
            or (self.kind == "SCALE" and (factor == 1 or self.axis == "Z"))
        ):
            return deepcopy(self.original)
        matrix = np.eye(2)
        if self.kind == "ROTATE":
            c, s = math.cos(angle), math.sin(angle)
            matrix = np.array([[c, -s], [s, c]])
        elif self.kind == "SCALE":
            factors = [
                factor if self.axis in (None, "X") else 1.0,
                factor if self.axis in (None, "Y") else 1.0,
            ]
            matrix = np.diag(factors)
        matrix = matrix * self.metric[None, :] / self.metric[:, None]
        return affine(
            self.original,
            self.selected,
            matrix,
            delta if self.kind == "MOVE" else np.zeros(2),
            self.pivot,
            self.handle,
        )

    def caption(self, snap=False, precise=False):
        delta, angle, factor = self.values(snap, precise)
        value = (
            f"X {delta[0]:+.4f}   Y {delta[1]:+.4f}"
            if self.kind == "MOVE"
            else f"{math.degrees(angle):+.2f}°" if self.kind == "ROTATE" else f"{factor:.4f}"
        )
        kind = {"MOVE": mark("Move"), "ROTATE": mark("Rotate"), "SCALE": mark("Scale")}[self.kind]
        return Joined(
            (
                msg(kind),
                " · " + self.axis if self.axis else "",
                "  ",
                value,
                "  [" + self.number + "]" if self.number else "",
                msg(" · Snap") if snap else "",
            ),
            separator="",
        )
