"""Regression checks for session ownership, atomic edits and export inputs."""

from pathlib import Path
from copy import deepcopy
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import anime_sdf_gen
from anime_sdf_gen import session, source, ui, commands
from anime_sdf_gen.ui_guard import bind
from anime_sdf_gen.core.files import load_project
from anime_sdf_gen.core import model, editing
from tests.fixture import fixture_face
from tests.support import TestRun

RUN = TestRun("guards").prepare(blender=True)
OUT = RUN.out
DRAFTS = OUT / "drafts"
failures = []


def check(name, condition):
    if not condition:
        failures.append(name)


anime_sdf_gen.register()
try:
    face = fixture_face(source)
    s = session.start(
        bpy.context,
        model.new_project(
            face.reference, face.alignment, resolution=512, output=str(OUT / "active")
        ),
        face,
        handlers=False,
    )
    original = deepcopy(s.project)
    other = deepcopy(s.project)
    other["id"] = model.uid()
    other["settings"]["output"] = str(OUT / "other")
    with patch.object(ui, "load_project", return_value=other), patch.object(
        source, "from_reference", return_value=face
    ):
        result = bpy.ops.anime_sdf_gen.open_project(filepath=str(OUT / "not-read.json"))
    check(
        "rejected open preserves active project", result == {"CANCELLED"} and s.project == original
    )
    s.project = original
    bpy.ops.anime_sdf_gen.action(action="TRIANGLE")
    original = deepcopy(s.project)
    s.export.job = (item for item in ())
    result = bpy.ops.anime_sdf_gen.transform(dx=0.05)
    check(
        "busy transform is rejected without mutation",
        result == {"CANCELLED"} and s.project == original,
    )
    s.export.close()
    s.project = original
    s.project["alignment"]["height"] = 2 * s.project["alignment"]["width"]
    frame = deepcopy(s.keyframe)
    t = editing.Transform(
        frame, {(s.contour, i) for i in range(len(s.curve["points"]))}, "ROTATE", (0.5, 0.3), 2.0
    )
    t.number = "90"
    expected = t.evaluate()["contours"][s.contour]
    result = bpy.ops.anime_sdf_gen.transform(angle=90)
    check(
        "numeric rotation equals keyboard rotation",
        result == {"FINISHED"}
        and np.allclose(
            [p["co"] for p in s.curve["points"]], [p["co"] for p in expected["points"]]
        ),
    )
    s.project["alignment"] = deepcopy(face.alignment)
    # Every successful command is one undo item; invalid/no-op commands are atomic.
    before = deepcopy(s.project)
    undo = len(s.history.undo_stack)
    commands.transform(s, dx=0.01)
    check("one command creates one undo entry", len(s.history.undo_stack) == undo + 1)
    commands.action(s, "UNDO")
    check("undo restores the complete artwork", s.project == before)
    undo = len(s.history.undo_stack)
    commands.transform(s)
    check("identity numeric edit does not add history", len(s.history.undo_stack) == undo)
    before = s.checkpoint()
    try:
        commands.point(s, [float("nan"), 0], "FREE", [0, 0], [0, 0])
    except ValueError:
        pass
    check(
        "failed point edit rolls back project selection and history",
        s.project == before["project"]
        and s.selected == before["selected"]
        and s.history.undo_stack == before["undo"],
    )

    pending = SimpleNamespace(dx=0.1, dy=0, angle=0, scale=1)
    bind(pending, s, target=True)
    s.point = (s.point + 1) % len(s.curve["points"])
    before = deepcopy(s.project)
    check(
        "stale point/shape target is rejected",
        ui.ANIME_SDF_GEN_OT_transform.execute(pending, bpy.context) == {"CANCELLED"}
        and s.project == before,
    )
    s.confirm()
    pending = SimpleNamespace()
    bind(pending, s, snapshot=True)
    s.project["settings"]["output"] = str(OUT / "new-name")
    before = deepcopy(s.project)
    check(
        "overwrite confirmation rejects changed output settings",
        ui.ANIME_SDF_GEN_OT_generate.execute(pending, bpy.context) == {"CANCELLED"}
        and not s.busy
        and s.project == before,
    )

    # Delayed submissions from a disposed session may never target its replacement.
    stale = []
    for cls, values in [
        (ui.ANIME_SDF_GEN_OT_settings, dict(section="FILENAME", filename="stale")),
        (ui.ANIME_SDF_GEN_OT_destination, dict(filepath=str(OUT / "stale.png"))),
        (ui.ANIME_SDF_GEN_OT_save_draft, dict(filepath=str(OUT / "stale.sdfproject.json"))),
        (ui.ANIME_SDF_GEN_OT_generate, {}),
        (ui.ANIME_SDF_GEN_OT_transform, dict(dx=0.1, dy=0, angle=0, scale=1)),
    ]:
        op = SimpleNamespace(**values)
        bind(op, s)
        stale.append((cls, op))
    session.end_session(True)
    s = session.start(
        bpy.context,
        model.new_project(
            face.reference, face.alignment, resolution=512, output=str(OUT / "snapshot")
        ),
        face,
        handlers=False,
    )
    s.confirm()
    before = deepcopy(s.project)
    for cls, op in stale:
        check(
            "stale " + cls.bl_idname + " cannot mutate replacement",
            cls.execute(op, bpy.context) == {"CANCELLED"}
            and s.project == before
            and session.ACTIVE is s,
        )
    s.export.start()
    job = s.export.job
    try:
        s.export.start()
    except ValueError:
        pass
    check("repeat export retains original job", s.export.job is job)
    s.export.cancel()
    expected = deepcopy(s.project)
    s.export.start()
    s.project["settings"].update(bit_depth=32, smoothing=8, output=str(OUT / "wrong"))
    while s.busy:
        s.export.advance(0.03, finish=False)
    check(
        "export snapshot succeeds independently of subsequent project mutation",
        bool(s.export.paths) and not s.error,
    )
    saved = load_project(s.export.paths[-1])
    check(
        "exported settings come from the starting snapshot",
        saved["settings"] == expected["settings"],
    )
finally:
    session.end_session(True)
    anime_sdf_gen.unregister()
report = {"status": "FAIL" if failures else "PASS", "failures": failures}
(OUT / "guards.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report))
if failures:
    raise AssertionError(failures)
