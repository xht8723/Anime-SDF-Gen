"""Adaptive cubic flattening, contour validation, and scanline mask fills."""
import numpy as np
import json
from .model import PAD, SPAN, LTR, sweep


def handles(c, index):
    pts = c["points"]
    p = pts[index]
    co = np.asarray(p["co"], dtype=float)
    if p["mode"] == "CORNER":
        return co.copy(), co.copy()
    if p["mode"] == "FREE":
        return co + p["left"], co + p["right"]
    prev = np.asarray(pts[(index-1) % len(pts)]["co"] if index or c["closed"] else p["co"])
    nxt = np.asarray(pts[(index+1) % len(pts)]["co"] if index < len(pts)-1 or c["closed"] else p["co"])
    direction = nxt - prev
    length = np.linalg.norm(direction)
    if length < 1e-12:
        return co.copy(), co.copy()
    direction /= length
    before = np.linalg.norm(co - prev)/3
    after = np.linalg.norm(nxt - co)/3
    return co-direction*before, co+direction*after


def _flatten(a, b, c, d, tolerance, out, depth=0):
    chord = d-a
    length = np.linalg.norm(chord)
    if length < 1e-12:
        error = max(np.linalg.norm(b-a), np.linalg.norm(c-a))
    else:
        error = max(abs(chord[0]*(b-a)[1]-chord[1]*(b-a)[0]),
                    abs(chord[0]*(c-a)[1]-chord[1]*(c-a)[0]))/length
        # Collinear handles can still double back along the chord.
        error = max(error, (np.linalg.norm(b-a)+np.linalg.norm(c-b)+np.linalg.norm(d-c)-length)/4)
    if error <= tolerance or depth >= 14:
        out.append(d)
        return
    ab, bc, cd = (a+b)/2, (b+c)/2, (c+d)/2
    abc, bcd = (ab+bc)/2, (bc+cd)/2
    mid = (abc+bcd)/2
    _flatten(a, ab, abc, mid, tolerance, out, depth+1)
    _flatten(mid, bcd, cd, d, tolerance, out, depth+1)


def flatten(c, tolerance=.0005):
    pts = c["points"]
    out = [np.asarray(pts[0]["co"], dtype=float)]
    count = len(pts) if c["closed"] else len(pts)-1
    for i in range(count):
        j = (i+1) % len(pts)
        _flatten(np.asarray(pts[i]["co"]), handles(c, i)[1], handles(c, j)[0],
                 np.asarray(pts[j]["co"]), tolerance, out)
    arr = np.asarray(out)
    if c["closed"] and np.linalg.norm(arr[0]-arr[-1]) < 1e-10:
        arr = arr[:-1]
    return arr


def polygon(c, direction=LTR, tolerance=.0005):
    arr = flatten(c, tolerance)
    if not c["closed"]:
        x = -PAD-.02 if direction == LTR else 1+PAD+.02
        arr = np.vstack([arr, [x, arr[-1, 1]], [x, arr[0, 1]]])
    return arr


def self_intersects(poly):
    n = len(poly)
    if n < 3:
        return True
    def cross(a, b):
        return a[0]*b[1]-a[1]*b[0]
    for i in range(n):
        a, b = poly[i], poly[(i+1) % n]
        if np.linalg.norm(a-b) < 1e-10:
            return True
        for j in range(i+2, n):
            if (j+1) % n == i:
                continue
            c, d = poly[j], poly[(j+1) % n]
            if np.any(np.maximum(a, b) < np.minimum(c, d)-1e-10) or np.any(np.maximum(c, d) < np.minimum(a, b)-1e-10):
                continue
            ab, cd = b-a, d-c
            den = cross(ab, cd)
            if abs(den) < 1e-12:
                if abs(cross(c-a, ab)) < 1e-10:
                    return True
                continue
            t, u = cross(c-a, cd)/den, cross(c-a, ab)/den
            if -1e-9 <= t <= 1+1e-9 and -1e-9 <= u <= 1+1e-9:
                return True
    return False


