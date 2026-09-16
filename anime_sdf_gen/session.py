"""Authoring state, guarded edits, and lifecycle coordination."""

from .core.messages import FileError, UserError, msg, diagnostic

from copy import deepcopy
from pathlib import Path
import time
import traceback
import bpy
import numpy as np
from mathutils import Vector
from . import source, i18n
from .core import model, editing
from .core.jobs import run
from .core.geometry import projection_steps, visible
from .core.files import atomic_text
from .resources import Registry, OriginContext
from .preview import Preview
from .export import ExportJob
from .commands import EditTransaction
from .editor import Editor
from .canvas import flat_contour
from mathutils.bvhtree import BVHTree

ACTIVE = None
SUSPENDED = None


def draft_root():
    # User data, never the extension installation directory or the original blend.
    path = bpy.utils.user_resource("CONFIG")
    if not path:
        raise FileError("The SDF recovery directory could not be created in Blender user data.")
    result = Path(path) / "anime_sdf_gen" / f"v{model.FORMAT_VERSION}" / "drafts"
    result.mkdir(parents=True, exist_ok=True)
    return result


class Session:
    def __init__(self, context, project, face, layout=None):
        self.project, self.face = project, face
        self.origin = OriginContext(context)
        self.registry = Registry()
        self.history = model.History()
        self.direction, self.key_index, self.contour, self.point = model.LTR, 0, 0, 0
        self.handle = "co"
        self.selected = {(0, 0)}
        self.curve_edit = None
        self.landmark = "nose"
        self.flat = False
        self.orbit_preview = self.playing = False
        self.rotation = 0.0
        self.closed = self.dragging = False
        self.close_requested = None
        self.save_requested = False
        self.error = self.seam_warning = ""
        self.locale_signature = i18n.signature()
        self.conflict = None
        self.draft_due = 0.0
        self.last_tick = time.perf_counter()
        self.preview_object = self.scene = None
        self._timer = self.tick
        self._modal_running = False
        self.editor = None
        self.layout_state = layout
        self.bvh = None
        self._material_copies = {}
        self.preview = Preview(self)
        self.export = ExportJob(self, lambda: end_session(remove_draft=True))
        self.refresh_projection()

    @property
    def busy(self):
        return self.export.running

    @property
    def stage(self):
        return self.project["authoring"]["stage"]

    def refresh_projection(self):
        face = self.face
        self.bvh = BVHTree.FromPolygons(
            face.vertices.tolist(), face.triangles.tolist(), all_triangles=True
        )
        self.preview.depth, _ = run(projection_steps(face.projected, self.size))
        self.preview.domain = np.isfinite(self.preview.depth)
        if not self.preview.domain.any() and self.stage != "ORIENT":
            raise UserError("No front-facing face surface. Reset the face orientation.")

    def redraw(self):
        if self.editor:
            self.editor.redraw()

    @property
    def size(self):
        return self.project["settings"]["preview_size"]

    @property
    def keyframe(self):
        self.key_index = max(
            0, min(self.key_index, len(model.sweep(self.project, self.direction)) - 1)
        )
        return model.get_keyframe(self.project, self.direction, self.key_index)

    @property
    def curve(self):
        cs = self.keyframe["contours"]
        self.contour = min(self.contour, len(cs) - 1)
        return cs[self.contour]

    def begin(self, attach_handlers=True):
        try:
            self._build_preview()
            if self.stage == "FIT":
                self.seed_landmarks()
            self.activate_stage()
            self.preview.debounce = time.perf_counter() + 0.15
            self.safe_write_draft()
            if attach_handlers and self.origin.window and not bpy.app.background:
                self.editor = Editor(self, self.layout_state)
                self.editor.open()
                bpy.app.timers.register(self._timer, first_interval=0.03)
            self.sync_launcher()
        except Exception:
            self.close(remove_draft=False)
            raise

    def _build_preview(self):
        own = self.registry.own
        self.scene = own("scenes", bpy.data.scenes.new("Anime SDF Gen Preview"))
        self.scene.render.engine = "BLENDER_EEVEE"
        self.scene.view_settings.view_transform = "Standard"
        self.scene.world = own("worlds", bpy.data.worlds.new("SDF Preview World"))
        self.scene.world.color = (0.12, 0.12, 0.12)
        mesh = own("meshes", bpy.data.meshes.new("SDF Preview Face"))
        self.preview_object = own("objects", bpy.data.objects.new("SDF Preview Face", mesh))
        self.scene.collection.objects.link(self.preview_object)
        self.scene.view_layers[0].objects.active = self.preview_object
        self.preview_object.select_set(True, view_layer=self.scene.view_layers[0])
        self.populate_reference()

    def populate_reference(self):
        if self.editor:
            self.editor.geometry_revision += 1
        mesh = self.preview_object.data
        mesh.clear_geometry()
        mesh.from_pydata(self.face.vertices.tolist(), [], self.face.triangles.tolist())
        mesh.update()
        for p in mesh.polygons:
            p.use_smooth = True
        for layer in list(mesh.uv_layers):
            mesh.uv_layers.remove(layer)
        for name, coords in (
            self.face.uv_layers or {self.face.reference["uv_map"]: self.face.uvs}
        ).items():
            layer = mesh.uv_layers.new(name=name)
            layer.data.foreach_set("uv", coords.astype(np.float32).ravel())
        if self.face.reference["uv_map"] in mesh.uv_layers:
            mesh.uv_layers.active = mesh.uv_layers[self.face.reference["uv_map"]]
        mesh.materials.clear()
        for original in self.face.materials or []:
            key = original.as_pointer() if original else 0
            if key not in self._material_copies:
                mat = (
                    original.copy() if original else bpy.data.materials.new("Anime SDF Gen Neutral")
                )
                self._material_copies[key] = self.registry.own("materials", mat)
            mesh.materials.append(self._material_copies[key])
        if self.face.material_indices is not None:
            mesh.polygons.foreach_set("material_index", self.face.material_indices)
        self.preview._face_batch = None

    def frame_view(self):
        if self.editor:
            self.editor.frame()

    def set_front(self, rotation=None):
        with self.edit(invalidate=False, stages=("ORIENT",)):
            if self.editor:
                self.editor.navigation.stop()
            if rotation is None:
                if not self.editor or not self.editor.ready:
                    raise UserError("Wait for the authoring view to open.")
                rotation = self.editor.views["AUTHOR"].view_rotation
            a = source.fit_frame(
                self.face.vertices, rotation @ Vector((0, 0, 1)), rotation @ Vector((0, 1, 0))
            )
            ref = deepcopy(self.project["source"])
            ref["uv_map"] = self.project["authoring"]["uv_map"] or ref["uv_map"]
            ref["front_only"] = self.project["authoring"]["front_only"]
            with self.origin.override():
                face = source.from_reference(ref, a, allow_relink=True)
            self.face = face
            self.project["source"], self.project["alignment"] = face.reference, a
            self.project["authoring"].update(stage="FIT", anchors={})
            self.project["landmarks"] = deepcopy(model.DEFAULT_LANDMARKS)
            self.refresh_projection()
            self.populate_reference()
            self.seed_landmarks()
            self.changed()
            self.frame_view()

    def seed_landmarks(self):
        """Attach missing default markers to the visible frontal surface."""
        a = self.project["alignment"]
        extent = max(a["width"], a["height"])
        start_depth = (float(np.max(self.face.projected[..., 2])) + 1) * extent
        direction = -Vector(a["forward"])
        covered = np.argwhere(self.preview.domain)
        if not len(covered):
            raise UserError("No visible face surface for fitting markers.")
        supported = (covered[:, ::-1] + 0.5) * model.SPAN / self.size - model.PAD
        for name, default in model.DEFAULT_LANDMARKS.items():
            if name in self.project["authoring"]["anchors"]:
                continue
            target = np.asarray(self.project["landmarks"].get(name, default))
            # Try the intended point first, then the nearest covered pixel
            # centers when a facial opening leaves a hole under that point.
            nearest = np.argsort(np.sum((supported - target) ** 2, axis=1), kind="stable")[:32]
            for xy in [target, *supported[nearest]]:
                origin = source.world_point(a, xy, start_depth)
                hit, normal, index, distance = self.bvh.ray_cast(origin, direction)
                if hit is not None and self.place_landmark(hit, index, name):
                    break
            else:
                raise UserError(
                    "Cannot place the {marker} marker on the selected face.",
                    marker=msg({"nose": "Nose", "mouth": "Mouth Center", "chin": "Chin"}[name]),
                )
        self.landmark = "nose"
        self.error = ""
        self.sync_launcher()
        self.redraw()

    def pick_landmark(self, view, mouse, name=None):
        origin, direction = view.ray(mouse)
        hit, normal, index, distance = self.bvh.ray_cast(origin, direction)
        if hit is None:
            self.notify_error("Click on the visible face to place a marker. No surface was hit.")
            return False
        return self.place_landmark(hit, index, name or self.landmark)

    def place_landmark(self, hit, index, name):
        a = self.project["alignment"]
        delta = np.asarray(hit) - a["center"]
        coords = np.array(
            [
                np.dot(delta, a["right"]) / a["width"] + 0.5,
                np.dot(delta, a["up"]) / a["height"] + 0.5,
                np.dot(delta, a["forward"]) / max(a["width"], a["height"]),
            ]
        )
        if not visible(self.preview.depth, coords[None], 4 * model.SPAN / self.size)[0]:
            self.error = msg(
                "That point is outside supported frontal coverage. Choose a visible facial surface."
            )
            self.redraw()
            return False
        tri = self.face.vertices[self.face.triangles[index]]
        weights = np.linalg.lstsq(np.vstack([tri.T, np.ones(3)]), np.append(hit, 1), rcond=None)[0]
        weights = np.clip(weights, 0, 1)
        weights /= weights.sum()
        self.project["landmarks"][name] = coords[:2].tolist()
        self.project["authoring"]["anchors"][name] = {
            "world": list(hit),
            "barycentric": weights.tolist(),
            "vertices": self.face.triangle_vertices[index].tolist(),
        }
        self.error = ""
        self.draft_due = time.perf_counter() + 0.5
        self.sync_launcher()
        self.redraw()
        return True

    def fit(self, count=None):
        with self.edit(invalidate=False, stages=("FIT",)):
            if any(
                name not in self.project["authoring"]["anchors"]
                for name in ("nose", "mouth", "chin")
            ):
                raise UserError("Place Nose, Mouth Center, and Chin on the face before fitting.")
            nose, mouth, chin = (self.project["landmarks"][k][1] for k in ("nose", "mouth", "chin"))
            if not nose > mouth > chin:
                raise UserError("Place Nose above Mouth Center, and Mouth Center above Chin.")
            model.refit(self.project, count)
            self.direction, self.key_index, self.contour, self.point = model.LTR, 0, 0, 0
            self.changed()
            self.activate_stage()

    def activate_stage(self):
        """Initialize a step without refitting curves or invalidating cached fields."""
        self.playing = self.orbit_preview = False
        if self.stage in ("EDIT", "CONFIRM"):
            self.direction, self.key_index, self.contour, self.point = model.LTR, 0, 0, 0
            self.handle = "co"
            self.keyframe_scroll = 0
            self.rotation = 0.0
            self.reset_selection()
        if self.stage == "CONFIRM":
            self.playing = self.orbit_preview = True
            self.flat = False
        self.last_tick = time.perf_counter()
        self.draft_due = self.last_tick + 0.1
        self.preview.render()
        if self.editor:
            self.editor.refresh_appearance()
        self.sync_launcher()
        self.redraw()

    def confirm(self):
        self.require_edit(("EDIT",))
        self.project["authoring"]["stage"] = "CONFIRM"
        self.activate_stage()

    def restore_project(self, project):
        previous_stage = self.stage
        self.preview.cancel()
        changed_geometry = (
            project["alignment"] != self.project["alignment"]
            or project["source"] != self.project["source"]
        )
        self.project = project
        if changed_geometry:
            with self.origin.override():
                self.face = source.from_reference(
                    project["source"], project["alignment"], validate=self.stage != "ORIENT"
                )
            self.refresh_projection()
            self.populate_reference()
        self.changed()
        if self.stage != previous_stage:
            self.activate_stage()

    def canonicalize_edit(self):
        model.synchronize_mirror(self.project, self.direction)

    def normalize_selection(self):
        self.direction = self.direction if self.direction in model.SWEEP_LABELS else model.LTR
        self.key_index = max(
            0, min(self.key_index, len(model.sweep(self.project, self.direction)) - 1)
        )
        frame = model.get_keyframe(self.project, self.direction, self.key_index)
        self.contour = max(0, min(self.contour, len(frame["contours"]) - 1))
        self.point = max(0, min(self.point, len(frame["contours"][self.contour]["points"]) - 1))
        self.selected.intersection_update(editing.available(frame))

    def reset_selection(self, whole_curve=False):
        self.handle = "co"
        self.selected = (
            {(self.contour, i) for i in range(len(self.curve["points"]))}
            if whole_curve
            else {(self.contour, self.point)}
        )

    def cancel_curve_edit(self):
        if self.curve_edit:
            self.curve_edit.cancel()

    def checkpoint(self):
        return {
            "project": deepcopy(self.project),
            "face": self.face,
            "selection": (
                self.direction,
                self.key_index,
                self.contour,
                self.point,
                self.handle,
                self.landmark,
            ),
            "selected": self.selected.copy(),
            "playback": (self.playing, self.orbit_preview, self.rotation, self.flat),
            "undo": self.history.undo_stack[:],
            "redo": self.history.redo_stack[:],
        }

    def rollback(self, state):
        previous_stage = self.stage
        self.preview.cancel()
        geometry = self.face is not state["face"]
        self.project, self.face = state["project"], state["face"]
        self.direction, self.key_index, self.contour, self.point, self.handle, self.landmark = (
            state["selection"]
        )
        self.selected = state["selected"].copy()
        self.history.undo_stack, self.history.redo_stack = state["undo"], state["redo"]
        self.dragging = False
        if geometry:
            self.refresh_projection()
            self.populate_reference()
        self.changed()
        if self.stage != previous_stage:
            self.activate_stage()
        self.playing, self.orbit_preview, self.rotation, self.flat = state["playback"]
        self.preview.render()

    def notify_error(self, exc):
        self.error = diagnostic(exc)
        self.redraw()

    def changed(self, dragging=False):
        self.normalize_selection()
        self.playing = False
        self.canonicalize_edit()
        self.preview.invalidate(dragging)
        self.conflict = None
        self.error = self.seam_warning = ""
        self.draft_due = time.perf_counter() + 0.5
        self.orbit_preview = False
        self.rotation = model.keyframe_rotation(self.direction, self.keyframe["progress"])
        self.preview.render(validate=not dragging and self.stage == "EDIT")
        if self.editor and not dragging:
            self.editor.refresh_appearance()
        self.sync_launcher()

    def select_keyframe(self, direction, index):
        if direction not in model.SWEEP_LABELS or not 0 <= index < len(
            model.sweep(self.project, direction)
        ):
            raise UserError("Choose an existing keyframe in a sweep row.")
        self.playing = self.orbit_preview = False
        self.direction, self.key_index = direction, index
        self.contour, self.point, self.handle = 0, 0, "co"
        self.reset_selection()
        self.rotation = model.keyframe_rotation(direction, self.keyframe["progress"])
        self.preview.render()
        self.sync_launcher()

    def sync_launcher(self):
        props = getattr(bpy.context.window_manager, "anime_sdf_gen", None)
        if props:
            props.keyframes = self.project["authoring"]["keyframe_count"]
            props.preset = self.project["preset"]
            props.mirror_sweeps = self.project["mirror_sweeps"]
            props.output = self.project["settings"]["output"]
            props.resolution = str(self.project["settings"]["resolution"])

    def require_edit(self, stages=None):
        if self.closed or ACTIVE is not self or self.busy:
            raise UserError("This session is closed or generation is running.")
        if stages is not None and self.stage not in stages:
            raise UserError("This action is unavailable in the current step.")

    def edit(self, history=True, invalidate=True, stages=None):
        return EditTransaction(self, history, invalidate, stages)

    def write_draft(self):
        atomic_text(
            draft_root() / (self.project["id"] + ".sdfproject.json"), model.dumps(self.project)
        )

    def safe_write_draft(self):
        try:
            self.write_draft()
            return True
        except (OSError, ValueError) as exc:
            # Recovery IO must never prevent restoration or cause preview IDs
            # to be included in an ordinary .blend save.
            self.error = msg("Recovery draft unavailable: {details}", details=diagnostic(exc))
            self.draft_due = 0
            print("Anime SDF Gen:", self.error)
            return False

    def refresh_language(self):
        current = i18n.signature()
        if current != self.locale_signature:
            self.locale_signature = current
            self.redraw()

    def tick(self):
        if self.closed:
            return None
        if self.close_requested is not None:
            # Dispose after the operator/input event has returned to Blender.
            # Closing its native window from inside that event frees its RNA.
            end_session(remove_draft=self.close_requested)
            return None
        if self.save_requested:
            self.save_requested = False
            try:
                with bpy.context.temp_override(
                    window=self.editor.window, area=self.editor.native_area
                ):
                    bpy.ops.wm.save_mainfile("INVOKE_DEFAULT")
            except Exception as exc:
                self.notify_error(exc)
            return None if self.closed else 0.025
        now = time.perf_counter()
        try:
            self.refresh_language()
            if self.editor:
                if not self.editor.alive():
                    end_session(remove_draft=True)
                    return None
                if not self.editor.ready:
                    self.editor.advance()
                    return 0.035
                self.editor.navigation.poll()
                self.editor.lock_author()
                self.editor.tick_tooltip(now)
            if self.draft_due and now >= self.draft_due:
                self.safe_write_draft()
                self.draft_due = 0
            if self.busy:
                self.export.advance(0.012)
            elif not self.dragging and self.stage in ("EDIT", "CONFIRM"):
                self.preview.advance(now)
            self.last_tick = now
        except Exception as exc:
            self.error = diagnostic(exc)
            traceback.print_exc()
            if self.editor and not self.editor.ready:
                if hasattr(bpy.context.window_manager, "anime_sdf_gen"):
                    i18n.launcher_notice = msg(
                        "Could not open editor: {details}", details=self.error
                    )
                end_session(remove_draft=False)
                return None
        return 0.025

    def close(self, remove_draft=False):
        if self.closed:
            return
        self.cancel_curve_edit()
        self.closed, self.playing = True, False
        self.preview.cancel()
        self.export.close()
        if bpy.app.timers.is_registered(self._timer):
            bpy.app.timers.unregister(self._timer)
        if getattr(self, "_event_timer", None):
            try:
                bpy.context.window_manager.event_timer_remove(self._event_timer)
            except ReferenceError:
                pass
            self._event_timer = None
        if self.editor:
            self.editor.close()
        self.registry.dispose()
        self.preview.close()
        self.bvh = None
        self._material_copies.clear()
        flat_contour.cache_clear()
        self.scene = self.preview_object = None
        self.curve_edit = None
        if remove_draft:
            try:
                (draft_root() / (self.project["id"] + ".sdfproject.json")).unlink(missing_ok=True)
            except OSError as exc:
                print("Anime SDF Gen: could not remove recovery draft:", exc)


