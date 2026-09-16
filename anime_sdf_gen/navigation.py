"""Route viewport navigation to Blender, retaining its keymap and preferences."""

import bpy
from .viewport import window_region

NAVIGATION = {
    "view3d.rotate",
    "view3d.move",
    "view3d.zoom",
    "view3d.dolly",
    "view3d.view_axis",
    "view3d.view_orbit",
    "view3d.view_pan",
    "view3d.view_roll",
    "view3d.view_persportho",
    "view3d.view_selected",
    "view3d.view_all",
    "view3d.ndof_orbit",
    "view3d.ndof_orbit_zoom",
    "view3d.ndof_pan",
    "view3d.ndof_all",
}
LOCKED_NAVIGATION = {
    "view3d.move",
    "view3d.zoom",
    "view3d.view_pan",
    "view3d.ndof_pan",
    "view3d.view_selected",
    "view3d.view_all",
}
CAMERA = ("view_location", "view_rotation", "view_distance", "view_perspective")


def camera_state(view):
    return {
        name: (
            getattr(view, name).copy()
            if name in ("view_location", "view_rotation")
            else getattr(view, name)
        )
        for name in CAMERA
    }


def apply_camera(view, state):
    for name, value in state.items():
        setattr(view, name, value)


class NativeNavigation:
    def __init__(self, editor):
        self.editor = editor
        self.role = None
        self._matrix_busy = False
        self.drawing = False

    @property
    def host(self):
        return self.editor.native_area.spaces.active.region_3d

    def match(self, event):
        # keyconfigs.user is Blender's merged active keymap, including user edits.
        configs = bpy.context.window_manager.keyconfigs
        config = configs.user or configs.active
        keymap = config.keymaps.get("3D View") if config else None
        if not keymap:
            return None
        item = keymap.keymap_items.match_event(event)
        return item.idname if item and item.active and item.idname in NAVIGATION else None

    def running(self):
        ids = {name.replace("view3d.", "VIEW3D_OT_") for name in NAVIGATION}
        return any(op.bl_idname in ids for op in self.editor.window.modal_operators)

    def prepare(self, role, interactive=False):
        self.poll()
        if self.role != role:
            apply_camera(self.host, camera_state(self.editor.views[role]))
            self.role = role
        self.host.lock_rotation = self.editor.session.stage == "EDIT" and role == "AUTHOR"
        if interactive:
            self.host.update()
        self.editor.redraw()

    def poll(self):
        if not self.role or self._matrix_busy or not self.editor.ready:
            return
        slot = self.editor.views[self.role]
        before = camera_state(slot)
        apply_camera(slot, camera_state(self.host))
        slot.update()
        if before != camera_state(slot):
            self.editor.redraw()

    def stop(self):
        self.poll()
        self.role = None

    def command(self, role, operator, **kwargs):
        self.prepare(role)
        e = self.editor
        with bpy.context.temp_override(
            window=e.window, area=e.native_area, region=window_region(e.native_area)
        ):
            getattr(bpy.ops.view3d, operator)(**kwargs)
        self.poll()
        e.redraw()

    def matrices(self, slot):
        """Use Blender's camera/lens and only adapt its output aspect ratio."""
        e = self.editor
        if not e.ready or not self.drawing:
            return
        r = self.host
        before = camera_state(r)
        locked = r.lock_rotation
        self._matrix_busy = True
        try:
            apply_camera(r, camera_state(slot))
            with bpy.context.temp_override(
                window=e.window, area=e.native_area, region=window_region(e.native_area)
            ):
                r.update()
            slot.view_matrix = r.view_matrix.copy()
            projection = r.window_matrix.copy()
            native = window_region(e.native_area)
            projection[0][0] *= (native.width / max(1, native.height)) / (
                slot.region.width / max(1, slot.region.height)
            )
            slot.projection_matrix = projection
            slot.perspective_matrix = projection @ slot.view_matrix
        finally:
            try:
                apply_camera(r, before)
                r.lock_rotation = locked
                with bpy.context.temp_override(
                    window=e.window, area=e.native_area, region=window_region(e.native_area)
                ):
                    r.update()
            finally:
                self._matrix_busy = False
