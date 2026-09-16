"""Native close, disable and last-window recovery in disposable Blender."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import anime_sdf_gen
from anime_sdf_gen import session, source
from anime_sdf_gen.core import model
from anime_sdf_gen.resources import OWNER_KEY
from tests.fixture import fixture_face
from tests.support import TestRun
from tests.ui_helpers import wait_for
from tests.ui_runner import run

RUN = TestRun("window-lifecycle").prepare(blender=True)
KINDS = (
    "objects",
    "meshes",
    "materials",
    "images",
    "scenes",
    "worlds",
    "collections",
    "node_groups",
    "screens",
    "workspaces",
)


def counts():
    return {k: len(getattr(bpy.data, k)) for k in KINDS}


def clean():
    assert not [(k, v.name) for k in KINDS for v in getattr(bpy.data, k) if OWNER_KEY in v]


def workflow():
    anime_sdf_gen.register()
    before = counts()
    fixture_hash = RUN.fixture_hash()
    face = fixture_face(source)

    def create():
        return session.start(
            bpy.context,
            model.new_project(
                face.reference, face.alignment, resolution=512, output=str(RUN.out / "face")
            ),
            face,
        )

    s = create()
    yield from wait_for(lambda: s.editor.ready)
    window = s.editor.window
    with bpy.context.temp_override(window=window):
        bpy.ops.wm.window_close()
    yield from wait_for(lambda: session.ACTIVE is None)
    assert s.closed and not s.registry.ids and not s.registry.draw_handlers
    assert counts() == before
    clean()
    RUN.report["checks"].append("Native popup close disposes owned resources and timers")

    s = create()
    yield from wait_for(lambda: s.editor.ready)
    anime_sdf_gen.unregister()
    yield 0.2
    assert session.ACTIVE is None and counts() == before
    clean()
    RUN.report["checks"].append("Disabling an active popup restores resources and callbacks")
    anime_sdf_gen.register()

    s = create()
    yield from wait_for(lambda: s.editor.ready)
    original_scene = s.origin.scene
    original_workspace = s.origin.workspace
    window = s.editor.window
    with bpy.context.temp_override(window=RUN.origin):
        bpy.ops.wm.window_close()
    yield 0.3
    assert len(bpy.context.window_manager.windows) == 1 and session.ACTIVE is s
    with s.origin.override():
        assert bpy.context.scene == original_scene
    RUN.origin = window
    s.close_requested = True
    yield from wait_for(lambda: session.ACTIVE is None)
    yield 0.2
    assert len(bpy.context.window_manager.windows) == 1
    assert window.scene == original_scene and window.workspace == original_workspace
    assert counts() == before
    clean()
    assert RUN.fixture_hash() == fixture_hash
    anime_sdf_gen.unregister()
    RUN.report["checks"].append(
        "Closing the last popup restores the source scene/workspace without quitting Blender"
    )


run(workflow, RUN, "window-lifecycle.json")
