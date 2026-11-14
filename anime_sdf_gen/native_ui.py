"""Finish the opening gesture before handing input to native Blender UI."""

from types import SimpleNamespace
import bpy
from .canvas import widget_at
from .viewport import window_region

SETTINGS_ACTIONS = {
    "RESOLUTION",
    "BIT_DEPTH",
    "SMOOTHING",
    "FILENAME",
    "SOURCE",
    "BAKE_UV",
    "KEYFRAME_COUNT",
    "POINT",
    "SHAPE_NAME",
}
NATIVE_ACTIONS = SETTINGS_ACTIONS | {"DESTINATION", "DRAFT", "GENERATE", "TRANSFORM", "REFIT"}


class NativeUI:
    def __init__(self, session):
        self.session = session
        self.pending = None

    def arm(self, key, button="LEFTMOUSE", widget=True):
        from .ui_guard import bind

        s = self.session
        s.require_edit()
        if self.pending is not None:
            return
        request = SimpleNamespace(key=key, button=button, widget=widget, ready=False)
        bind(
            request, s, target=key in {"POINT", "TRANSFORM", "SHAPE_NAME"},
            snapshot=key in {"GENERATE", "REFIT"},
        )
        self.pending = request
        s.editor.clear_hover()

    def cancel(self):
        self.pending = None

    def handle_event(self, event, mouse):
        from .ui_guard import current

        request = self.pending
        if request is None:
            return False
        if current(request) is not self.session or (
            event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS"
        ):
            self.cancel()
        elif event.type == request.button and event.value in {"PRESS", "DOUBLE_CLICK"}:
            # A second press can arrive before the queued timer tick. Finish
            # that gesture too so its release cannot dismiss the new dialog.
            request.ready = False
        elif event.type == request.button and event.value == "RELEASE":
            if request.widget:
                hovered = widget_at(self.session.editor.widgets, mouse)
                if not hovered or hovered["key"] != request.key or not hovered["enabled"]:
                    self.cancel()
                    return True
            request.ready = True
        # Consume the release and any intervening clicks; Blender must not see
        # the opening gesture inside the dialog it is about to create.
        return True

    def advance(self):
        from .ui_guard import current
        from .interface import dispatch

        request = self.pending
        if request is None or not request.ready:
            return
        self.pending = None
        s = self.session
        if current(request) is not s:
            return
        e = s.editor
        if not e or not e.ready or not e.alive():
            return
        if request.widget and not any(
            w["key"] == request.key and w["enabled"] for w in e.widgets
        ):
            return
        e.navigation.stop()
        e.clear_hover()
        with bpy.context.temp_override(
            window=e.window, area=e.native_area, region=window_region(e.native_area)
        ):
            dispatch(s, request.key)
