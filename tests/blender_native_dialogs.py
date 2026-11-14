"""Native dialogs opened with real popup presses/releases, including nested controls."""

from copy import deepcopy
from pathlib import Path
import sys
from unittest.mock import patch
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import anime_sdf_gen
from anime_sdf_gen import canvas, session, source, ui
from anime_sdf_gen.curve_input import CurveInput
from anime_sdf_gen.core import model
from anime_sdf_gen.viewport import scale, window_region
from tests.fixture import fixture_face
from tests.support import TestRun
from tests.ui_helpers import dialog_confirm_position, center, click, event, redraw, shot, wait_for
from tests.ui_runner import run

RUN = TestRun("native-dialogs-2k").prepare(blender=True)
active = {}
trace = []
rects = {}
RUN.report["trace"] = trace
original_curve_modal = CurveInput.modal
double_click_next = False


def curve_modal(self, event, mouse, region, view):
    global double_click_next
    if double_click_next and event.type == "LEFTMOUSE" and event.value == "PRESS":
        double_click_next = False
        # event_simulate accepts only PRESS/RELEASE/NOTHING and does not derive
        # DOUBLE_CLICK. Supply that native tag at the input boundary; the actual
        # press and following release still travel through the popup's handler.
        original_event = event

        class DoubleClick:
            value = "DOUBLE_CLICK"

            def __getattr__(self, name):
                return getattr(original_event, name)

        with patch("anime_sdf_gen.curve_input.binding", return_value=None):
            return original_curve_modal(self, DoubleClick(), mouse, region, view)
    return original_curve_modal(self, event, mouse, region, view)


CurveInput.modal = curve_modal


def wrapper(method, original, key):
    def record(self, context):
        name = getattr(self, "section", key)
        if method == "invoke":
            active[name] = self
            trace.append([name, "invoke"])
        elif method in ("execute", "cancel"):
            active.pop(name, None)
            trace.append([name, method])
        elif method == "draw":
            r = context.region
            rects[name] = [r.x, r.y, r.width, r.height]

    def invoke(self, context, event):
        record(self, context)
        return original(self, context, event)

    def other(self, context):
        record(self, context)
        return original(self, context) if original else None

    return invoke if method == "invoke" else other


def track(cls, key):
    for method in ("invoke", "execute", "cancel", "draw"):
        original = getattr(cls, method, None)
        if original is not None or method == "cancel":
            setattr(cls, method, wrapper(method, original, key))


for cls, key in (
    (ui.ANIME_SDF_GEN_OT_settings, "settings"),
    (ui.ANIME_SDF_GEN_OT_transform, "TRANSFORM"),
    (ui.ANIME_SDF_GEN_OT_destination, "DESTINATION"),
    (ui.ANIME_SDF_GEN_OT_save_draft, "DRAFT"),
    (ui.ANIME_SDF_GEN_OT_generate, "GENERATE"),
):
    track(cls, key)


def keypress(kind, xy=(2, 2), **kwargs):
    event(kind, xy=xy, **kwargs)
    kwargs.pop("unicode", None)
    event(kind, "RELEASE", xy, **kwargs)


def mouse_click(xy, **kwargs):
    event("MOUSEMOVE", "NOTHING", xy)
    yield 0.08
    event("LEFTMOUSE", xy=xy, **kwargs)
    yield 0.08
    event("LEFTMOUSE", "RELEASE", xy, **kwargs)
    yield 0.08


def native_ok(name):
    return dialog_confirm_position(RUN.out, name)


def type_text(text, xy):
    for character in text:
        kind = (
            character.upper()
            if character.isalpha()
            else {"_": "MINUS", ".": "PERIOD", "2": "TWO"}[character]
        )
        keypress(kind, xy=xy, unicode=character, shift=character == "_")


