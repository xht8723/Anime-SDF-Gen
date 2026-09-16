"""Popup event routing and recoverable modal input."""

import time
import traceback
import bpy
import numpy as np
from . import session
from .commands import action
from .curve_input import CurveInput
from .interface import dispatch
from .navigation import LOCKED_NAVIGATION
from .viewport import scale, window_region
from .canvas import inside, pick


class ANIME_SDF_GEN_OT_interact(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.interact"
    bl_label = "Anime SDF Gen Interaction"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        s = session.ACTIVE
        if not s or s._modal_running:
            return {"CANCELLED"}
        self.owner = s.registry.id
        self.drag = None
        self.transaction = None
        self.last_draw = 0.0
        s.curve_edit = CurveInput(s)
        self._event_timer = context.window_manager.event_timer_add(0.025, window=context.window)
        s._event_timer = self._event_timer
        s._modal_running = True
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        s = session.ACTIVE
        if s and s.registry.id == self.owner:
            s.cancel_curve_edit()
            s._modal_running = False
            s.dragging = False
        if getattr(self, "_event_timer", None):
            try:
                context.window_manager.event_timer_remove(self._event_timer)
            except (ReferenceError, ValueError):
                pass
            self._event_timer = None
        return {"FINISHED"}

    def modal(self, context, event):
        try:
            return self._modal(context, event)
        except Exception as exc:
            traceback.print_exc()
            s = session.ACTIVE
            if not s or s.closed:
                return {"FINISHED"}
            if s.registry.id != self.owner:
                return self._finish(context)
            try:
                s.cancel_curve_edit()
                if self.transaction:
                    self.transaction.cancel()
                else:
                    s.normalize_selection()
            except Exception:
                traceback.print_exc()
            self.transaction = None
            self.drag = None
            s.dragging = False
            s.playing = False
            s.notify_error(exc)
            # Never terminate the only input handler because an edit failed.
            return {"RUNNING_MODAL"}

    def _modal(self, context, event):
        s = session.ACTIVE
        if not s or s.closed or s.registry.id != self.owner:
            return self._finish(context)
        if not s.editor or not s.editor.owns_context(context):
            return {"PASS_THROUGH"}
        e = s.editor
        native = window_region(e.native_area)
        e.navigation.poll()
        if event.type == "WINDOW_DEACTIVATE":
            e.clear_hover()
            s.cancel_curve_edit()
            if self.drag and self.drag[0] == "smoothing":
                s.preview.set_smoothing(self.drag[1])
            if self.transaction:
                self.transaction.cancel()
            self.transaction = self.drag = None
            s.dragging = False
            return {"PASS_THROUGH"}
        if event.type == "TIMER":
            return {"PASS_THROUGH"}
        # Blender's modal orbit/pan/zoom receives its own moves, snapping keys,
        # release and Esc. Its actual camera is mirrored by the draw/timer path.
        if e.navigation.running():
            e.clear_hover()
            return {"PASS_THROUGH"}
        s.normalize_selection()
        mouse = np.array([event.mouse_x - native.x, event.mouse_y - native.y], dtype=float)
        e.resize(native)
        if self.drag and self.drag[0] == "smoothing":
            if event.type in ("ESC", "RIGHTMOUSE") and event.value == "PRESS":
                s.preview.set_smoothing(self.drag[1])
                self.drag = None
            elif event.type in ("MOUSEMOVE", "LEFTMOUSE"):
                _, previous, x, w = self.drag
                s.preview.set_smoothing(round(float(np.clip((mouse[0] - x) / w * 8, 0, 8)), 2))
                if event.type == "LEFTMOUSE" and event.value == "RELEASE":
                    self.drag = None
            e.redraw()
            return {"RUNNING_MODAL"}
        role = next(
            (
                name
                for name in ("AUTHOR", "PREVIEW")
                if name in e.boxes and e.views[name].region.contains(mouse)
            ),
            None,
        )
        if self.drag and self.drag[0] not in ("rotation", "divider"):
            role = self.drag_role
        if s.curve_edit.active:
            role = "AUTHOR"
        view = e.views.get(role)
        region = view.region if view else None
        local = mouse - np.array([region.x, region.y]) if region else None
        if s.curve_edit.active and s.curve_edit.modal(event, local, region, view):
            return {"RUNNING_MODAL"}
        if event.ctrl and event.type == "Z" and event.value == "PRESS":
            e.clear_hover()
            if not s.busy and not self.drag:
                action(s, "REDO" if event.shift else "UNDO")
            return {"RUNNING_MODAL"}
        if event.ctrl and event.type == "S" and event.value == "PRESS" and not self.drag:
            e.clear_hover()
            s.save_requested = True
            return {"RUNNING_MODAL"}
        if (
            event.ctrl
            and event.type == "SPACE"
            and event.value == "PRESS"
            and role
            and not self.drag
        ):
            e.maximize(role)
            return {"RUNNING_MODAL"}
        if not self.drag:
            hovered = next(
                (
                    widget
                    for widget in reversed(e.widgets)
                    if inside(mouse, widget["box"])
                    and ("clip" not in widget or inside(mouse, widget["clip"]))
                ),
                None,
            )
            hover = hovered["key"] if hovered else None
            e.set_hover(hover, mouse)
            if event.type == "LEFTMOUSE" and event.value == "PRESS" and hovered:
                e.clear_hover()
                if hovered["enabled"]:
                    if hovered["key"] == "SMOOTHING_SLIDER":
                        bx, by, bw, bh = hovered["box"]
                        x, w = bx + 12 * scale(), max(1, bw - 24 * scale())
                        self.drag = ("smoothing", s.project["settings"]["smoothing"], x, w)
                        s.preview.set_smoothing(
                            round(float(np.clip((mouse[0] - x) / w * 8, 0, 8)), 2)
                        )
                        return {"RUNNING_MODAL"}
                    e.navigation.stop()
                    dispatch(s, hovered["key"])
                    self.transaction = None
                    if not s.closed:
                        s.redraw()
                return {"RUNNING_MODAL"}
        if s.busy:
            return {"RUNNING_MODAL"}
        if (
            event.type in ("WHEELUPMOUSE", "WHEELDOWNMOUSE")
            and event.value == "PRESS"
            and not self.drag
        ):
            e.clear_hover()
            direction = 1 if event.type == "WHEELUPMOUSE" else -1
            if e.warning_bounds and e.warning_bounds.contains(mouse):
                e.warning_scroll = max(
                    0, min(e.warning_scroll_max, e.warning_scroll - direction * 36 * scale())
                )
            elif e.boxes["PANEL"].contains(mouse):
                e.panel_scroll = max(
                    0,
                    min(
                        getattr(e, "panel_scroll_max", 0), e.panel_scroll - direction * 48 * scale()
                    ),
                )
            elif s.stage == "EDIT" and e.boxes["SHELF"].contains(mouse):
                s.keyframe_scroll = max(0, getattr(s, "keyframe_scroll", 0) - direction)
            else:
                direction = None
            if direction is not None:
                e.redraw()
                return {"RUNNING_MODAL"}
        if not self.drag and view:
            navigation = e.navigation.match(event)
            if navigation:
                e.clear_hover()
                if s.stage == "EDIT" and role == "AUTHOR" and navigation not in LOCKED_NAVIGATION:
                    return {"RUNNING_MODAL"}
                e.navigation.prepare(role, interactive=True)
                return {"PASS_THROUGH"}
        if not self.drag and s.stage == "EDIT" and role == "AUTHOR":
            if s.curve_edit.modal(event, local, region, view):
                e.clear_hover()
                return {"RUNNING_MODAL"}
        if not self.drag and event.type == "LEFTMOUSE" and event.value == "PRESS":
            e.clear_hover()
            e.navigation.stop()
            divider = e.boxes.get("DIVIDER")
            if divider and inside(
                mouse,
                (divider.x - 4 * scale(), divider.y, divider.width + 8 * scale(), divider.height),
            ):
                self.drag = ("divider",)
                return {"RUNNING_MODAL"}
            if s.stage in ("EDIT", "CONFIRM"):
                x, y, w, h = e.boxes["SLIDER"]
                margin = 6 * scale()
                # Include the endpoint knob, even when DPI scaling places its
                # center between integer mouse coordinates.
                if inside(mouse, (x - margin, y, w + 2 * margin, h)):
                    self.drag = ("rotation",)
                    s.playing = False
        if self.drag and self.drag[0] in ("divider", "rotation"):
            mode = self.drag[0]
            if event.type == "MOUSEMOVE" or (mode == "rotation" and event.type == "LEFTMOUSE"):
                if mode == "divider":
                    e.split_ratio = float(np.clip(mouse[0] / e.boxes["SHELF"].width, 0.25, 0.75))
                else:
                    x, y, w, h = e.boxes["SLIDER"]
                    s.rotation = float(np.clip((mouse[0] - x) / w * 360, 0, 360))
                    s.orbit_preview = True
                    s.preview.render()
                    s.sync_launcher()
                e.redraw()
            if (
                event.type in ("LEFTMOUSE", "MIDDLEMOUSE") and event.value == "RELEASE"
            ) or event.type == "ESC":
                self.drag = None
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS" and region and s.stage == "FIT":
            hit = pick(s, local, view) or ("landmark", s.landmark)
            self.transaction = s.edit(invalidate=False, stages=("FIT",))
            if not s.pick_landmark(view, local, hit[1]):
                self.transaction = None
                return {"RUNNING_MODAL"}
            s.landmark = hit[1]
            self.drag = hit
            self.drag_role = role
            s.dragging = True
            s.playing = False
            s.sync_launcher()
            s.redraw()
            return {"RUNNING_MODAL"}
        if self.drag:
            if event.type == "ESC" and event.value == "PRESS":
                self.transaction.cancel()
                s.dragging = False
                self.drag = None
                self.transaction = None
                return {"RUNNING_MODAL"}
            if event.type in ("MOUSEMOVE", "LEFTMOUSE"):
                s.pick_landmark(view, local, s.landmark)
                released = event.type == "LEFTMOUSE" and event.value == "RELEASE"
                now = time.perf_counter()
                if released or now - self.last_draw >= 1 / 60:
                    s.changed(dragging=not released)
                    self.last_draw = now
                if released:
                    s.dragging = False
                    self.drag = None
                    self.transaction.commit()
                    self.transaction = None
                    s.redraw()
                return {"RUNNING_MODAL"}
        # The popup owns its keymap. N/T, native fullscreen, editor switches and
        # transform keys cannot expose Blender chrome or edit the preview mesh.
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        self._finish(context)
