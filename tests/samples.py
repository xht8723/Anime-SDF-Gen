"""Reusable synthetic inputs, independent of test cases and Blender."""

import numpy as np
from anime_sdf_gen.core import model


def project(keyframes=5, mirror=True):
    return model.new_project(
        {"object": "test", "fingerprint": "fixture"},
        {
            "center": [0, 0, 0],
            "right": [1, 0, 0],
            "up": [0, 1, 0],
            "forward": [0, 0, 1],
            "width": 1,
            "height": 1,
        },
        keyframes,
        mirror,
    )


def ellipse(name, cx, cy, rx, ry, operation="ADD"):
    k = 0.5522847498307936
    pts = [
        model.point(cx + rx, cy, "FREE", [0, -k * ry], [0, k * ry]),
        model.point(cx, cy + ry, "FREE", [k * rx, 0], [-k * rx, 0]),
        model.point(cx - rx, cy, "FREE", [0, k * ry], [0, -k * ry]),
        model.point(cx, cy - ry, "FREE", [-k * rx, 0], [k * rx, 0]),
    ]
    return {
        "id": model.uid(),
        "name": name,
        "closed": True,
        "operation": operation,
        "enabled": True,
        "points": pts,
    }


def image():
    a = np.random.default_rng(77).random((19, 31, 3))
    a[..., 2] = a[..., 2] > 0.5
    a[0, 0] = [0, 1, 1]
    a[-1, -1] = [1, 0, 0]
    a[0, 1] = [1e-12, 1 - 1e-12, 0]
    a[0, 2] = [0.50000012, 0.50000024, 1]
    return a
