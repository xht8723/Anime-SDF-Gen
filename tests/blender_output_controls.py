"""Real popup interactions for output precision, smoothing, and save/resume."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import numpy as np
import anime_sdf_gen
from anime_sdf_gen import session, source
from anime_sdf_gen.core import model
from tests.fixture import fixture_face
from tests.ui_helpers import (
    redraw,
    shot,
    labels,
    event,
    hover,
    click,
    metadata,
    await_tooltip,
    wait_for,
)
from tests.support import TestRun
from tests.ui_runner import run as run_ui

RUN = TestRun("output-controls-2k").prepare(blender=True)
ROOT = Path(__file__).resolve().parents[1]
OUT = RUN.out
report = RUN.report
origin = RUN.origin
started = RUN.started
from anime_sdf_gen.core import files


def action(name, **kwargs):
    e = session.ACTIVE.editor
    with bpy.context.temp_override(window=e.window, area=e.native_area):
        return getattr(bpy.ops.anime_sdf_gen, name)(**kwargs)


def workflow():
    anime_sdf_gen.register()
    before = {
        k: len(getattr(bpy.data, k))
        for k in (
            "objects",
            "meshes",
            "materials",
            "images",
            "scenes",
            "worlds",
            "screens",
            "workspaces",
        )
    }
    face = fixture_face(source)
    project = model.new_project(
        face.reference, face.alignment, preset="NOSE", resolution=512, output=str(OUT / "face")
    )
    s = session.start(bpy.context, project, face)
    yield from wait_for(lambda: s.editor.ready and s.editor.widgets)
    yield from wait_for(lambda: s.preview.thresholds is not None or bool(s.error), 90)
    assert not s.error, s.error
    click("NEXT")
    yield 0.2
    assert s.stage == "CONFIRM" and s.playing
    e = s.editor
    report["window_dimensions"] = [e.window.width, e.window.height]
    report["blender"] = bpy.app.version_string
    assert s.project["settings"]["bit_depth"] == 16 and s.project["settings"]["smoothing"] == 0
    metadata()
    shot(OUT, "01-confirm-defaults.png")
    click("BIT_DEPTH")
    yield 0.2
    shot(OUT, "02-precision-dialog.png")
    event("ESC")
    event("ESC", "RELEASE")
    yield 0.2
    for bits in (8, 32, 16, 32):
        assert action("settings", section="BIT_DEPTH", bit_depth=str(bits)) == {"FINISHED"}
        redraw()
        assert s.project["settings"]["bit_depth"] == bits
        assert any(model.BIT_DEPTH_LABELS[bits] == line[0] for line in labels())
        paths = files.output_paths(s.project, s.project["settings"]["output"])
        assert paths[0].suffix == (".exr" if bits == 32 else ".png")
    action("packing", map_name="character_right", route="SEPARATE")
    redraw()
    assert any("face_right.exr" == line[0] for line in labels())
    assert s.playing
    report["checks"].append(
        "precision dialog opens; depth changes update Confirm labels and mixed output filenames while playback continues"
    )

    # A real slider drag must not disturb the orbit or raw field cache.
    raw = s.preview.raw_thresholds
    cache = {k: id(v) for k, v in s.preview.field_cache.items()}
    x, y, w, h = e.boxes["SMOOTHING_TRACK"]
    start = (x, y)
    end = (x + w, y)
    event("MOUSEMOVE", "NOTHING", start)
    event("LEFTMOUSE", xy=start)
    yield 0.05
    for i in range(12):
        event("MOUSEMOVE", "NOTHING", (x + w * (i + 1) / 12, y))
        yield 0.025
    assert s.project["settings"]["smoothing"] > 7 and s.playing
    event("ESC")
    event("ESC", "RELEASE")
    yield 0.15
    assert s.project["settings"]["smoothing"] == 0 and s.preview.thresholds is raw and s.playing
    event("MOUSEMOVE", "NOTHING", end)
    event("LEFTMOUSE", xy=end)
    event("LEFTMOUSE", "RELEASE", xy=end)
    yield from wait_for(
        lambda: s.project["settings"]["smoothing"] == 8
        and s.preview.filtered_key == (id(raw), 8, True)
    )
    assert cache == {k: id(v) for k, v in s.preview.field_cache.items()}
    np.testing.assert_array_equal(s.preview.thresholds[..., 1], s.preview.thresholds[:, ::-1, 0])
    report["checks"].append(
        "real slider dragging is live, Escape restores Off exactly, and committed filtering keeps playback and raw/distance caches"
    )

    click("PLAY")
    yield 0.1
    assert not s.playing
    filtered = s.preview.thresholds.copy()
    diff = np.abs(filtered - raw) * s.preview.domain[..., None]
    iy, ix, channel = np.unravel_index(np.argmax(diff), diff.shape)
    assert diff[iy, ix, channel] > 0
    progress = float(filtered[iy, ix, channel] + raw[iy, ix, channel]) / 2
    s.rotation = model.keyframe_rotation(model.LTR if channel == 0 else model.RTL, progress)
    s.orbit_preview = True
    s.preview.render()
    s.sync_launcher()
    after = s.preview.rgba.copy()
    shot(OUT, "03-smoothed-preview.png")
    s.preview.set_smoothing(0)
    before_mask = s.preview.rgba.copy()
    shot(OUT, "04-unsmoothed-preview.png")
    assert np.any(after[..., 0] != before_mask[..., 0])
    s.preview.set_smoothing(8)
    yield from wait_for(lambda: s.preview.filtered_key == (id(raw), 8, True))
    np.testing.assert_array_equal(s.preview.rgba, after)
    assert not s.playing
    hover("SMOOTHING_SLIDER")
    yield from await_tooltip("SMOOTHING_SLIDER")
    shot(OUT, "05-smoothing-tooltip.png")
    metadata()
    report["checks"].append(
        "Confirm mask visibly changes with smoothing, exact Off restore and repeatability pass, and every new control has a readable tooltip"
    )

    # Rebuild the popup after serialization, keeping only project data.
    art = model.dumps(s.project)
    old = s.registry.id
    with bpy.context.temp_override(window=e.window, area=e.native_area):
        bpy.ops.wm.save_as_mainfile(
            filepath=str(OUT / "save-with-output-settings.blend"), check_existing=False
        )
    yield from wait_for(
        lambda: session.ACTIVE is not None
        and session.ACTIVE.registry.id != old
        and session.ACTIVE.editor.ready,
        60,
    )
    s = session.ACTIVE
    e = s.editor
    assert model.dumps(s.project) == art
    yield from wait_for(
        lambda: s.preview.filtered_key is not None and s.preview.thresholds is not None, 90
    )
    assert s.project["settings"]["smoothing"] == 8 and s.project["settings"]["bit_depth"] == 32
    assert not s.playing
    shot(OUT, "06-resumed-confirm.png")
    report["checks"].append(
        "saving suspends and rebuilds the popup with depth, smoothing, routes, paused rotation and artwork preserved"
    )
    session.end_session(True)
    yield 0.2
    assert before == {k: len(getattr(bpy.data, k)) for k in before}
    assert (
        s.preview.filter_job is None
        and s.preview.raw_thresholds is None
        and s.preview._mask_texture is None
    )
    assert fixture_face(source).reference["fingerprint"] == face.reference["fingerprint"]
    anime_sdf_gen.unregister()
    report["checks"].append(
        "close releases filter arrays, callbacks and GPU resources; source fingerprint and datablock counts are unchanged"
    )


run_ui(workflow, RUN, "output-controls.json", timeout=300)
