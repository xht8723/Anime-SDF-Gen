"""Native translation contexts, independent flags, Unicode data and registration."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import itertools
import traceback
from unittest.mock import patch
from types import SimpleNamespace
import bpy
import numpy as np
import anime_sdf_gen
from anime_sdf_gen import i18n, ui, source
from anime_sdf_gen.catalog import ENTRIES
from anime_sdf_gen.core import model, files
from anime_sdf_gen.core.messages import CONTEXT, msg, raw, UserError
from tests.support import TestRun

RUN = TestRun("i18n-runtime").prepare(blender=True)
v = bpy.context.preferences.view
translation = bpy.app.translations
original_flags = (
    v.language,
    v.use_translate_interface,
    v.use_translate_tooltips,
    v.use_translate_reports,
)
catalog = dict(ENTRIES)
obj = mesh = None

try:
    actual_register = bpy.utils.register_class
    calls = 0

    def fail_registration(cls):
        global calls
        calls += 1
        if calls == 4:
            raise RuntimeError("Injected registration failure")
        actual_register(cls)

    with patch.object(bpy.utils, "register_class", side_effect=fail_registration):
        try:
            anime_sdf_gen.register()
        except RuntimeError as exc:
            assert "Injected" in str(exc)
        else:
            raise AssertionError("Expected registration failure")
    assert not ui._registered_classes and not i18n._registered
    assert not hasattr(bpy.types.WindowManager, "anime_sdf_gen")
    RUN.report["checks"].append(
        "failed registration removes registered classes, properties and translations"
    )

    for cycle in range(3):
        anime_sdf_gen.register()
        v.language = "zh_HANS"
        v.use_translate_interface = v.use_translate_tooltips = v.use_translate_reports = True
        assert i18n.iface("Next Step  →") == "下一步  →"
        if cycle < 2:
            anime_sdf_gen.unregister()
            assert translation.pgettext_iface("Next Step  →", CONTEXT) == "Next Step  →"
    fields = 0
    for cls in ui.CLASSES:
        if not issubclass(cls, bpy.types.PropertyGroup):
            assert cls.bl_rna.translation_context == CONTEXT, cls
        for name, deferred in cls.__dict__.get("__annotations__", {}).items():
            kw = deferred.keywords
            if "name" not in kw and "items" not in kw:
                continue
            if issubclass(cls, bpy.types.Operator):
                module, operator = cls.bl_idname.split(".")
                rna = getattr(getattr(bpy.ops, module), operator).get_rna_type()
            else:
                rna = cls.bl_rna
            prop = rna.properties.get(name)
            assert prop is not None and prop.translation_context == CONTEXT, (cls, name)
            for text in (kw.get("name", ""), kw.get("description", "")):
                if text:
                    assert text in catalog or text == "Anime SDF Gen", (cls, name, text)
            if prop.type == "ENUM":
                for item in prop.enum_items:
                    for text in (item.name, item.description):
                        if text and any(c.islower() for c in text):
                            assert text in catalog, (cls, name, text)
            fields += 1
    RUN.report["rna_fields_checked"] = fields

    message = msg("The source has no UV map named {uv_name}.", uv_name="Smoothing {UV}")
    for interface, tips, reports in itertools.product((False, True), repeat=3):
        v.use_translate_interface = interface
        v.use_translate_tooltips = tips
        v.use_translate_reports = reports
        assert i18n.iface("Smoothing") == ("平滑强度" if interface else "Smoothing")
        assert i18n.tip("Smoothing") == ("平滑强度" if tips else "Smoothing")
        expected = "源模型没有名为 Smoothing {UV} 的 UV 贴图。" if reports else str(message)
        assert i18n.report(message) == expected
        assert i18n.iface(raw("Smoothing")) == "Smoothing"
        notifications = []
        operator = SimpleNamespace(report=lambda kinds, text: notifications.append(text))
        with patch.object(ui.session, "ACTIVE", SimpleNamespace(redraw=lambda: None)):
            assert ui.ANIME_SDF_GEN_OT_create.execute(operator, bpy.context) == {"FINISHED"}
        expected = (
            "Anime SDF Gen 已在编辑窗口中打开。"
            if reports
            else "Anime SDF Gen is already open in its editor window."
        )
        assert notifications == [expected]
    v.use_translate_interface = v.use_translate_tooltips = v.use_translate_reports = True
    for locale in ("en_US", "zh_HANS", "de_DE", "DEFAULT", "zh_HANS", "en_US"):
        v.language = locale
        expected = "下一步  →" if translation.locale == "zh_HANS" else "Next Step  →"
        assert i18n.iface("Next Step  →") == expected, (locale, translation.locale)
    RUN.report["checks"].append(
        "all flag combinations, Automatic, unsupported locale fallback and repeated live language changes"
    )

    # A source with real Chinese object, group and UV names, in this process only.
    mesh = bpy.data.meshes.new("中文网格")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], [], [(0, 1, 2, 3)])
    mesh.update()
    uv = mesh.uv_layers.new(name="面部 UV")
    for i, co in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[i].uv = co
    obj = bpy.data.objects.new("角色面部", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    group = obj.vertex_groups.new(name="面部顶点组")
    group.add(list(range(4)), 1, "REPLACE")
    face = source.capture(obj, "VERTEX_GROUP", group.name)
    project = model.new_project(
        face.reference,
        face.alignment,
        resolution=512,
        output=str(RUN.out / "中文目录" / "面部纹理"),
    )
    image = np.linspace(0, 1, 12 * 16 * 3, dtype=np.float32).reshape(12, 16, 3)
    image[..., 2] = image[..., 2] > 0.5
    canonical = model.dumps(project)
    for translated in (False, True):
        v.language = "zh_HANS"
        v.use_translate_reports = translated
        notifications = []
        operator = SimpleNamespace(
            filepath=str(RUN.out / "通知测试.sdfproject.json"),
            report=lambda kinds, text: notifications.append(text),
        )
        active = SimpleNamespace(project=project, editor=SimpleNamespace(close_requested=None))
        with (
            patch.object(ui.session, "ACTIVE", active),
            patch.object(ui, "current", return_value=active),
            patch.object(ui, "atomic_text") as writer,
        ):
            assert ui.ANIME_SDF_GEN_OT_save_draft.execute(operator, bpy.context) == {"FINISHED"}
            writer.assert_called_once_with(operator.filepath, canonical)
        expected = (
            "草稿已保存，原始工作区已恢复。"
            if translated
            else "Draft saved; original workspace restored."
        )
        assert notifications == [expected]
    v.use_translate_reports = True
    RUN.report["checks"].append(
        "native create/save notifications use the add-on context and report flag"
    )
    for bits in model.BIT_DEPTHS:
        project["settings"]["bit_depth"] = bits
        expected = None
        for locale in ("en_US", "zh_HANS"):
            v.language = locale
            before = model.dumps(project)
            checked = source.from_reference(face.reference, face.alignment)
            assert checked.reference == face.reference
            paths = files.export_bundle(project, image, project["settings"]["output"])
            data = tuple(Path(path).read_bytes() for path in paths)
            if expected is not None:
                assert data == expected, "Language changed image or sidecar bytes"
            expected = data
            assert model.dumps(project) == before
    project["settings"]["bit_depth"] = 16
    assert model.dumps(project) == canonical
    RUN.report["checks"].append(
        "Chinese source/group/UV/path names and byte-identical PNG8, PNG16, EXR32 and sidecars across languages"
    )
    RUN.report["fixture_sha256"] = RUN.fixture_hash()
    RUN.report["status"] = "PASS"
except Exception:
    RUN.report.update(status="FAIL", traceback=traceback.format_exc())
    traceback.print_exc()
finally:
    anime_sdf_gen.unregister()
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)
    if mesh:
        bpy.data.meshes.remove(mesh)
    v.language, v.use_translate_interface, v.use_translate_tooltips, v.use_translate_reports = (
        original_flags
    )
    RUN.write("i18n-runtime.json")
if RUN.report["status"] != "PASS":
    raise RuntimeError(RUN.report["traceback"])
print(RUN.report)