def fill_polygon(poly, size):
    # Scanlines visit intersections, rather than testing every edge at every pixel.
    ys = (np.arange(size, dtype=float)+.5)*SPAN/size-PAD
    intersections = np.full((len(poly), size), np.inf)
    for i, a in enumerate(poly):
        b = poly[(i+1) % len(poly)]
        lo, hi = sorted((a[1], b[1]))
        active = (ys >= lo) & (ys < hi)
        if hi-lo > 1e-12 and np.any(active):
            intersections[i, active] = a[0]+(ys[active]-a[1])*(b[0]-a[0])/(b[1]-a[1])
    intersections.sort(axis=0)
    # Difference-array span fill avoids allocating an edges x height x width cube.
    diff = np.zeros((size, size+1), dtype=np.int16)
    rows = np.arange(size)
    for i in range(0, len(poly)-1, 2):
        valid = np.isfinite(intersections[i+1])
        a = np.ceil((intersections[i, valid]+PAD)*size/SPAN-.5).astype(int).clip(0, size)
        b = np.ceil((intersections[i+1, valid]+PAD)*size/SPAN-.5).astype(int).clip(0, size)
        diff[rows[valid], a] += 1
        diff[rows[valid], b] -= 1
    return np.cumsum(diff[:, :-1], axis=1) > 0


def raster_layers(frame, direction, size, validate=True, cache=None):
    """Local shadow and surviving explicit light after this frame's layers."""
    key=(size,direction,validate,json.dumps(frame,sort_keys=True))
    if cache is not None and key in cache:
        result=cache.pop(key);cache[key]=result
        return result
    mask=np.zeros((size,size),dtype=bool);light=np.zeros_like(mask)
    for c in frame['contours']:
        if not c.get('enabled',True):continue
        poly=polygon(c,direction,SPAN/(size*4))
        if validate and self_intersects(poly):
            raise ValueError(f"{c['name']}: contour crosses itself or has coincident points.")
        shape=fill_polygon(poly,size)
        if c['operation']=='ADD':
            mask|=shape;light&=~shape
        else:
            mask&=~shape
            if c['closed']:light|=shape
    if cache is not None:
        cache[key]=(mask,light)
        while len(cache)>80:del cache[next(iter(cache))]
    return mask,light


def inherited_light(project, frame, direction, size, validate=True, cache=None):
    """Explicit light carries only toward the start of this boundary sweep."""
    light=np.zeros((size,size),dtype=bool)
    for later in sweep(project,direction):
        if later['progress']>frame['progress'] and any(c['closed'] and c['operation']=='REMOVE' and c.get('enabled',True) for c in later['contours']):
            light |= raster_layers(later,direction,size,validate,cache)[1]
    return light


def raster_keyframe(project, frame, direction, size, validate=True, cache=None):
    mask,_=raster_layers(frame,direction,size,validate,cache)
    return mask & ~inherited_light(project,frame,direction,size,validate,cache)


def insert_point(c, segment):
    """Split a cubic exactly with de Casteljau, preserving its current shape."""
    from .model import point
    i, j = segment, (segment+1) % len(c["points"])
    a, d = np.asarray(c["points"][i]["co"]), np.asarray(c["points"][j]["co"])
    ai, b = handles(c, i)
    cc, dj = handles(c, j)
    ab, bc, cd = (a+b)/2, (b+cc)/2, (cc+d)/2
    abc, bcd = (ab+bc)/2, (bc+cd)/2
    mid = (abc+bcd)/2
    c["points"][i].update(mode="FREE", left=(ai-a).tolist(), right=(ab-a).tolist())
    c["points"][j].update(mode="FREE", left=(cd-d).tolist(), right=(dj-d).tolist())
    c["points"].insert(i+1, point(*mid, mode="FREE", left=abc-mid, right=bcd-mid))
    return i+1
