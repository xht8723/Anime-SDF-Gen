"""Atomic bake-map switching, material defaults, persistence and baked placement."""

from pathlib import Path
from types import SimpleNamespace
import sys
import traceback
from unittest.mock import patch

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import anime_sdf_gen
from anime_sdf_gen import commands, session, source, ui
from anime_sdf_gen.core import files, model
from anime_sdf_gen.core.image_io import read_png
from anime_sdf_gen.ui_guard import bind
from tests.fixture import fixture_face
from tests.support import TestRun

RUN = TestRun("uv-selection").prepare(blender=True)


def export(s, name):
    s.project["settings"]["output"] = str(RUN.out / name)
    s.export.start()
    while s.busy:
        s.export.advance(0.05, finish=False)
    assert s.export.paths, s.error
    return read_png(s.export.paths[0]), files.load_project(s.export.paths[-1])


def unchanged(s, before, caches):
    assert s.checkpoint() == before
    assert caches == cache_ids(s)


def cache_ids(s):
    return tuple(
        id(x)
        for x in (
            s.bvh, s.preview.depth, s.preview.domain,
            s.preview.raw_thresholds, s.preview.thresholds, s.preview._face_batch,
        )
    )


try:
    original_hash = RUN.fixture_hash()
    anime_sdf_gen.register()
    obj = bpy.data.objects["body"]
    mesh = obj.data
    original_active = mesh.uv_layers.active.name
    coords = np.array([v.uv[:] for v in mesh.uv_layers["UVMap"].data])
    for name, offset in (("Bake_A", 0.0), ("Bake_B", 0.5)):
        uv = mesh.uv_layers.new(name=name)
        values = coords.copy()
        values[:, 0] = values[:, 0] * 0.45 + offset
        uv.data.foreach_set("uv", values.ravel())
    mesh.uv_layers.new(name="Invalid")
    mesh.uv_layers["Invalid"].data.foreach_set("uv", np.zeros(coords.size))
    mesh.uv_layers.new(name="Nonfinite")
    mesh.uv_layers["Nonfinite"].data.foreach_set("uv", np.full(coords.size, np.nan))
    # Active and render maps deliberately differ; both must survive bake choices.
    original_render = "Bake_A"
    mesh.uv_layers.active = mesh.uv_layers[original_active]
    mesh.uv_layers[original_render].active_render = True
    mesh.update()
    bpy.context.view_layer.update()
    face = fixture_face(source)
    p = model.new_project(
        face.reference, face.alignment, resolution=512, output=str(RUN.out / "original")
    )
    s = session.start(bpy.context, p, face, handlers=False)
    commands.handle_mode(s, "CORNER")
    s.confirm()
    before = s.checkpoint()
    caches = cache_ids(s)
    preview_mesh = s.preview_object.data
    material_links = [
        (m, [(n.name, getattr(n, "uv_map", None)) for n in m.node_tree.nodes])
        for m in preview_mesh.materials if m and m.node_tree
    ]
    s.set_bake_uv("Bake_A")
    for key in ("selection", "selected", "playback", "undo", "redo"):
        assert s.checkpoint()[key] == before[key], key
    assert cache_ids(s) == caches
    assert s.project["sweeps"] == before["project"]["sweeps"]
    assert s.project["landmarks"] == before["project"]["landmarks"]
    assert s.project["alignment"] == before["project"]["alignment"]
    assert s.project["source"]["uv_map"] == s.project["authoring"]["uv_map"] == "Bake_A"
    assert s.project["source"]["fingerprint"] != face.reference["fingerprint"]
    assert mesh.uv_layers.active.name == preview_mesh.uv_layers.active.name == original_active
    assert next(uv.name for uv in preview_mesh.uv_layers if uv.active_render) == original_render
    assert material_links == [
        (m, [(n.name, getattr(n, "uv_map", None)) for n in m.node_tree.nodes])
        for m in preview_mesh.materials if m and m.node_tree
    ]
    RUN.report["checks"].append(
        "UV switch preserves artwork, fit, selection, history, playback, caches and material UVs"
    )

    s.set_bake_uv("Invalid")
    assert not s.face.uvs.any()
    s.set_bake_uv("Bake_A")
    for name in ("missing", "Nonfinite"):
        before, caches = s.checkpoint(), cache_ids(s)
        try:
            s.set_bake_uv(name)
            raise AssertionError("invalid map accepted")
        except ValueError:
            pass
        unchanged(s, before, caches)
    for change in ("pose", "geometry", "identity", "region"):
        before, caches = s.checkpoint(), cache_ids(s)
        replacement = source.from_reference(
            dict(s.project["source"], uv_map="Bake_B"),
            s.project["alignment"], allow_relink=True,
        )
        if change == "pose":
            original_location = obj.location.copy()
            obj.location.x += 0.1
            bpy.context.view_layer.update()
        elif change == "geometry":
            replacement.vertices[0, 0] += 0.01
        elif change == "identity":
            replacement.triangle_vertices[0] = replacement.triangle_vertices[0, ::-1]
        else:
            replacement.reference["faces"] = replacement.reference["faces"][1:]
        try:
            if change == "pose":
                s.set_bake_uv("Bake_B")
            else:
                with patch.object(source, "from_reference", return_value=replacement):
                    s.set_bake_uv("Bake_B")
            raise AssertionError("changed source accepted: " + change)
        except ValueError:
            pass
        finally:
            if change == "pose":
                obj.location = original_location
                bpy.context.view_layer.update()
        unchanged(s, before, caches)
    pending = SimpleNamespace(section="BAKE_UV", uv_map="Bake_B")
    bind(pending, s)
    s.project["authoring"]["stage"] = "EDIT"
    assert ui.ANIME_SDF_GEN_OT_settings.execute(pending, bpy.context) == {"CANCELLED"}
    s.confirm()
    before, caches = s.checkpoint(), cache_ids(s)
    ui.ANIME_SDF_GEN_OT_settings.cancel(pending, bpy.context)
    unchanged(s, before, caches)
    s.export.start()
    assert ui.ANIME_SDF_GEN_OT_settings.execute(pending, bpy.context) == {"CANCELLED"}
    s.export.cancel()
    RUN.report["checks"].append(
        "missing/invalid maps, geometry, pose, triangle identity, region, stale stage, "
        "cancellation and busy submissions are atomic"
    )

    a, saved_a = export(s, "layout-a")
    s.set_bake_uv("Bake_B")
    b, saved_b = export(s, "layout-b")
    assert a.shape == b.shape == (512, 512, 3)
    assert a[:, :256, 2].any() and not a[:, 256:, 2].any()
    assert b[:, 256:, 2].any() and not b[:, :256, 2].any()
    assert saved_a["source"]["uv_map"] == saved_a["authoring"]["uv_map"] == "Bake_A"
    assert saved_b["source"]["uv_map"] == saved_b["authoring"]["uv_map"] == "Bake_B"
    s.write_draft()
    draft = files.load_project(session.draft_root() / (s.project["id"] + ".sdfproject.json"))
    assert draft == s.project
    session.end_session(True)
    s = session.start(
        bpy.context, saved_b,
        source.from_reference(saved_b["source"], saved_b["alignment"]), handlers=False,
    )
    assert s.stage == "CONFIRM" and s.project["authoring"]["uv_map"] == "Bake_B"
    assert s.preview_object.data.uv_layers.active.name == original_active
    assert next(
        uv.name for uv in s.preview_object.data.uv_layers if uv.active_render
    ) == original_render
    assert ui.ANIME_SDF_GEN_OT_settings.execute(pending, bpy.context) == {"CANCELLED"}
    assert next(uv.name for uv in mesh.uv_layers if uv.active_render) == original_render
    assert RUN.fixture_hash() == original_hash
    RUN.report["checks"].append(
        "two 512px layouts change baked placement and metadata; draft and reopen retain "
        "bake choice and reference material defaults"
    )
    RUN.report["status"] = "PASS"
except Exception:
    RUN.report.update(status="FAIL", traceback=traceback.format_exc())
    traceback.print_exc()
finally:
    anime_sdf_gen.unregister()
    RUN.write("uv-selection.json")
if RUN.report["status"] != "PASS":
    raise RuntimeError(RUN.report["traceback"])
