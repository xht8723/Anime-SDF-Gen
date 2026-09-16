"""GPU assertions shared by real popup tests."""

import numpy as np
from tests.ui_helpers import redraw
from anime_sdf_gen import session


def pixels():
    redraw()
    b = session.ACTIVE.editor.buffers["PREVIEW"]
    a = np.asarray(b.texture_color.read(), dtype=float).reshape(b.height, b.width, 4)[..., :3]
    return a / 255 if a.max() > 1 else a


def appearance(flat=False):
    """Classify independent brightness ranges; never infer coverage from normals."""
    a = pixels()
    background = np.max(np.abs(a - [0.055, 0.065, 0.083]), axis=2) < 0.006
    uncovered = np.max(np.abs(a - [0.12] * 3), axis=2) < 0.006
    valid = ~(background | uncovered)
    luminance = a @ np.array([0.2126, 0.7152, 0.0722])
    lit = valid & (luminance > 0.25)
    shadow = valid & ~lit
    if flat:
        assert np.all(np.abs(a[lit] - 1) < 0.006)
        assert np.all(np.abs(a[shadow]) < 0.006)
    else:
        assert np.all((luminance[lit] > 0.30) & (luminance[lit] < 0.71))
        assert np.all((luminance[shadow] > 0.085) & (luminance[shadow] < 0.22))
    return a, lit, shadow
