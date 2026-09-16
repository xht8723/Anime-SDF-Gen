"""Guarded application edits shared by buttons, dialogs and curve input."""

from .core.messages import UserError

from copy import deepcopy
import time
from .core import curves, editing, model


class EditTransaction:
    def __init__(self, session, history=True, invalidate=True, stages=None):
        session.require_edit(stages)
        self.session = session
        self.before = session.checkpoint()
        self.history = history
        self.invalidate = invalidate
        self.active = True

    def __enter__(self):
        return self

    def commit(self):
        if not self.active:
            return
        s = self.session
        try:
            if s.project != self.before["project"]:
                if self.history:
                    s.history.push(self.before["project"])
                if self.invalidate:
                    s.changed()
                else:
                    s.draft_due = time.perf_counter() + 0.1
                    s.sync_launcher()
                    s.redraw()
        except Exception:
            self.cancel()
            raise
        self.active = False

    def cancel(self):
        if self.active:
            self.active = False
            self.session.rollback(self.before)

    def __exit__(self, kind, value, traceback):
        if kind:
            self.cancel()
        else:
            self.commit()
        return False


def handle_mode(s, mode):
    with s.edit(stages=("EDIT",)):
        for ci, pi in s.selected or {(s.contour, s.point)}:
            c = s.keyframe["contours"][ci]
            p = c["points"][pi]
            if mode == "FREE" and p["mode"] != "FREE":
                left, right = curves.handles(c, pi)
                p.update(left=(left - p["co"]).tolist(), right=(right - p["co"]).tolist())
            p["mode"] = mode


def point(s, xy, mode, left, right):
    with s.edit(stages=("EDIT",)):
        p = s.curve["points"][s.point]
        if mode == "FREE" and p["mode"] != "FREE":
            incoming, outgoing = curves.handles(s.curve, s.point)
            p.update(left=(incoming - p["co"]).tolist(), right=(outgoing - p["co"]).tolist())
        else:
            p.update(left=list(left), right=list(right))
        p.update(co=list(xy), mode=mode)
        for key in ("co", "left", "right"):
            if any(not (-100 <= v <= 100) for v in p[key]):
                raise UserError("Curve coordinates must be finite and within ±100 face units.")


def operation(s, value):
    with s.edit(stages=("EDIT",)):
        if not s.curve["closed"]:
            raise UserError("Select a closed curve first.")
        s.curve["operation"] = value


def transform(s, dx=0, dy=0, angle=0, scale=1):
    with s.edit(stages=("EDIT",)):
        editing.transform_contour(
            s.curve,
            dx,
            dy,
            angle,
            scale,
            s.project["alignment"]["height"] / s.project["alignment"]["width"],
        )


def reference(s, value):
    with s.edit(history=False, invalidate=False):
        s.project["authoring"]["reference"] = value
    if s.editor:
        s.editor.refresh_appearance()


def flat(s):
    s.require_edit()
    s.flat = not s.flat
    s.redraw()