def search_uv(name, choice, source_dialog=False):
    ok = native_ok(name + "-before-search")
    xy = ok + np.array([70, 48 if source_dialog else 27]) * scale()
    RUN.report["search_position"] = dict(ok=ok.tolist(), xy=xy.tolist(), scale=scale())
    yield from mouse_click(xy)
    yield 0.2
    keypress("A", xy=xy, ctrl=True)
    type_text(choice, xy)
    yield 0.3
    shot(RUN.out, name + "-nested-search.png")
    keypress("RET", xy=xy)
    yield 0.2
    assert name in active and active[name].uv_map == choice, (
        name, active[name].uv_map if name in active else trace
    )
    yield from mouse_click(ok)
    yield 0.3
    assert name not in active


def cancel(name):
    keypress("ESC")
    yield 0.25
    assert name not in active, (name, trace)


def open_button(name, hold=0.05):
    redraw()
    xy = center(name)
    event("MOUSEMOVE", "NOTHING", xy)
    event("LEFTMOUSE", xy=xy)
    yield hold
    assert name not in active, (name, "opened before release")
    assert session.ACTIVE.native_ui.pending
    event("LEFTMOUSE", "RELEASE", xy)
    yield from wait_for(lambda: name in active)
    yield 0.6
    assert name in active, (name, "dismissed after release", trace)
    return xy