def start(context, project, face, handlers=True, layout=None):
    global ACTIVE
    if ACTIVE:
        raise UserError("Finish or close the current SDF authoring session first.")
    session = Session(context, project, face, layout)
    ACTIVE = session
    try:
        session.begin(handlers)
    except Exception:
        ACTIVE = None
        raise
    return session


def end_session(remove_draft=False):
    global ACTIVE
    current, ACTIVE = ACTIVE, None
    if current:
        current.close(remove_draft)


@bpy.app.handlers.persistent
def save_pre(_):
    global SUSPENDED
    if ACTIVE and not SUSPENDED:
        ACTIVE.cancel_curve_edit()
        ACTIVE.safe_write_draft()
        SUSPENDED = {
            "project": deepcopy(ACTIVE.project),
            "face": ACTIVE.face,
            "history": ACTIVE.history,
            "direction": ACTIVE.direction,
            "key_index": ACTIVE.key_index,
            "editor": {
                k: deepcopy(getattr(ACTIVE, k))
                for k in (
                    "contour",
                    "point",
                    "handle",
                    "landmark",
                    "selected",
                    "flat",
                    "rotation",
                    "orbit_preview",
                    "playing",
                )
            },
            "window": ACTIVE.origin.window,
            "layout": ACTIVE.editor.snapshot() if ACTIVE.editor else None,
        }
        end_session(remove_draft=False)


