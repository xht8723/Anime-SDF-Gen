"""Independent Blender image IO, smoothing cache, and export lifecycle checks."""

from pathlib import Path
import json, sys, time, traceback, hashlib
from unittest.mock import patch
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from anime_sdf_gen.core.image_io import read_png, read_exr
from anime_sdf_gen.core.thresholds import decode
import anime_sdf_gen
from anime_sdf_gen import session, source, preview
from anime_sdf_gen.core import files, model, smoothing
from anime_sdf_gen.core.jobs import run
from tests.fixture import fixture_face
from tests.samples import image
from tests.support import TestRun

RUN = TestRun("precision").prepare(blender=True)
OUT = RUN.out
DRAFTS = OUT / "drafts"
report = RUN.report
report["images"] = []
counts = lambda: {
    k: len(getattr(bpy.data, k))
    for k in (
        "objects",
        "meshes",
        "materials",
        "images",
        "scenes",
        "worlds",
        "collections",
        "node_groups",
    )
}


def independent_reload(path, expected):
    img = bpy.data.images.load(str(path), check_existing=False)
    try:
        img.colorspace_settings.name = "Non-Color"
        actual = np.empty(img.size[0] * img.size[1] * img.channels, np.float32)
        img.pixels.foreach_get(actual)
        actual = actual.reshape(img.size[1], img.size[0], img.channels)
        if expected.ndim == 2:
            np.testing.assert_allclose(actual[..., 0], expected, rtol=0, atol=1e-7)
            if actual.shape[2] >= 3:
                np.testing.assert_allclose(
                    actual[..., :3], np.repeat(expected[..., None], 3, axis=-1), rtol=0, atol=1e-7
                )
        else:
            np.testing.assert_allclose(actual[..., :3], expected, rtol=0, atol=1e-7)
        report["images"].append(
            {
                "name": Path(path).name,
                "is_float": img.is_float,
                "channels": img.channels,
                "size": list(img.size),
            }
        )
    finally:
        bpy.data.images.remove(img)


