"""Real bilingual popup, live locale refresh and Chinese 2K/4K layout checks."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import copy
import time
import bpy
import numpy as np
import anime_sdf_gen
from anime_sdf_gen import i18n, ui_guard, session, source
from anime_sdf_gen.core import model, files
from anime_sdf_gen.core.messages import UserError
from tests.fixture import fixture_face
from tests.support import TestRun
from tests.ui_helpers import redraw, shot, labels, click, event, hover, await_tooltip, wait_for
from tests.ui_runner import run as run_ui

RUN = TestRun("i18n-2k").prepare(blender=True)
OUT = RUN.out
report = RUN.report
v = bpy.context.preferences.view
KINDS = ("objects", "meshes", "materials", "images", "scenes", "worlds", "screens", "workspaces")


def counts():
    return {name: len(getattr(bpy.data, name)) for name in KINDS}


def texts():
    return [value for value, *_ in labels()]


def dismiss():
    event("ESC")
    event("ESC", "RELEASE")


def synchronous_switch(s, language):
    artwork = model.dumps(s.project)
    selection = (set(s.selected), s.direction, s.key_index, s.contour, s.point, s.handle)
    history = copy.deepcopy((s.history.undo_stack, s.history.redo_stack))
    playback = (s.rotation, s.playing, s.orbit_preview)
    caches = (
        id(s.preview.raw_thresholds),
        id(s.preview.thresholds),
        s.preview.mask_revision,
        id(s.preview._mask_texture),
        s.preview._mask_texture_revision,
    )
    field_ids = {key: id(value) for key, value in s.preview.field_cache.items()}
    job = s.export.job
    v.language = language
    s.refresh_language()
    redraw()
    assert model.dumps(s.project) == artwork
    assert selection == (set(s.selected), s.direction, s.key_index, s.contour, s.point, s.handle)
    assert history == (s.history.undo_stack, s.history.redo_stack)
    assert playback == (s.rotation, s.playing, s.orbit_preview)
    assert caches == (
        id(s.preview.raw_thresholds),
        id(s.preview.thresholds),
        s.preview.mask_revision,
        id(s.preview._mask_texture),
        s.preview._mask_texture_revision,
    )
    assert field_ids == {key: id(value) for key, value in s.preview.field_cache.items()}
    assert s.export.job is job


def workflow():
    v.language = "zh_HANS"
    v.use_translate_interface = v.use_translate_tooltips = v.use_translate_reports = True
    anime_sdf_gen.register()
    before = counts()
    face = fixture_face(source)
    fingerprint = face.reference["fingerprint"]

    # Show the real native launcher panel before creating the floating editor.
    origin = RUN.origin
    area = next(a for a in origin.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(window=origin, area=area, region=region):
        bpy.ops.wm.call_panel(name="ANIME_SDF_GEN_PT_launcher")
    yield 0.2
    with bpy.context.temp_override(window=origin, area=area, region=region):
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        bpy.ops.screen.screenshot(filepath=str(OUT / "00-chinese-launcher.png"))
    origin.event_simulate(type="ESC", value="PRESS", x=200, y=200)
    origin.event_simulate(type="ESC", value="RELEASE", x=200, y=200)
    yield 0.2

    project = model.new_project(
        face.reference, face.alignment, resolution=512, output=str(OUT / "中文目录" / "角色贴图")
    )
    project["authoring"]["stage"] = "ORIENT"
    s = session.start(bpy.context, project, face)
    yield from wait_for(lambda: s.editor.ready and s.editor.widgets)
    assert "将面部调整为正视图。" in texts()
    assert "下一步  →" in texts()
    assert "PREVIEW" not in s.editor.boxes
    report["window_dimensions"] = [s.editor.window.width, s.editor.window.height]
    report["ui_scale"] = v.ui_scale
    shot(OUT, "01-orient-zh.png")
    click("NEXT")
    yield 0.2
    assert s.stage == "FIT" and "放置标记。" in texts()
    assert {"鼻子", "嘴部中心", "下巴"} <= set(texts())
    shot(OUT, "02-markers-zh.png")
    click("NEXT")
    yield from wait_for(
        lambda: s.stage == "EDIT" and (s.preview.thresholds is not None or s.error), 90
    )
    assert not s.error, str(s.error)
    assert "调整曲线。" in texts() and {"左 → 右", "右 → 左"} <= set(texts())
    shot(OUT, "03-curves-zh.png")
    hover("MIRROR")
    yield from await_tooltip("MIRROR")
    shot(OUT, "04-mirror-tooltip-zh.png")

    # Real timer detection, followed by synchronous cache/state assertions.
    v.language = "en_US"
    yield from wait_for(lambda: s.locale_signature[0] == bpy.app.translations.locale, 5)
    assert s.locale_signature[0] == "en_US", (
        s.locale_signature,
        bpy.app.translations.locale,
        v.language,
    )
    assert "Adjust curves." in texts()
    synchronous_switch(s, "zh_HANS")
    synchronous_switch(s, "en_US")
    synchronous_switch(s, "zh_HANS")
    holder = type("BoundDialog", (), {})()
    ui_guard.bind(holder, s, target=True)
    synchronous_switch(s, "en_US")
    assert ui_guard.current(holder, ("EDIT",)) is s
    synchronous_switch(s, "zh_HANS")

    s.notify_error(
        UserError(
            "The source has no UV map named {uv_name}.",
            uv_name="测试 UV {literal} / 长名称_角色_面部_贴图",
        )
    )
    redraw()
    assert "测试 UV {literal}" in s.editor.warning_text
    assert "源模型没有名为" in s.editor.warning_text
    shot(OUT, "05-warning-zh.png")
    warning = s.error
    synchronous_switch(s, "en_US")
    assert s.error is warning and "The source has no UV map named" in s.editor.warning_text
    v.use_translate_reports = False
    synchronous_switch(s, "zh_HANS")
    assert s.editor.warning_text.startswith("The source has no UV map named")
    v.use_translate_reports = True
    s.refresh_language()
    s.error = ""
    redraw()
    report["checks"].append(
        "four-step Chinese labels, retained warnings, independent report flags, automatic refresh and zero locale-driven cache uploads"
    )

    click("NEXT")
    yield 0.2
    assert s.stage == "CONFIRM" and s.playing
    assert "确认。" in texts() and "生成并完成" in texts()
    initial_rotation = s.rotation
    synchronous_switch(s, "en_US")
    synchronous_switch(s, "zh_HANS")
    yield 0.1
    assert s.playing and s.rotation != initial_rotation
    click("PLAY")
    yield 0.1
    assert not s.playing
    shot(OUT, "06-confirm-zh.png")
    original_project = model.dumps(s.project)
    click("BIT_DEPTH")
    yield 0.2
    shot(OUT, "07-depth-dialog-zh.png")
    v.language = "en_US"
    yield 0.1
    v.language = "zh_HANS"
    yield 0.1
    dismiss()
    yield 0.1
    assert model.dumps(s.project) == original_project
    hover("SMOOTHING_SLIDER")
    yield from await_tooltip("SMOOTHING_SLIDER")
    shot(OUT, "08-smoothing-tooltip-zh.png")

    timings = {}
    for language in ("en_US", "zh_HANS"):
        synchronous_switch(s, language)
        redraw()
        values = []
        for _ in range(12):
            start = time.perf_counter()
            redraw()
            values.append((time.perf_counter() - start) * 1000)
        timings[language] = float(np.median(values))
    report["redraw_median_ms"] = timings

    paths = files.output_paths(s.project, s.project["settings"]["output"])
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"existing-validation-file")
    s.export.start()
    s.export.advance(0.00001, finish=False)
    assert s.busy and s.export.message
    synchronous_switch(s, "en_US")
    english = i18n.report(s.export.message)
    synchronous_switch(s, "zh_HANS")
    assert i18n.report(s.export.message) != english
    shot(OUT, "09-generation-zh.png")
    s.export.cancel()
    assert all(path.read_bytes() == b"existing-validation-file" for path in paths)
    assert not s.busy and not s.closed
    report["checks"].append(
        "native precision dialog, long tooltip, playback continuity and active-export locale changes with preserved files on cancellation"
    )

    art = model.dumps(s.project)
    old = s.registry.id
    e = s.editor
    with bpy.context.temp_override(window=e.window, area=e.native_area):
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "中文编辑保存.blend"), check_existing=False)
    yield from wait_for(
        lambda: session.ACTIVE is not None
        and session.ACTIVE.registry.id != old
        and session.ACTIVE.editor.ready,
        90,
    )
    s = session.ACTIVE
    assert model.dumps(s.project) == art and s.locale_signature[0] == "zh_HANS"
    assert "确认。" in texts()
    shot(OUT, "10-save-resume-zh.png")
    editable = OUT / "可编辑工程.sdfproject.json"
    editable.write_text(model.dumps(s.project), encoding="utf-8")
    session.end_session(True)
    yield 0.1
    with bpy.context.temp_override(window=origin):
        assert bpy.ops.anime_sdf_gen.open_project(filepath=str(editable)) == {"FINISHED"}
    yield from wait_for(lambda: session.ACTIVE and session.ACTIVE.editor.ready, 60)
    assert model.dumps(session.ACTIVE.project) == art
    assert "确认。" in texts()
    anime_sdf_gen.unregister()
    yield 0.1
    assert session.ACTIVE is None and not i18n._registered
    assert counts() == before
    assert fixture_face(source).reference["fingerprint"] == fingerprint
    report["fixture_sha256"] = RUN.fixture_hash()
    report["checks"].append(
        "Chinese save/resume and project reopening preserve schema 4; disabling cleans the active popup and translation registry"
    )


run_ui(workflow, RUN, "i18n-ui.json", timeout=300)