def resume():
    global SUSPENDED
    if not SUSPENDED:
        return None
    data, SUSPENDED = SUSPENDED, None
    try:
        window = data["window"]
        if window and window not in list(bpy.context.window_manager.windows):
            window = next(iter(bpy.context.window_manager.windows), None)
        kwargs = {"window": window} if window else {}
        with bpy.context.temp_override(**kwargs):
            s = start(bpy.context, data["project"], data["face"], layout=data.get("layout"))
            s.history = data["history"]
            s.select_keyframe(data["direction"], data["key_index"])
            for k, value in data.get("editor", {}).items():
                setattr(s, k, value)
            s.preview.render()
            s.sync_launcher()
    except Exception:
        traceback.print_exc()
    return None


@bpy.app.handlers.persistent
def save_post(_):
    if SUSPENDED and not bpy.app.timers.is_registered(resume):
        bpy.app.timers.register(resume, first_interval=0.05)


@bpy.app.handlers.persistent
def load_pre(_):
    global SUSPENDED
    if ACTIVE:
        ACTIVE.cancel_curve_edit()
        ACTIVE.safe_write_draft()
        end_session(remove_draft=False)
    SUSPENDED = None
    if bpy.app.timers.is_registered(resume):
        bpy.app.timers.unregister(resume)


HANDLERS = (
    ("save_pre", save_pre),
    ("save_post", save_post),
    ("save_post_fail", save_post),
    ("load_pre", load_pre),
)


def register_handlers():
    for name, callback in HANDLERS:
        handlers = getattr(bpy.app.handlers, name)
        if callback not in handlers:
            handlers.append(callback)


def unregister_handlers():
    load_pre(None)
    for name, callback in HANDLERS:
        handlers = getattr(bpy.app.handlers, name)
        if callback in handlers:
            handlers.remove(callback)
