"""Default-resolution export benchmark, writing only to build/validation."""

import json
from pathlib import Path
import sys
import time
import traceback
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from anime_sdf_gen.core import editing
import anime_sdf_gen
from anime_sdf_gen import session, source
from tests.fixture import fixture_face
from anime_sdf_gen.core import model
from anime_sdf_gen.core.image_io import read_png, read_exr
from tests.support import TestRun

RUN = TestRun("full-export").prepare(blender=True)
OUT = RUN.out
DRAFTS = OUT / "drafts"
args = RUN.extra
size = int(args[0]) if args else 2048
bits = int(args[1]) if len(args) > 1 else 16
smooth = float(args[2]) if len(args) > 2 else 0
stem = f"face_sdf_{size}_{bits}_{smooth:g}"

try:
    anime_sdf_gen.register()
    p = bpy.context.window_manager.anime_sdf_gen
    p.resolution = "2048"
    p.output = str(OUT / stem)
    face = fixture_face(source)
    project = model.new_project(face.reference, face.alignment, output=str(OUT / stem))
    project["settings"].update(resolution=size, bit_depth=bits, smoothing=smooth)
    cutout = model.triangle()
    cutout["operation"] = "REMOVE"
    editing.transform_contour(cutout, dx=-0.14)
    model.sweep(project, model.LTR)[6]["contours"].append(cutout)
    model.synchronize_mirror(project)
    s = session.start(bpy.context, project, face)
    t = time.perf_counter()
    s.confirm()
    s.export.start()
    longest = 0.0
    last = ""
    while s.busy:
        start = time.perf_counter()
        s.export.advance(0.01)
        longest = max(longest, time.perf_counter() - start)
        stage = str(s.export.message).split(" · ")[0]
        if stage != last:
            print(stage, flush=True)
            last = stage
    assert s.export.paths, s.error
    png = (read_exr if bits == 32 else read_png)(s.export.paths[0])
    assert png.shape == (size, size, 3)
    assert np.unique(png[..., 0]).size > (100 if bits == 8 else 4096)
    img = bpy.data.images.load(s.export.paths[0], check_existing=False)
    try:
        img.colorspace_settings.name = "Non-Color"
        actual = np.empty(size * size * 4, np.float32)
        img.pixels.foreach_get(actual)
        expected = png if bits == 32 else png.astype(float) / ((1 << bits) - 1)
        np.testing.assert_allclose(
            actual.reshape(size, size, 4)[..., :3], expected, rtol=0, atol=1e-7
        )
    finally:
        bpy.data.images.remove(img)
    report = {
        "status": "PASS",
        "seconds": time.perf_counter() - t,
        "largest_generation_tick_seconds": longest,
        "includes_carried_lit_cutout": True,
        "bits": bits,
        "smoothing": smooth,
        "independent_blender_reload": True,
        "shape": list(png.shape),
        "unique_R_values": int(np.unique(png[..., 0]).size),
        "coverage_texels": int(np.count_nonzero(png[..., 2])),
        "texture": s.export.paths[0],
        "project": s.export.paths[1],
    }
    anime_sdf_gen.unregister()
except Exception:
    report = {"status": "FAIL", "traceback": traceback.format_exc()}
    traceback.print_exc()
(OUT / f"export_{size}_{bits}_{smooth:g}.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report, indent=2))
if report["status"] != "PASS":
    sys.exit(1)