def workflow():
    global double_click_next
    anime_sdf_gen.register()
    obj = bpy.data.objects["body"]
    uv = obj.data.uv_layers.new(name="Bake_B")
    for a, b in zip(uv.data, obj.data.uv_layers["UVMap"].data):
        a.uv = (b.uv.x * 0.45 + 0.5, b.uv.y)
    obj.data.uv_layers.active = obj.data.uv_layers["UVMap"]
    obj.data.uv_layers["UVMap"].active_render = True
    bpy.context.view_layer.update()
    face = fixture_face(source)
    p = model.new_project(
        face.reference, face.alignment, resolution=512, output=str(RUN.out / "face")
    )
    p["authoring"]["stage"] = "ORIENT"
    s = session.start(bpy.context, p, face)
    yield from wait_for(lambda: s.editor.ready and s.editor.widgets)
    RUN.report["window_dimensions"] = [s.editor.window.width, s.editor.window.height]
    yield from open_button("SOURCE", hold=0.8)
    shot(RUN.out, "01-source-held-release.png")
    RUN.report["rects"] = deepcopy(rects)
    yield from search_uv("SOURCE", "Bake_B", source_dialog=True)
    assert s.project["authoring"]["uv_map"] == "Bake_B"
    RUN.report["checks"].append(
        "long-held Source/UV button opens only after release and survives idle"
    )
    # Cancelled gestures must never create a native dialog.
    for cancellation in ("outside", "ESC", "RIGHTMOUSE", "WINDOW_DEACTIVATE", "stage"):
        yield 0.4
        redraw()
        xy = center("SOURCE")
        event("LEFTMOUSE", xy=xy)
        yield 0.08
        assert s.native_ui.pending, (cancellation, "gesture not armed")
        if cancellation == "outside":
            event("LEFTMOUSE", "RELEASE", (20, 250))
        elif cancellation == "stage":
            s.project["authoring"]["stage"] = "FIT"
            event("LEFTMOUSE", "RELEASE", xy)
        else:
            keypress(cancellation, xy=xy)
            event("LEFTMOUSE", "RELEASE", xy)
        yield 0.2
        assert not s.native_ui.pending and "SOURCE" not in active, cancellation
        s.project["authoring"]["stage"] = "ORIENT"
    RUN.report["checks"].append(
        "release outside, Escape, right click, focus loss and stale stage cancel pending gestures"
    )
    before_invokes = trace.count(["SOURCE", "invoke"])
    yield 0.4
    redraw()
    xy = center("SOURCE")
    event("LEFTMOUSE", xy=xy)
    event("LEFTMOUSE", "RELEASE", xy)
    event("LEFTMOUSE", xy=xy)
    yield 0.3
    assert "SOURCE" not in active and s.native_ui.pending
    event("LEFTMOUSE", "RELEASE", xy)
    yield 0.5
    assert trace.count(["SOURCE", "invoke"]) == before_invokes + 1
    assert "SOURCE" in active
    yield from cancel("SOURCE")

    s.project["authoring"].update(stage="EDIT", uv_map="UVMap")
    s.activate_stage()
    yield 0.3
    click("KEYFRAME:left_to_right:4")
    yield 0.1
    yield from wait_for(lambda: s.preview.thresholds is not None or bool(s.error), 90)
    view = s.editor.views["AUTHOR"]
    point = canvas.to_view(s, s.curve["points"][3]["co"], view)
    xy = (view.region.x + point.x, view.region.y + point.y)
    event("MOUSEMOVE", "NOTHING", xy)
    event("LEFTMOUSE", xy=xy)
    event("LEFTMOUSE", "RELEASE", xy)
    yield 0.03
    double_click_next = True
    event("LEFTMOUSE", xy=xy)
    yield 0.2
    assert "POINT" not in active and s.native_ui.pending, (s.curve_edit.state, trace[-8:])
    event("LEFTMOUSE", "RELEASE", xy)
    yield from wait_for(lambda: "POINT" in active)
    yield 0.5
    assert "POINT" in active
    shot(RUN.out, "point-double-click.png")
    yield from cancel("POINT")
    click("TRIANGLE")
    yield 0.2
    yield from open_button("TRANSFORM")
    ok = native_ok("transform")
    shape = deepcopy(s.curve)
    xy = ok + np.array([130, 27]) * scale()
    yield from mouse_click(xy, ctrl=True)
    keypress("A", xy=xy, ctrl=True)
    type_text("2", xy)
    keypress("RET", xy=xy)
    yield 0.15
    yield from mouse_click(ok)
    yield 0.2
    assert "TRANSFORM" not in active and shape != s.curve
    # Remove test shape and continue with the default valid artwork.
    click("UNDO")
    yield 0.2
    click("DELETE_SHAPE")
    yield 0.2
    click("NEXT")
    yield 0.2
    assert s.stage == "CONFIRM"
    yield from wait_for(lambda: s.preview.thresholds is not None or bool(s.error), 90)
    assert not s.error, s.error
    artwork = deepcopy(s.project["sweeps"])
    thresholds = s.preview.thresholds
    cache = {k: id(v) for k, v in s.preview.field_cache.items()}
    materials = s.preview_object.data.uv_layers.active.name
    yield from open_button("BAKE_UV")
    yield from search_uv("BAKE_UV", "Bake_B")
    assert s.project["source"]["uv_map"] == s.project["authoring"]["uv_map"] == "Bake_B"
    assert s.preview.thresholds is thresholds and artwork == s.project["sweeps"]
    assert cache == {k: id(v) for k, v in s.preview.field_cache.items()}
    assert s.preview_object.data.uv_layers.active.name == materials and s.playing
    RUN.report["checks"].append(
        "native UV searches accept changes in Orientation and Confirm; point double-click "
        "consumes release; transform dialog accepts"
    )
    RUN.report["double_click_simulation"] = (
        "Two simulated presses/releases; DOUBLE_CLICK tagged at CurveInput boundary because "
        "Blender event_simulate does not emit that value. No direct operator invocation."
    )

    for name in ("FILENAME", "RESOLUTION", "BIT_DEPTH", "SMOOTHING"):
        yield from open_button(name)
        if name == "FILENAME":
            ok = native_ok("filename")
            xy = ok + np.array([70, 27]) * scale()
            yield from mouse_click(xy)
            keypress("A", xy=xy, ctrl=True)
            type_text("native", xy)
            keypress("RET", xy=xy)
            yield 0.1
            yield from mouse_click(ok)
            yield 0.25
            assert name not in active and Path(s.project["settings"]["output"]).name == "native"
        elif name == "RESOLUTION":
            ok = native_ok("resolution-dropdown")
            xy = ok + np.array([70, 27]) * scale()
            yield from mouse_click(xy)
            keypress("HOME", xy=xy)
            keypress("DOWN_ARROW", xy=xy)
            keypress("RET", xy=xy)
            yield 0.2
            assert name in active and active[name].resolution != "512"
            yield from cancel(name)
            assert s.project["settings"]["resolution"] == 512
        else:
            yield from cancel(name)
    RUN.report["checks"].append(
        "output dialogs survive release/idle; native text edits accept and Escape cancels"
    )
    for name in ("DESTINATION", "DRAFT"):
        before = deepcopy(s.project)
        yield from open_button(name)
        browsers = [
            (w, a)
            for w in bpy.context.window_manager.windows
            for a in w.screen.areas
            if a.type == "FILE_BROWSER"
        ]
        assert len(browsers) == 1, browsers
        window, area = browsers[0]
        with bpy.context.temp_override(window=window, area=area):
            bpy.ops.screen.screenshot(filepath=str(RUN.out / (name + "-file-browser.png")))
        window.event_simulate(type="ESC", value="PRESS", x=200, y=200)
        window.event_simulate(type="ESC", value="RELEASE", x=200, y=200)
        yield from wait_for(lambda: name not in active)
        yield 0.3
        assert s.project == before and session.ACTIVE is s
    RUN.report["checks"].append(
        "destination and draft file browsers survive release/idle and cancel without changes"
    )

    # Normal controls still receive events after native dialogs are gone.
    x, y, w, _ = s.editor.boxes["SMOOTHING_TRACK"]
    yield from mouse_click((x + w * 0.4, y))
    assert 0 < s.project["settings"]["smoothing"] < 8
    s.preview.set_smoothing(0)
    click("BACK")
    yield 0.2
    click("KEYFRAME:left_to_right:4")
    yield 0.2
    view = s.editor.views["AUTHOR"]
    q = canvas.to_view(s, s.curve["points"][3]["co"], view)
    xy = (view.region.x + q.x, view.region.y + q.y)
    before = deepcopy(s.project["sweeps"])
    event("MOUSEMOVE", "NOTHING", xy)
    event("LEFTMOUSE", xy=xy)
    yield 0.1
    event("MOUSEMOVE", "NOTHING", (xy[0] + 15, xy[1]))
    yield 0.15
    event("LEFTMOUSE", "RELEASE", (xy[0] + 15, xy[1]))
    yield 0.15
    assert s.project["sweeps"] != before
    click("UNDO")
    yield 0.2
    assert s.project["sweeps"] == before
    click("NEXT")
    yield 0.2
    r = s.editor.views["PREVIEW"].region
    xy = (r.x + r.width / 2, r.y + r.height / 2)
    distance = s.editor.views["PREVIEW"].view_distance
    keypress("WHEELUPMOUSE", xy=xy)
    yield 0.25
    assert s.editor.views["PREVIEW"].view_distance != distance
    RUN.report["checks"].append(
        "smoothing slider, curve drag/undo, stage navigation and viewport zoom work after dialogs"
    )

    s.project["settings"]["resolution"] = 512
    output = Path(s.project["settings"]["output"] + ".png")
    output.write_bytes(b"previous output")
    yield from open_button("GENERATE")
    shot(RUN.out, "overwrite-confirmation.png")
    yield from cancel("GENERATE")
    assert output.read_bytes() == b"previous output" and not s.busy
    yield from open_button("GENERATE")
    keypress("RET")
    yield from wait_for(lambda: s.busy or s.closed)
    yield from wait_for(lambda: s.closed or bool(s.error), 90)
    assert s.closed and output.read_bytes().startswith(b"\x89PNG"), s.error
    RUN.report["checks"].append(
        "overwrite confirmation survives release, cancels without writes, accepts a 512px export"
    )
    RUN.report["trace"] = trace
    yield 0.2
    anime_sdf_gen.unregister()


run(workflow, RUN, "native-dialogs.json")
