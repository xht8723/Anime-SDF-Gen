"""Ordered distance-field interpolation and explicit endpoint encoding."""
import numpy as np
import hashlib
from .model import PAD, SPAN, LTR, RTL, SWEEP_LABELS, MAX_KEYFRAMES, sweep
from .curves import raster_keyframe
from .distance import signed_steps, run


class KeyframeConflict(ValueError):
    def __init__(self, direction, before, after, mask):
        self.direction, self.before, self.after, self.mask = direction, before, after, mask
        super().__init__(f"{SWEEP_LABELS[direction]} keyframes {before+1} → {after+1}: {int(mask.sum())} pixels become lit again outside carried cutouts. Adjust the main boundary or shadow shapes.")


def face_domain(size):
    axis = (np.arange(size)+.5)*SPAN/size-PAD
    return (axis[:, None] >= 0) & (axis[:, None] <= 1) & (axis[None, :] >= 0) & (axis[None, :] <= 1)


def compile_steps(project, size, domain=None, field_cache=None, mask_cache=None):
    domain = face_domain(size) if domain is None else domain
    if project['mirror_sweeps']:
        domain = domain | domain[:, ::-1]
    result = np.ones((size, size, 2), dtype=np.float32)
    layer_cache={} if mask_cache is None else mask_cache
    def field(mask):
        # Later cutouts can change this mask without changing this frame's curves.
        key = (size,hashlib.blake2b(np.packbits(mask).tobytes(),digest_size=16).digest())
        if field_cache is not None and key in field_cache:
            return field_cache[key]
        d = yield from signed_steps(mask)
        if field_cache is not None:
            field_cache[key] = d
            while len(field_cache) > 2*MAX_KEYFRAMES:
                del field_cache[next(iter(field_cache))]
        return d
    for channel, direction in enumerate((LTR,) if project['mirror_sweeps'] else (LTR, RTL)):
        frames = sweep(project, direction)
        previous_mask = raster_keyframe(project, frames[0], direction, size,cache=layer_cache)
        previous_d = yield from field(previous_mask)
        result[..., channel][previous_mask] = 0
        for index, frame in enumerate(frames[1:], 1):
            yield f"{SWEEP_LABELS[direction]} keyframe {index+1}/{len(frames)}", index/len(frames)
            mask = raster_keyframe(project, frame, direction, size,cache=layer_cache)
            conflict = previous_mask & ~mask & domain
            if np.any(conflict):
                raise KeyframeConflict(direction, index-1, index, conflict)
            d = yield from field(mask)
            changing = ~previous_mask & mask & (result[..., channel] == 1)
            a, b = frames[index-1]["progress"], frame["progress"]
            alpha = -previous_d[changing]/(d[changing]-previous_d[changing])
            result[..., channel][changing] = np.clip(a+(b-a)*alpha, 1/65535, 65534/65535)
            previous_mask, previous_d = mask, d
    if project['mirror_sweeps']:
        result[..., 1] = result[:, ::-1, 0]
    return result


def compile_project(project, size, domain=None):
    return run(compile_steps(project, size, domain))


def decode(threshold, progress):
    return (threshold == 0) | ((threshold < 1) & (float(progress) >= threshold))


def endpoint_seams(thresholds, domain):
    """Counts of visible front/back discontinuities between authored maps."""
    return {name: int(np.count_nonzero((decode(thresholds[...,0],progress) != decode(thresholds[...,1],progress)) & domain))
            for name,progress in (('Front',0),('Back',1))}


def sample(array, uv):
    """Bilinear lookup in face coordinates (0..1), including the padded canvas."""
    size = array.shape[0]
    pos = (np.asarray(uv)+PAD)*size/SPAN-.5
    pos = np.clip(pos, 0, size-1)
    lo = np.floor(pos).astype(np.int32)
    hi = np.minimum(lo+1, size-1)
    frac = pos-lo
    x, y = lo[..., 0], lo[..., 1]
    xx, yy = hi[..., 0], hi[..., 1]
    fx, fy = frac[..., 0], frac[..., 1]
    if array.ndim == 3:
        fx, fy = fx[..., None], fy[..., None]
    return (array[y, x]*(1-fx)+array[y, xx]*fx)*(1-fy)+(array[yy, x]*(1-fx)+array[yy, xx]*fx)*fy
