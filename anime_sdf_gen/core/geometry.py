"""UV validation, orthographic visibility, and triangle rasterization."""
import numpy as np
from .model import PAD, SPAN
from .compile import sample


def cross2(a, b):
    return a[..., 0]*b[..., 1]-a[..., 1]*b[..., 0]


def area(tris):
    return cross2(tris[:, 1]-tris[:, 0], tris[:, 2]-tris[:, 0])


def _intersection_area(a, b):
    poly = list(a)
    sign = 1 if cross2(b[1]-b[0], b[2]-b[0]) > 0 else -1
    for j in range(3):
        edge0, edge1 = b[j], b[(j+1) % 3]
        out = []
        if not poly:
            return 0.
        prev = poly[-1]
        pd = float(cross2(edge1-edge0, prev-edge0))*sign
        for cur in poly:
            cd = float(cross2(edge1-edge0, cur-edge0))*sign
            if (cd >= 0) != (pd >= 0):
                out.append(prev + (cur-prev)*(pd/(pd-cd)))
            if cd >= 0:
                out.append(cur)
            prev, pd = cur, cd
        poly = out
    if len(poly) < 3:
        return 0.
    p = np.asarray(poly)
    return abs(float(np.sum(cross2(p, np.roll(p, -1, axis=0)))))*.5


def validate_uv(uvs, positions=None):
    uvs = np.asarray(uvs, dtype=float)
    if not len(uvs) or not np.isfinite(uvs).all():
        raise ValueError("The face has no finite UV triangles.")
    if uvs.min() < -1e-6 or uvs.max() > 1+1e-6:
        raise ValueError("V1 requires the selected face UVs inside a single 0–1 tile.")
    bad = np.flatnonzero(np.abs(area(uvs)) < 1e-12)
    if len(bad):
        raise ValueError(f"{len(bad)} face triangles have zero-area UVs (first triangle {int(bad[0])}).")
    if positions is not None:
        physical = np.linalg.norm(np.cross(positions[:, 1]-positions[:, 0], positions[:, 2]-positions[:, 0]), axis=1)
        extent=float(np.max(np.ptp(positions.reshape(-1,3),axis=0)))
        if extent==0 or np.any(physical <= extent*extent*1e-14):
            raise ValueError("The selected region contains degenerate mesh triangles.")
    lo, hi = uvs.min(axis=1), uvs.max(axis=1)
    bins, tested = {}, set()
    for i in range(len(uvs)):
        low, high = np.floor(lo[i]*64).astype(int).clip(0, 63), np.floor(hi[i]*64).astype(int).clip(0, 63)
        candidates = set()
        for y in range(low[1], high[1]+1):
            for x in range(low[0], high[0]+1):
                candidates.update(bins.get((x, y), ()))
        for j in candidates:
            if (j, i) in tested:
                continue
            tested.add((j, i))
            if np.any(np.minimum(hi[i], hi[j])-np.maximum(lo[i], lo[j]) <= 1e-10):
                continue
            if _intersection_area(uvs[i], uvs[j]) > 1e-12:
                raise ValueError(f"Overlapping face UV triangles {j} and {i}. Choose a unique face UV map; shadow symmetry does not resolve shared texels.")
        for y in range(low[1], high[1]+1):
            for x in range(low[0], high[0]+1):
                bins.setdefault((x, y), []).append(i)


def triangle_pixels(tri, size):
    """Yield row-bounded pixel batches and barycentric weights; UV origin bottom left."""
    den = float(cross2(tri[1]-tri[0], tri[2]-tri[0]))
    if abs(den) < 1e-14:
        return
    lo = np.ceil(tri.min(axis=0)*size-.5).astype(int).clip(0, size)
    hi = (np.floor(tri.max(axis=0)*size-.5).astype(int)+1).clip(0, size)
    if np.any(hi <= lo):
        return
    for row in range(lo[1], hi[1], 32):
        xx, yy = np.meshgrid(np.arange(lo[0], hi[0]), np.arange(row, min(row+32, hi[1])))
        p = np.stack([(xx+.5)/size, (yy+.5)/size], axis=-1)
        b = cross2(p-tri[0], tri[2]-tri[0])/den
        c = cross2(tri[1]-tri[0], p-tri[0])/den
        a = 1-b-c
        inside = (a >= -1e-8) & (b >= -1e-8) & (c >= -1e-8)
        if np.any(inside):
            yield yy[inside], xx[inside], np.stack([a[inside], b[inside], c[inside]], axis=-1)


def projection_steps(projected, size):
    depth = np.full((size, size), -np.inf, dtype=np.float32)
    facing = area(projected[..., :2]) > 1e-10
    for i, tri in enumerate(projected):
        if facing[i]:
            for y, x, weights in triangle_pixels((tri[:, :2]+PAD)/SPAN, size):
                z = weights @ tri[:, 2]
                depth[y, x] = np.maximum(depth[y, x], z)
        if i % 64 == 0:
            yield "Projection coverage", i/max(1, len(projected))
    return depth, facing


def visible(depth, coords, tolerance):
    # Nearest depth avoids interpolation with uncovered (-inf) pixels.
    xy = np.floor((coords[:, :2]+PAD)*len(depth)/SPAN).astype(int).clip(0, len(depth)-1)
    z = depth[xy[:, 1], xy[:, 0]]
    return np.isfinite(z) & (coords[:, 2] >= z-tolerance)


def bake_steps(thresholds, uvs, projected, depth, facing, size):
    output = np.ones((size, size, 3), dtype=np.float32)
    output[..., 2] = 0
    tolerance = 3*SPAN/len(depth)
    for i, tri in enumerate(uvs):
        if facing[i]:
            for y, x, weights in triangle_pixels(tri, size):
                coords = weights @ projected[i]
                valid = visible(depth, coords, tolerance)
                if np.any(valid):
                    yy, xx = y[valid], x[valid]
                    output[yy, xx, :2] = sample(thresholds, coords[valid, :2])
                    output[yy, xx, 2] = 1
        if i % 64 == 0:
            yield "Transfer to UV map", i/max(1, len(uvs))
    if not output[..., 2].any():
        raise ValueError("No visible front-facing face texels. Check the forward/up alignment and face region.")
    return output


def pad_steps(image, radius):
    """Nearest-seed dilation; B remains the original face coverage, without a halo."""
    size = image.shape[0]
    valid = image[..., 2] > .5
    sy, sx = np.indices(valid.shape, dtype=np.int32)
    seed_x, seed_y = np.where(valid, sx, -1), np.where(valid, sy, -1)
    best = np.where(valid, 0, radius*radius+1).astype(np.int32)
    # Each pass grows one Chebyshev step. Euclidean distances decide ownership.
    for step in range(radius):
        old_x, old_y = seed_x.copy(), seed_y.copy()
        for dy, dx in ((-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)):
            tx, ty = np.roll(old_x, (dy, dx), (0, 1)), np.roll(old_y, (dy, dx), (0, 1))
            possible = tx >= 0
            if dy < 0: possible[dy:] = False
            if dy > 0: possible[:dy] = False
            if dx < 0: possible[:, dx:] = False
            if dx > 0: possible[:, :dx] = False
            dist = (sx-tx)**2+(sy-ty)**2
            improve = possible & (dist < best) & (dist <= radius*radius)
            seed_x[improve], seed_y[improve], best[improve] = tx[improve], ty[improve], dist[improve]
            yield "UV island padding", (step+((dy+1)*3+dx+1)/9)/max(1, radius)
    use = ~valid & (seed_x >= 0)
    image[use, :2] = image[seed_y[use], seed_x[use], :2]
    return image
