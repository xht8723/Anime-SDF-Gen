"""Cached mask/threshold computation; one CPU mask and one GPU upload."""

from .core.messages import UserError, msg, diagnostic, Joined

import time
import numpy as np
from .core import model, curves
from .core.compile import compile_steps, KeyframeConflict
from .core.thresholds import decode, endpoint_seams
from .core.smoothing import smooth_steps


class Preview:
    def __init__(self, session):
        self.session = session
        self.field_cache = {}
        self.mask_cache = {}
        self.thresholds = self.raw_thresholds = None
        self.filter_job = self.filter_key = self.filtered_key = None
        self.filter_due = self.debounce = 0.0
        self.job = None
        self.depth = self.domain = None
        self.rgba = np.ones((session.size, session.size, 4), dtype=np.float32)
        self.mask_revision = 0
        self._mask_texture = self._face_shader = self._face_batch = None
        self._mask_texture_revision = -1
        self.last_render_ms = 0.0
        self.render_times = []

    def cancel_filter(self):
        if self.filter_job:
            self.filter_job.close()
        self.filter_job = self.filter_key = None

    def cancel(self):
        if self.job:
            self.job.close()
        self.job = None
        self.cancel_filter()

    def set_smoothing(self, value):
        self.session.require_edit()
        value = float(value)
        if not np.isfinite(value) or not 0 <= value <= 8:
            raise UserError("Smoothing must be a finite number from 0 to 8.")
        if self.session.project["settings"]["smoothing"] == value:
            return
        self.session.project["settings"]["smoothing"] = value
        self.cancel_filter()
        self.filter_due = time.perf_counter() + 0.15
        if value == 0 and self.raw_thresholds is not None:
            self.thresholds = self.raw_thresholds
            self.filtered_key = (
                id(self.raw_thresholds),
                0.0,
                self.session.project["mirror_sweeps"],
            )
            if self.session.orbit_preview:
                self.render()
        self.session.draft_due = time.perf_counter() + 0.5
        self.session.sync_launcher()
        self.session.redraw()

    def advance_filter(self, now, stop):
        if self.raw_thresholds is None:
            return
        strength = self.session.project["settings"]["smoothing"]
        key = (id(self.raw_thresholds), strength, self.session.project["mirror_sweeps"])
        if key == self.filtered_key:
            return
        if strength == 0:
            self.cancel_filter()
            self.thresholds = self.raw_thresholds
            self.filtered_key = key
            if self.session.orbit_preview:
                self.render()
            return
        if self.filter_job is None and now >= self.filter_due:
            self.filter_key = key
            self.filter_job = smooth_steps(
                self.raw_thresholds, strength, self.session.project["mirror_sweeps"]
            )
        while self.filter_job and time.perf_counter() < stop:
            try:
                next(self.filter_job)
            except StopIteration as done:
                if self.filter_key == key:
                    self.thresholds = done.value
                    self.filtered_key = key
                    if self.session.orbit_preview:
                        self.render()
                self.filter_job = self.filter_key = None
                break
            except Exception as exc:
                self.cancel_filter()
                self.session.error = diagnostic(exc)
                self.filter_due = float("inf")
                self.session.redraw()
                break

    def render(self, validate=False):
        start = time.perf_counter()
        try:
            if self.session.orbit_preview and self.thresholds is not None:
                direction, progress = model.rotation_sample(self.session.rotation)
                channel = 0 if direction == model.LTR else 1
                mask = decode(self.thresholds[..., channel], progress)
            else:
                # Preview the current artwork immediately, including an invalid
                # contour being repaired. Validation still blocks generation.
                mask = curves.raster_keyframe(
                    self.session.project,
                    self.session.keyframe,
                    self.session.direction,
                    self.session.size,
                    False,
                    self.mask_cache,
                )
            self.rgba[..., 0] = mask
            self.rgba[..., 1] = self.session.conflict if self.session.conflict is not None else 0
            self.rgba[..., 2] = self.domain
            self.mask_revision += 1
            self.session.redraw()
            if validate:
                curves.raster_keyframe(
                    self.session.project,
                    self.session.keyframe,
                    self.session.direction,
                    self.session.size,
                    True,
                    self.mask_cache,
                )
        except ValueError as exc:
            self.session.error = diagnostic(exc)
        self.last_render_ms = (time.perf_counter() - start) * 1000
        self.render_times.append(self.last_render_ms)
        self.render_times = self.render_times[-120:]

    def advance(self, now):
        if self.raw_thresholds is None and self.job is None and now >= self.debounce:
            self.job = compile_steps(
                self.session.project,
                self.session.size,
                self.domain,
                self.field_cache,
                self.mask_cache,
            )
        if self.job:
            stop = now + 0.009
            while time.perf_counter() < stop:
                try:
                    next(self.job)
                except StopIteration as done:
                    self.raw_thresholds = done.value
                    seams = endpoint_seams(self.raw_thresholds, self.domain)
                    affected = [
                        msg("{name}: {count} pixels", name=msg(name), count=count)
                        for name, count in seams.items()
                        if count
                    ]
                    self.session.seam_warning = (
                        msg(
                            "360° orbit seam at {details}. Align the two sweeps’ endpoint artwork for a continuous orbit. Export is available.",
                            details=Joined(tuple(affected)),
                        )
                        if affected
                        else ""
                    )
                    self.job = None
                    if self.session.orbit_preview:
                        self.render()
                    break
                except (ValueError, KeyframeConflict) as exc:
                    self.session.error = diagnostic(exc)
                    self.session.conflict = exc.mask if isinstance(exc, KeyframeConflict) else None
                    self.job = None
                    self.debounce = float("inf")
                    self.render()
                    break
        self.advance_filter(now, time.perf_counter() + 0.009)
        if self.session.playing and self.thresholds is not None:
            self.session.rotation = model.advance_rotation(
                self.session.rotation, (now - self.session.last_tick) * 30.0
            )
            self.session.orbit_preview = True
            self.render()

    def invalidate(self, dragging=False):
        self.thresholds = self.raw_thresholds = None
        self.filtered_key = None
        self.cancel()
        self.debounce = time.perf_counter() + (0.20 if dragging else 0.08)

    def close(self):
        self.cancel()
        self.thresholds = self.raw_thresholds = None
        self.filtered_key = None
        self._face_shader = self._face_batch = self._mask_texture = None
        self.depth = self.domain = self.rgba = None
        self.field_cache.clear()
        self.mask_cache.clear()
        self.render_times.clear()