def action(s, code):
    s.require_edit()
    if code == "NEXT":
        code = {"ORIENT": "SET_FRONT", "FIT": "FIT", "EDIT": "CONFIRM"}.get(s.stage, "")
    if code == "SET_FRONT":
        s.set_front()
        return
    if code == "FIT":
        s.fit(s.project["authoring"]["keyframe_count"])
        return
    if code == "CONFIRM":
        s.confirm()
        return
    if code in ("UNDO", "REDO"):
        with s.edit(history=False, invalidate=False):
            s.restore_project(
                s.history.undo(s.project) if code == "UNDO" else s.history.redo(s.project)
            )
        return
    if code == "PLAY":
        s.playing = not s.playing
        s.orbit_preview = True
        s.redraw()
        return
    if code == "FRAME":
        s.frame_view()
        return
    if code in ("FOCUS_AUTHOR", "FOCUS_PREVIEW"):
        if s.editor:
            s.editor.maximize(code.removeprefix("FOCUS_"))
        return
    if code == "BACK":
        if s.stage == "ORIENT":
            return
        with s.edit(history=s.stage != "CONFIRM", invalidate=False):
            if s.stage == "CONFIRM":
                s.project["authoring"]["stage"] = "EDIT"
                s.activate_stage()
            else:
                s.project["authoring"]["stage"] = "FIT" if s.stage == "EDIT" else "ORIENT"
                if s.stage == "FIT":
                    s.seed_landmarks()
                s.playing = s.orbit_preview = False
                s.changed()
        return
    if code in ("KEYFRAMES_MORE", "KEYFRAMES_LESS"):
        with s.edit(invalidate=False, stages=("ORIENT", "FIT")):
            count = s.project["authoring"]["keyframe_count"] + (
                1 if code == "KEYFRAMES_MORE" else -1
            )
            s.project["authoring"]["keyframe_count"] = max(
                model.MIN_KEYFRAMES, min(model.MAX_KEYFRAMES, count)
            )
        return
    with s.edit(stages=("FIT", "EDIT") if code == "MIRROR" else ("EDIT",)):
        if code == "TRIANGLE":
            curve = model.triangle()
            names = {c["name"] for c in s.keyframe["contours"]}
            number = 2
            while curve["name"] in names:
                curve["name"] = f"Triangle {number}"
                number += 1
            s.keyframe["contours"].append(curve)
            s.contour = len(s.keyframe["contours"]) - 1
            s.point = 0
        elif code == "DUPLICATE":
            if not s.curve["closed"]:
                raise UserError("Only closed shapes can be duplicated.")
            c = deepcopy(s.curve)
            c["id"] = model.uid()
            c["name"] += " copy"
            editing.transform_contour(c, dx=0.025, dy=0.025)
            s.keyframe["contours"].insert(s.contour + 1, c)
            s.contour += 1
        elif code == "DELETE_SHAPE":
            if not s.curve["closed"]:
                raise UserError("The main boundary cannot be deleted.")
            del s.keyframe["contours"][s.contour]
            s.contour = max(0, s.contour - 1)
        elif code == "TOGGLE":
            s.curve["enabled"] = not s.curve["enabled"]
        elif code in ("UP", "DOWN"):
            target = s.contour + (-1 if code == "UP" else 1)
            if s.contour == 0 or not 1 <= target < len(s.keyframe["contours"]):
                raise UserError("The main boundary stays first.")
            cs = s.keyframe["contours"]
            cs[s.contour], cs[target] = cs[target], cs[s.contour]
            s.contour = target
        elif code == "INSERT_POINT":
            segment = min(s.point, len(s.curve["points"]) - (1 if s.curve["closed"] else 2))
            s.point = curves.insert_point(s.curve, segment)
        elif code == "DELETE_POINT":
            if len(s.curve["points"]) <= (3 if s.curve["closed"] else 2):
                raise UserError("This contour needs its remaining points.")
            if not s.curve["closed"] and s.point in (0, len(s.curve["points"]) - 1):
                raise UserError("Keep the main boundary endpoints; move them instead.")
            del s.curve["points"][s.point]
            s.point = max(0, s.point - 1)
        elif code == "ADD_KEYFRAME":
            s.key_index = model.insert_keyframe(s.project, s.direction, s.key_index)
        elif code == "REMOVE_KEYFRAME":
            s.key_index = model.remove_keyframe(s.project, s.direction, s.key_index)
        elif code == "COPY_KEYFRAME":
            model.copy_previous(s.project, s.direction, s.key_index)
        elif code == "MIRROR":
            s.project["mirror_sweeps"] = not s.project["mirror_sweeps"]
        else:
            raise UserError("Unknown authoring action.")
        if code in ("TRIANGLE", "DUPLICATE", "UP", "DOWN"):
            s.reset_selection(whole_curve=True)
        elif code in (
            "DELETE_SHAPE",
            "INSERT_POINT",
            "DELETE_POINT",
            "ADD_KEYFRAME",
            "REMOVE_KEYFRAME",
            "COPY_KEYFRAME",
        ):
            s.reset_selection()