def tests():
    anime_sdf_gen.register()
    before = counts()
    fixture_hash = hashlib.sha256(RUN.fixture.read_bytes()).hexdigest()
    face = fixture_face(source)
    for bits in (8, 16, 32):
        for layout in ("packed", "mixed", "separate"):
            p = model.new_project(face.reference, face.alignment, resolution=512)
            p["settings"]["bit_depth"] = bits
            if layout == "mixed":
                model.set_packing(p, "character_left", "B")
                model.set_packing(p, "character_right", "SEPARATE")
            if layout == "separate":
                for name in model.MAP_LABELS:
                    model.set_packing(p, name, "SEPARATE")
            paths = files.export_bundle(p, image(), OUT / "io" / str(bits) / layout)
            canonical = files.quantize(image(), bits)
            if bits != 32:
                canonical = canonical.astype(float) / ((1 << bits) - 1)
            for path, info in zip(paths, files.load_project(paths[-1])["textures"]):
                independent_reload(path, files.packed_codes(canonical, info["channels"]))
    report["checks"].append(
        "Blender independently reloads packed, mixed and single-Y PNG8/16 and EXR32 with correct orientation, channels and numerical values"
    )
    assert counts() == before

    p = model.new_project(
        face.reference,
        face.alignment,
        preset="NOSE",
        resolution=512,
        output=str(OUT / "generated" / "face"),
    )
    s = session.start(bpy.context, p, face, handlers=False)
    deadline = time.perf_counter() + 90
    while s.preview.thresholds is None:
        s.tick()
        assert not s.error, s.error
        assert time.perf_counter() < deadline
    raw = s.preview.raw_thresholds
    copy = raw.copy()
    field_ids = {key: id(value) for key, value in s.preview.field_cache.items()}
    s.confirm()
    s.playing = False
    s.rotation = 83
    s.orbit_preview = True
    with patch.object(
        preview, "compile_steps", side_effect=AssertionError("smoothing must not recompile artwork")
    ):
        s.preview.set_smoothing(4)
        s.tick()
        assert s.preview.filter_job is None, "Debounce was skipped"
        assert not s.playing and s.rotation == 83
        s.preview.filter_due = 0
        s.preview.advance_filter(time.perf_counter(), time.perf_counter() + 0.000001)
        s.preview.set_smoothing(8)
        assert s.preview.filter_job is None
        s.preview.filter_due = 0
        while s.preview.filtered_key != (id(raw), 8, True):
            s.tick()
        np.testing.assert_array_equal(
            s.preview.thresholds, run(smoothing.smooth_steps(raw, 8, True))
        )
        assert not np.array_equal(s.preview.thresholds, raw)
        s.preview.render()
        direction, progress = model.rotation_sample(83)
        np.testing.assert_array_equal(
            s.preview.rgba[..., 0], decode(s.preview.thresholds[..., 0], progress)
        )
        assert s.rotation == 83 and not s.playing
        s.playing = True
        s.rotation = 111
        s.preview.set_smoothing(2)
        assert s.playing and s.rotation == 111
        s.preview.filter_due = 0
        while s.preview.filtered_key != (id(raw), 2, True):
            s.tick()
        s.preview.set_smoothing(0)
        assert s.preview.thresholds is raw and s.playing
        np.testing.assert_array_equal(raw, copy)
        assert field_ids == {key: id(value) for key, value in s.preview.field_cache.items()}
    report["checks"].append(
        "smoothing reuses raw thresholds and distance caches; debounce/stale cancellation, exact Off restore, mask decode and play/pause/rotation preservation pass"
    )

    # Only the exporter encoding changes with bit depth; smoothing is head-space.
    s.playing = False
    s.preview.set_smoothing(8)
    for bits in (8, 16, 32):
        s.project["settings"]["bit_depth"] = bits
        s.project["settings"]["output"] = str(OUT / "generated" / str(bits) / "face")
        s.export.start()
        deadline = time.perf_counter() + 90
        while s.export.job:
            s.export.advance(0.03, finish=False)
            assert time.perf_counter() < deadline
        assert s.export.paths and not s.error, s.error
        saved = files.load_project(s.export.paths[-1])
        assert saved["settings"]["smoothing"] == 8 and saved["settings"]["bit_depth"] == bits
        actual = (read_exr if bits == 32 else read_png)(s.export.paths[0])
        independent_reload(
            s.export.paths[0], actual if bits == 32 else actual.astype(float) / ((1 << bits) - 1)
        )
        assert np.isin(actual[..., 2], (0, 1) if bits == 32 else (0, (1 << bits) - 1)).all()
    report["checks"].append(
        "fixture exports with smoothing enabled in all three depths; Blender reload and binary coverage pass"
    )

    # Failure must keep the session editable and previous output intact.
    old = {Path(v): Path(v).read_bytes() for v in s.export.paths}
    with patch.object(
        files, "verify_steps", side_effect=IOError("injected EXR verification failure")
    ):
        s.export.start()
        while s.export.job:
            s.export.advance(0.03, finish=False)
    assert not s.busy and "injected" in str(s.error) and session.ACTIVE is s
    assert all(p.read_bytes() == data for p, data in old.items())
    s.error = ""
    s.export.start()
    while s.export.job:
        label, _ = next(s.export.job)
        if str(label).startswith("Encode face.exr"):
            break
    s.export.cancel()
    assert session.ACTIVE is s and not s.busy
    assert all(p.read_bytes() == data for p, data in old.items())
    assert not list((OUT / "generated/32").glob("*.tmp"))
    report["checks"].append(
        "EXR verification failure and mid-encoding cancellation retain prior outputs and the active editing session"
    )
    session.end_session(True)
    anime_sdf_gen.unregister()
    assert counts() == before
    assert (
        s.preview.raw_thresholds is None
        and s.preview.filter_job is None
        and not s.preview.field_cache
    )
    assert hashlib.sha256(RUN.fixture.read_bytes()).hexdigest() == fixture_hash
    report["fixture_sha256"] = fixture_hash
    report["checks"].append(
        "all owned resources are released and the original fixture hash is unchanged"
    )


started = time.perf_counter()
try:
    tests()
    report["status"] = "PASS"
except Exception:
    report.update(status="FAIL", traceback=traceback.format_exc())
    traceback.print_exc()
finally:
    if session.ACTIVE:
        session.end_session(False)
    report["elapsed_seconds"] = time.perf_counter() - started
    (OUT / "precision.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
if report["status"] != "PASS":
    raise RuntimeError(report.get("traceback", "Precision test failed"))
