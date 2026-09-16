"""Owned Blender datablocks and the untouched source-window context."""

import uuid
import traceback
import bpy

OWNER_KEY = "anime_sdf_gen_session"


class Registry:
    def __init__(self):
        self.id = uuid.uuid4().hex
        self.ids, self.draw_handlers = [], []

    def own(self, kind, block):
        block[OWNER_KEY] = self.id
        self.ids.append((kind, block))
        return block

    def dispose(self):
        for handler, stage in self.draw_handlers:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(handler, stage)
            except (ValueError, ReferenceError):
                pass
        self.draw_handlers.clear()
        ui, remaining = [], []
        for kind, block in self.ids:
            if kind in ("screens", "workspaces"):
                try:
                    if block.get(OWNER_KEY) == self.id:
                        ui.append(block)
                except ReferenceError:
                    pass
            else:
                remaining.append((kind, block))
        self.ids = remaining
        if ui:
            # UI IDs have no collection.remove API. Their window has already
            # been closed/rebound; the original workspace is never in this set.
            bpy.data.batch_remove(ui)
        # First unlink owned objects/scenes, then their dependent data. No purge.
        order = {
            "objects": 0,
            "scenes": 1,
            "meshes": 2,
            "materials": 3,
            "worlds": 4,
            "node_groups": 5,
            "images": 6,
            "collections": 7,
        }
        for kind, block in sorted(self.ids, key=lambda x: order.get(x[0], 8)):
            try:
                if block.get(OWNER_KEY) != self.id:
                    continue
                collection = getattr(bpy.data, kind)
                if block.use_fake_user:
                    block.use_fake_user = False
                if kind in ("objects", "scenes", "collections"):
                    collection.remove(block, do_unlink=True)
                elif block.users == 0:
                    collection.remove(block)
                else:
                    # A user explicitly adopted a preview resource elsewhere.
                    # Preserve that reference instead of destroying unrelated work.
                    del block[OWNER_KEY]
            except (ReferenceError, RuntimeError):
                traceback.print_exc()
        self.ids.clear()


class OriginContext:
    """Only the source references needed for extraction and last-window recovery."""

    def __init__(self, context):
        self.window = context.window
        self.scene = context.window.scene if context.window else context.scene
        self.view_layer = context.view_layer
        self.workspace = context.workspace if context.window else None

    def override(self):
        kwargs = {"scene": self.scene, "view_layer": self.view_layer}
        if self.window and self.window in list(bpy.context.window_manager.windows):
            kwargs["window"] = self.window
        return bpy.context.temp_override(**kwargs)
