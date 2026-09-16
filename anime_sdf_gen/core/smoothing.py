"""Cancellable head-space filtering; no UV islands or coverage enter this stage."""

from .messages import UserError, msg

import math
import numpy as np
from .thresholds import INTERIOR_MIN, INTERIOR_MAX


def gaussian_kernel(strength, size):
    if not math.isfinite(strength) or not 0 <= strength <= 8:
        raise UserError("Smoothing must be a finite number from 0 to 8.")
    sigma = float(strength) * size / 2048
    if sigma == 0:
        return np.ones(1, dtype=np.float64)
    radius = math.ceil(3 * sigma)
    axis = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (axis / sigma) ** 2)
    return kernel / kernel.sum()


def _convolve_steps(array, kernel, axis):
    """Zero outside the padded canvas; numerator and weights share that border."""
    out = np.empty_like(array)
    radius = len(kernel) // 2
    h, w = array.shape
    for row in range(0, h, 32):
        end = min(h, row + 32)
        block = out[row:end]
        block.fill(0)
        for index, weight in enumerate(kernel):
            offset = index - radius
            if axis == 1:
                lo, hi = max(0, -offset), min(w, w - offset)
                if lo < hi:
                    block[:, lo:hi] += weight * array[row:end, lo + offset : hi + offset]
            else:
                lo, hi = max(row, -offset), min(end, h - offset)
                if lo < hi:
                    block[lo - row : hi - row] += weight * array[lo + offset : hi + offset]
        yield msg("Smooth shadow thresholds"), end / h
    return out


def smooth_steps(thresholds, strength, mirrored=False):
    """Filter ordinary thresholds, preserving endpoint pixels exactly.

    Returns the input itself when disabled. The input is never modified.
    Normalized convolution excludes sentinels from both directions' weights.
    """
    kernel = gaussian_kernel(strength, len(thresholds))
    if strength == 0:
        return thresholds
    if thresholds.ndim != 3 or thresholds.shape[2] != 2 or not np.isfinite(thresholds).all():
        raise UserError("Expected two finite head-space threshold fields.")
    output = thresholds.copy()
    for channel in range(1 if mirrored else 2):
        field = thresholds[..., channel]
        interior = (field > 0) & (field < 1)
        if not interior.any():
            continue
        weights = interior.astype(np.float64)
        values = np.where(interior, field, 0).astype(np.float64)
        for axis in (1, 0):
            values = yield from _convolve_steps(values, kernel, axis)
            weights = yield from _convolve_steps(weights, kernel, axis)
        # The center weight is positive, including for isolated transition pixels.
        for row in range(0, len(field), 32):
            end = row + 32
            use = interior[row:end]
            output[row:end, :, channel][use] = np.clip(
                values[row:end][use] / weights[row:end][use], INTERIOR_MIN, INTERIOR_MAX
            )
            yield msg("Smooth shadow thresholds"), min(end, len(field)) / len(field)
    if mirrored:
        output[..., 1] = output[:, ::-1, 0]
    return output
