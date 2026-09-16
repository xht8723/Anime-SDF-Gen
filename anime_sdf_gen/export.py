"""Cancellable export coordination over an immutable project snapshot."""

from .core.messages import UserError, msg, diagnostic

from copy import deepcopy
import time
import traceback
import bpy
import numpy as np
from . import source
from .core import model
from .core.compile import compile_steps, KeyframeConflict
from .core.geometry import projection_steps, bake_steps, pad_steps
from .core.files import export_steps
from .core.smoothing import smooth_steps


class ExportJob:
    def __init__(self, session, on_finish):
        self.session = session
        self.on_finish = on_finish
        self.job = None
        self.paths = None
        self.message = ""

    @property
    def running(self):
        return self.job is not None

    def start(self):
        s = self.session
        if s.closed or self.running:
            raise UserError("Generation is already running or this session is closed.")
        if s.stage != "CONFIRM":
            raise UserError("Continue to Confirm before generating.")
        if not s.project["settings"]["output"].strip():
            raise UserError("Choose a save location in Confirm before generating.")
        project = deepcopy(s.project)
        model.validate_project(project)
        s.playing = False
        s.preview.cancel()
        s.error, s.conflict = "", None
        self.paths = None
        self.job = self._generate(project)
        s.safe_write_draft()

    def _generate(self, project):
        # Re-read before export to catch a changed source, pose, or UV layout.
        with self.session.origin.override():
            face = source.from_reference(project["source"], project["alignment"])
        size = project["settings"]["resolution"]
        depth, facing = yield from projection_steps(face.projected, size)
        threshold = yield from compile_steps(project, size, np.isfinite(depth))
        threshold = yield from smooth_steps(
            threshold, project["settings"]["smoothing"], project["mirror_sweeps"]
        )
        image = yield from bake_steps(threshold, face.uvs, face.projected, depth, facing, size)
        image = yield from pad_steps(
            image, max(1, round(project["settings"]["padding"] * size / 2048))
        )
        yield msg("Verify and commit output files"), 0.99
        output = bpy.path.abspath(project["settings"]["output"])
        if not output:
            raise UserError("Choose an output path before generation.")
        return (yield from export_steps(project, image, output))

    def advance(self, seconds=0.012, finish=True):
        stop = time.perf_counter() + seconds
        while self.job and time.perf_counter() < stop:
            try:
                label, progress = next(self.job)
                self.message = msg("{label} · {progress:.0%}", label=label, progress=progress)
            except StopIteration as done:
                self.paths = done.value
                self.job = None
                self.message = msg("Saved: {path}", path=self.paths[0])
                if finish:
                    self.on_finish()
                break
            except Exception as exc:
                self.job = None
                self.session.preview.cancel()
                self.session.preview.debounce = float("inf")
                self.session.error = diagnostic(exc)
                if isinstance(exc, KeyframeConflict):
                    self.session.direction, self.session.key_index = exc.direction, exc.after
                    coords = np.linspace(0, len(exc.mask) - 1, self.session.size).astype(int)
                    self.session.conflict = exc.mask[np.ix_(coords, coords)]
                    self.session.orbit_preview = False
                    self.session.preview.render()
                    self.session.sync_launcher()
                traceback.print_exc()
                break
        if not self.session.closed:
            self.session.redraw()

    def cancel(self):
        self.close()
        self.message = msg("Generation cancelled; authoring data retained.")

    def close(self):
        job, self.job = self.job, None
        if job:
            job.close()
