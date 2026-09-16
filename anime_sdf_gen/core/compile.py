"""Ordered distance-field interpolation and explicit endpoint encoding."""

from .messages import UserError, msg, mark

import numpy as np
import hashlib
from .model import PAD, SPAN, LTR, RTL, SWEEP_LABELS, MAX_KEYFRAMES, sweep
from .curves import raster_keyframe
from .distance import signed_steps
from .jobs import run
from .thresholds import INTERIOR_MIN, INTERIOR_MAX


class KeyframeConflict(UserError):
    def __init__(self, direction, before, after, mask):
        self.direction, self.before, self.after, self.mask = direction, before, after, mask
        super().__init__(
            mark(
                "{direction} keyframes {before} → {after}: {count} pixels become lit again outside carried cutouts. Adjust the main boundary or shadow shapes."
            ),
            direction=msg(SWEEP_LABELS[direction]),
            before=before + 1,
            after=after + 1,
            count=int(mask.sum()),
        )


def face_domain(size):
    axis = (np.arange(size) + 0.5) * SPAN / size - PAD
    return (axis[:, None] >= 0) & (axis[:, None] <= 1) & (axis[None, :] >= 0) & (axis[None, :] <= 1)


def compile_steps(project, size, domain=None, field_cache=None, mask_cache=None):
    domain = face_domain(size) if domain is None else domain
    if project["mirror_sweeps"]:
        domain = domain | domain[:, ::-1]
    result = np.ones((size, size, 2), dtype=np.float32)
    layer_cache = {} if mask_cache is None else mask_cache

    def field(mask):
        # Later cutouts can change this mask without changing this frame's curves.
        key = (size, hashlib.blake2b(np.packbits(mask).tobytes(), digest_size=16).digest())
        if field_cache is not None and key in field_cache:
            return field_cache[key]
        d = yield from signed_steps(mask)
        if field_cache is not None:
            field_cache[key] = d
            while len(field_cache) > 2 * MAX_KEYFRAMES:
                del field_cache[next(iter(field_cache))]
        return d

    for channel, direction in enumerate((LTR,) if project["mirror_sweeps"] else (LTR, RTL)):
        frames = sweep(project, direction)
        previous_mask = raster_keyframe(project, frames[0], direction, size, cache=layer_cache)
        previous_d = yield from field(previous_mask)
        result[..., channel][previous_mask] = 0
        for index, frame in enumerate(frames[1:], 1):
            yield msg(
                "{direction} keyframe {index}/{count}",
                direction=msg(SWEEP_LABELS[direction]),
                index=index + 1,
                count=len(frames),
            ), index / len(frames)
            mask = raster_keyframe(project, frame, direction, size, cache=layer_cache)
            conflict = previous_mask & ~mask & domain
            if np.any(conflict):
                raise KeyframeConflict(direction, index - 1, index, conflict)
            d = yield from field(mask)
            changing = ~previous_mask & mask & (result[..., channel] == 1)
            a, b = frames[index - 1]["progress"], frame["progress"]
            alpha = -previous_d[changing] / (d[changing] - previous_d[changing])
            result[..., channel][changing] = np.clip(
                a + (b - a) * alpha, INTERIOR_MIN, INTERIOR_MAX
            )
            previous_mask, previous_d = mask, d
    if project["mirror_sweeps"]:
        result[..., 1] = result[:, ::-1, 0]
    return result


def compile_project(project, size, domain=None):
    return run(compile_steps(project, size, domain))
