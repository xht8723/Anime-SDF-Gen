"""Export all four regression faces using their active UV and frontal filtering."""

from pathlib import Path
import hashlib
import sys
import traceback
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import anime_sdf_gen
from anime_sdf_gen import session, source
from anime_sdf_gen.core import files, model
from anime_sdf_gen.core.image_io import read_png
from tests.support import TestRun

RUN = TestRun("bugs-export").prepare(blender=True)

try:
    before = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("bugs.blend", "test_sdf.blend")
    }
    anime_sdf_gen.register()
    for name in ("hana_face", "amiya_face", "genshin_face", "avywen_face"):
        obj = bpy.data.objects[name]
        uv = obj.data.uv_layers.active.name
        face = source.extract(
            obj, uv, selected=list(range(len(obj.data.polygons))), front_only=True
        )
        project = model.new_project(
            face.reference, face.alignment, resolution=512, output=str(RUN.out / name)
        )
        s = session.start(bpy.context, project, face, handlers=False)
        s.confirm()
        s.export.start()
        while s.busy:
            s.export.advance(0.05, finish=False)
        assert s.export.paths, s.error
        pixels = read_png(s.export.paths[0])
        saved = files.load_project(s.export.paths[-1])
        assert pixels.shape == (512, 512, 3) and pixels[..., 2].any()
        assert saved["source"]["uv_map"] == saved["authoring"]["uv_map"] == uv
        RUN.report["checks"].append({
            "object": name, "uv": uv, "triangles": len(face.uvs),
            "coverage_texels": int(np.count_nonzero(pixels[..., 2])),
            "texture": s.export.paths[0],
        })
        session.end_session(True)
    after = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in before}
    assert before == after
    RUN.report.update(status="PASS", model_hashes=after)
except Exception:
    RUN.report.update(status="FAIL", traceback=traceback.format_exc())
    traceback.print_exc()
finally:
    anime_sdf_gen.unregister()
    RUN.write("bugs-export.json")
if RUN.report["status"] != "PASS":
    raise RuntimeError(RUN.report["traceback"])
