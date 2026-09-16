"""Exact separable squared Euclidean distance transform, vectorized across rows.

The lower-envelope algorithm follows Felzenszwalb and Huttenlocher (2012).
Generator checkpoints bound the amount of work between UI timer callbacks.
"""

from .messages import UserError, msg

import numpy as np
from .jobs import run


def _rows_steps(f, label):
    rows, n = f.shape
    v = np.zeros((rows, n), dtype=np.int32)
    z = np.empty((rows, n + 1), dtype=np.float64)
    z[:, 0], z[:, 1:] = -np.inf, np.inf
    k = np.zeros(rows, dtype=np.int32)
    rr = np.arange(rows)
    for q in range(1, n):
        vk = v[rr, k]
        s = ((f[:, q] + q * q) - (f[rr, vk] + vk.astype(float) ** 2)) / (2 * (q - vk))
        pop = s <= z[rr, k]
        while np.any(pop):
            k[pop] -= 1
            r = rr[pop]
            vk2 = v[r, k[pop]]
            s[pop] = ((f[r, q] + q * q) - (f[r, vk2] + vk2.astype(float) ** 2)) / (2 * (q - vk2))
            pop = s <= z[rr, k]
        k += 1
        v[rr, k], z[rr, k], z[rr, k + 1] = q, s, np.inf
        if q % 32 == 0:
            yield label, q / (2 * n)
    k.fill(0)
    result = np.empty_like(f)
    for q in range(n):
        advance = z[rr, k + 1] < q
        while np.any(advance):
            k[advance] += 1
            advance = z[rr, k + 1] < q
        vk = v[rr, k]
        result[:, q] = (q - vk).astype(float) ** 2 + f[rr, vk]
        if q % 32 == 0:
            yield label, 0.5 + q / (2 * n)
    return result


def squared_steps(features):
    features = np.asarray(features, dtype=bool)
    if features.ndim != 2:
        raise UserError("The distance transform requires a 2D mask.")
    h, w = features.shape
    infinity = float(h * h + w * w) * 4
    if not features.any():
        return np.full((h, w), infinity)
    f = np.where(features, 0.0, infinity)
    f = yield from _rows_steps(f, msg("Distance: rows"))
    f = yield from _rows_steps(f.T.copy(), msg("Distance: columns"))
    return f.T.copy()


def signed_steps(mask):
    """Positive inside shadow; finite diagonal sentinels for empty/full masks."""
    mask = np.asarray(mask, dtype=bool)
    diagonal = float(np.hypot(*mask.shape))
    if not mask.any():
        return np.full(mask.shape, -diagonal, dtype=np.float32)
    if mask.all():
        return np.full(mask.shape, diagonal, dtype=np.float32)
    outside = yield from squared_steps(~mask)
    inside = yield from squared_steps(mask)
    return (np.sqrt(outside) - np.sqrt(inside)).astype(np.float32)


def signed(mask):
    return run(signed_steps(mask))
