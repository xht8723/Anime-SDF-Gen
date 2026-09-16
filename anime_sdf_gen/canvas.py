"""Shared head-plane picking, projection, and overlay drawing primitives."""

import math
import json
from functools import lru_cache
import blf
import gpu
import numpy as np
from mathutils import Vector
from gpu_extras.batch import batch_for_shader
from . import source
from .viewport import scale
from .core import curves


def label(text, x, y, size=12, color=(0.87, 0.90, 0.95, 1)):
    blf.size(0, size * scale())
    blf.color(0, *color)
    blf.position(0, x, y, 0)
    blf.draw(0, text)


def lines(coords, color, width=1, mode="LINE_STRIP"):
    if len(coords) < 2 or any(p is None for p in coords):
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    shader.bind()
    shader.uniform_float("color", color)
    gpu.state.line_width_set(width * scale())
    batch_for_shader(shader, mode, {"pos": coords}).draw(shader)


def disc(x, y, radius, color):
    radius *= scale()
    coords = [(x, y)] + [
        (x + radius * math.cos(i * 2 * math.pi / 20), y + radius * math.sin(i * 2 * math.pi / 20))
        for i in range(21)
    ]
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    shader.bind()
    shader.uniform_float("color", color)
    batch_for_shader(
        shader, "TRIS", {"pos": coords}, indices=[(0, i, i + 1) for i in range(1, 21)]
    ).draw(shader)


def rect(x, y, w, h, color):
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    shader.bind()
    shader.uniform_float("color", color)
    batch_for_shader(
        shader, "TRI_FAN", {"pos": [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]}
    ).draw(shader)


def to_view(s, xy, view):
    return view.project(source.world_point(s.project["alignment"], xy, 0))


def from_view(s, xy, view):
    origin, direction = view.ray(xy)
    a = s.project["alignment"]
    normal = Vector(a["forward"])
    denom = direction.dot(normal)
    if abs(denom) < 1e-8:
        return None
    hit = origin + direction * ((Vector(a["center"]) - origin).dot(normal) / denom)
    delta = hit - Vector(a["center"])
    return np.array(
        [
            delta.dot(Vector(a["right"])) / a["width"] + 0.5,
            delta.dot(Vector(a["up"])) / a["height"] + 0.5,
        ]
    )


@lru_cache(maxsize=64)
def flat_contour(serialized):
    c = json.loads(serialized)
    points = curves.flatten(c, 0.0007)
    return np.vstack([points, points[0]]) if c["closed"] else points


def project_points(s, points, region, view):
    a = s.project["alignment"]
    world = (
        np.asarray(a["center"])
        + (points[:, 0, None] - 0.5) * a["width"] * np.asarray(a["right"])
        + (points[:, 1, None] - 0.5) * a["height"] * np.asarray(a["up"])
    )
    clip = np.column_stack([world, np.ones(len(world))]) @ np.asarray(view.perspective_matrix).T
    if np.any(clip[:, 3] <= 0):
        return []
    # GPU vertex buffers consume float32. A float64 NumPy buffer can be accepted
    # without an exception yet draw corrupted coordinates on some backends.
    return np.asarray(
        (clip[:, :2] / clip[:, 3, None] + 1) * np.array([region.width, region.height]) / 2,
        dtype=np.float32,
    )


def contour_lines(s, c, region, view, color, width=1):
    points = flat_contour(json.dumps(c, sort_keys=True))
    lines(project_points(s, points, region, view), color, width)


def pick(s, mouse, view):
    candidates = []
    if s.stage == "FIT":
        for name, anchor in s.project["authoring"]["anchors"].items():
            q = view.project(anchor["world"])
            if q is not None:
                candidates.append((np.linalg.norm(np.array(q) - mouse), ("landmark", name)))
    else:
        for ci, c in enumerate(s.keyframe["contours"]):
            if not c.get("enabled", True):
                continue
            for pi, p in enumerate(c["points"]):
                q = to_view(s, p["co"], view)
                if q is not None:
                    candidates.append((np.linalg.norm(np.array(q) - mouse), ("co", ci, pi)))
                if ci == s.contour and pi == s.point and (ci, pi) in s.selected:
                    for kind, h in zip(("left", "right"), curves.handles(c, pi)):
                        q = to_view(s, h, view)
                        if q is not None:
                            candidates.append((np.linalg.norm(np.array(q) - mouse), (kind, ci, pi)))
    if not candidates:
        return None
    distance, item = min(candidates, key=lambda p: p[0])
    return item if distance <= 12 * scale() else None


def inside(point, box):
    x, y, w, h = box
    return x <= point[0] <= x + w and y <= point[1] <= y + h
