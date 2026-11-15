"""UV validation, orthographic visibility, and triangle rasterization."""

from .messages import UserError, msg

import numpy as np
from .model import PAD, SPAN
from .thresholds import sample, INTERIOR_MIN, INTERIOR_MAX


def cross2(a, b):
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def area(tris):
    return cross2(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])


def validate_uv(uvs):
    uvs = np.asarray(uvs, dtype=float)
    if uvs.ndim != 3 or uvs.shape[1:] != (3, 2) or not np.isfinite(uvs).all():
        raise UserError("The bake UV map contains invalid coordinates.")


def triangle_pixels(tri, size):
    """Yield row-bounded pixel batches and barycentric weights; UV origin bottom left."""
    den = float(cross2(tri[1] - tri[0], tri[2] - tri[0]))
    if abs(den) < 1e-14:
        return
    lo = np.ceil(tri.min(axis=0) * size - 0.5).clip(0, size).astype(int)
    hi = (np.floor(tri.max(axis=0) * size - 0.5) + 1).clip(0, size).astype(int)
    if np.any(hi <= lo):
        return
    for row in range(lo[1], hi[1], 32):
        xx, yy = np.meshgrid(np.arange(lo[0], hi[0]), np.arange(row, min(row + 32, hi[1])))
        p = np.stack([(xx + 0.5) / size, (yy + 0.5) / size], axis=-1)
        b = cross2(p - tri[0], tri[2] - tri[0]) / den
        c = cross2(tri[1] - tri[0], p - tri[0]) / den
        a = 1 - b - c
        inside = (a >= -1e-8) & (b >= -1e-8) & (c >= -1e-8)
        if np.any(inside):
            yield yy[inside], xx[inside], np.stack([a[inside], b[inside], c[inside]], axis=-1)


def projection_steps(projected, size, *, front_only=False):
    depth = np.full((size, size), -np.inf, dtype=np.float32)
    facing = area(projected[..., :2]) > 1e-10
    for i, tri in enumerate(projected):
        if not front_only or facing[i]:
            for y, x, weights in triangle_pixels((tri[:, :2] + PAD) / SPAN, size):
                z = weights @ tri[:, 2]
                depth[y, x] = np.maximum(depth[y, x], z)
            if not front_only and abs(area(tri[None, :, :2])[0]) < 1e-14:
                # Edge-on/point projections still receive UV samples. Include
                # their bilinear sample footprint in the authoring domain.
                for a, b in zip(tri, np.roll(tri, -1, axis=0)):
                    count = max(1, int(np.ceil(np.max(np.abs(b[:2] - a[:2])) * size / SPAN * 2)))
                    points = a + np.linspace(0, 1, count + 1)[:, None] * (b - a)
                    xy = np.floor((points[:, :2] + PAD) * size / SPAN - 0.5).astype(int)
                    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                        x, y = (xy + (dx, dy)).clip(0, size - 1).T
                        np.maximum.at(depth, (y, x), points[:, 2])
        if i % 64 == 0:
            yield msg("Projection coverage"), i / max(1, len(projected))
    return depth, facing


def visible(depth, coords, tolerance):
    # Nearest depth avoids interpolation with uncovered (-inf) pixels.
    xy = np.floor((coords[:, :2] + PAD) * len(depth) / SPAN).astype(int).clip(0, len(depth) - 1)
    z = depth[xy[:, 1], xy[:, 0]]
    return np.isfinite(z) & (coords[:, 2] >= z - tolerance)


def bake_steps(thresholds, uvs, projected, depth, facing, size, *, front_only=False):
    output = np.ones((size, size, 3), dtype=np.float32)
    output[..., 2] = 0
    tolerance = 3 * SPAN / len(depth)
    for i, tri in enumerate(uvs):
        if not front_only or facing[i]:
            for y, x, weights in triangle_pixels(tri, size):
                coords = weights @ projected[i]
                valid = visible(depth, coords, tolerance) if front_only else np.ones(len(coords), bool)
                if np.any(valid):
                    yy, xx = y[valid], x[valid]
                    values = sample(thresholds, coords[valid, :2])
                    interior = (values > 0) & (values < 1)
                    # A float64 bilinear mixture next to an endpoint can round
                    # to that sentinel on assignment to the float32 bake.
                    values[interior] = values[interior].clip(INTERIOR_MIN, INTERIOR_MAX)
                    output[yy, xx, :2] = values
                    output[yy, xx, 2] = 1
        if i % 64 == 0:
            yield msg("Transfer to UV map"), i / max(1, len(uvs))
    return output


def pad_steps(image, radius):
    """Nearest-seed dilation; B remains the original face coverage, without a halo."""
    valid = image[..., 2] > 0.5
    sy, sx = np.indices(valid.shape, dtype=np.int32)
    seed_x, seed_y = np.where(valid, sx, -1), np.where(valid, sy, -1)
    best = np.where(valid, 0, radius * radius + 1).astype(np.int32)
    # Each pass grows one Chebyshev step. Euclidean distances decide ownership.
    for step in range(radius):
        old_x, old_y = seed_x.copy(), seed_y.copy()
        for dy, dx in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
            tx, ty = np.roll(old_x, (dy, dx), (0, 1)), np.roll(old_y, (dy, dx), (0, 1))
            possible = tx >= 0
            if dy < 0:
                possible[dy:] = False
            if dy > 0:
                possible[:dy] = False
            if dx < 0:
                possible[:, dx:] = False
            if dx > 0:
                possible[:, :dx] = False
            dist = (sx - tx) ** 2 + (sy - ty) ** 2
            improve = possible & (dist < best) & (dist <= radius * radius)
            seed_x[improve], seed_y[improve], best[improve] = (
                tx[improve],
                ty[improve],
                dist[improve],
            )
            yield msg("UV island padding"), (step + ((dy + 1) * 3 + dx + 1) / 9) / max(1, radius)
    use = ~valid & (seed_x >= 0)
    image[use, :2] = image[seed_y[use], seed_x[use], :2]
    return image
