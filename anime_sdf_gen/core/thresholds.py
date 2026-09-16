"""Threshold conventions, decoding, and padded head-space sampling."""

import numpy as np
from .model import PAD, SPAN

INTERIOR_MIN = np.nextafter(np.float32(0), np.float32(1))
INTERIOR_MAX = np.nextafter(np.float32(1), np.float32(0))


def decode(threshold, progress):
    return (threshold == 0) | ((threshold < 1) & (float(progress) >= threshold))


def endpoint_seams(thresholds, domain):
    """Counts of visible front/back discontinuities between authored maps."""
    return {
        name: int(
            np.count_nonzero(
                (decode(thresholds[..., 0], progress) != decode(thresholds[..., 1], progress))
                & domain
            )
        )
        for name, progress in (("Front", 0), ("Back", 1))
    }


def sample(array, uv):
    """Bilinear lookup in face coordinates (0..1), including the padded canvas."""
    size = array.shape[0]
    pos = (np.asarray(uv) + PAD) * size / SPAN - 0.5
    pos = np.clip(pos, 0, size - 1)
    lo = np.floor(pos).astype(np.int32)
    hi = np.minimum(lo + 1, size - 1)
    frac = pos - lo
    x, y = lo[..., 0], lo[..., 1]
    xx, yy = hi[..., 0], hi[..., 1]
    fx, fy = frac[..., 0], frac[..., 1]
    if array.ndim == 3:
        fx, fy = fx[..., None], fy[..., None]
    return (array[y, x] * (1 - fx) + array[y, xx] * fx) * (1 - fy) + (
        array[yy, x] * (1 - fx) + array[yy, xx] * fx
    ) * fy
