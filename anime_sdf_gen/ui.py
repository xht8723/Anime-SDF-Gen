"""Blender panels and explicit authoring actions; no persistent scene properties."""

from .core.messages import UserError, CONTEXT, msg, diagnostic

from pathlib import Path
import traceback
import bpy
from . import i18n
from .i18n import iface, report
from .typography import wrap
from .viewport import scale
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy_extras.io_utils import ImportHelper, ExportHelper
from . import source, session, commands
from .ui_guard import bind, current
from .core import model
from .core.files import load_project, atomic_text, output_paths, output_extension
from .input import ANIME_SDF_GEN_OT_interact

SKIP = {"SKIP_SAVE"}
DEPTH_ITEMS = [
    (
        str(n),
        model.BIT_DEPTH_LABELS[n],
        (
            "Smaller files with coarser transitions"
            if n == 8
            else "Default precision" if n == 16 else "Full floating-point precision; larger files"
        ),
    )
    for n in model.BIT_DEPTHS
]
SMOOTHING_HELP = "Smooth threshold values before UV baking. Can alter small details; does not soften hard-cutoff shadows. 0 is Off; sigma is scaled from a 2048-pixel face canvas."


def smoothing_dialog_changed(self, context):
    s = current(self, ("CONFIRM",))
    if s and getattr(self, "preview_ready", False) and self.section == "SMOOTHING":
        s.preview.set_smoothing(self.smoothing)


class ANIME_SDF_GEN_Properties(bpy.types.PropertyGroup):
    source_method: EnumProperty(
        name="Source",
        items=[
            (
                "SELECTED",
                "Selected Faces",
                "Use visible selected polygons on the active Edit Mode mesh",
            ),
            (
                "VERTEX_GROUP",
                "Vertex Group",
                "Use polygons whose vertices all have positive weight in a group",
            ),
        ],
        default="SELECTED",
        options=SKIP,
        translation_context=CONTEXT,
    )
    vertex_group: StringProperty(
        name="Face vertex group", options=SKIP, translation_context=CONTEXT
    )
    keyframes: IntProperty(
        name="Shadow keyframes",
        description="Number of keyframes in each complete boundary sweep",
        default=9,
        min=2,
        max=33,
        step=1,
        options=SKIP,
        translation_context=CONTEXT,
    )
    mirror_sweeps: BoolProperty(
        name="Mirror Full Sweep", default=True, options=SKIP, translation_context=CONTEXT
    )
    preset: EnumProperty(
        name="Starting preset",
        items=[
            ("CLEAN", "Clean Face", "Straight boundaries across the entire face"),
            ("NOSE", "Nose Accent", "More pronounced nose profile"),
        ],
        default="CLEAN",
        options=SKIP,
        translation_context=CONTEXT,
    )
    resolution: EnumProperty(
        name="Texture resolution",
        items=[(str(n), str(n) + " × " + str(n), "") for n in (512, 1024, 2048, 4096)],
        default="2048",
        options=SKIP,
        translation_context=CONTEXT,
    )
    output: StringProperty(
        name="Output file stem",
        subtype="FILE_PATH",
        default="//face_sdf",
        options=SKIP,
        translation_context=CONTEXT,
    )


def report_error(operator, context, exc):
    message = diagnostic(exc)
    i18n.launcher_notice = message
    if session.ACTIVE:
        session.ACTIVE.notify_error(exc)
    # An active popup owns its warning footer. Before it opens, use Blender's
    # warning report; ERROR reports would raise through bpy.ops.
    else:
        operator.report({"WARNING"}, report(message))
    if not isinstance(exc, ValueError):
        traceback.print_exc()
    return {"CANCELLED"}


class ANIME_SDF_GEN_OT_create(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.create"
    bl_label = "Create"
    bl_description = "Validate the face and open an isolated curve-authoring preview"

    def execute(self, context):
        p = context.window_manager.anime_sdf_gen
        try:
            if session.ACTIVE:
                session.ACTIVE.redraw()
                self.report({"INFO"}, report("Anime SDF Gen is already open in its editor window."))
                return {"FINISHED"}
            obj = context.view_layer.objects.active
            f = source.capture(obj, p.source_method, p.vertex_group)
            project = model.new_project(
                f.reference,
                f.alignment,
                p.keyframes,
                p.mirror_sweeps,
                p.preset,
                int(p.resolution),
                bpy.path.abspath(p.output),
            )
            project["authoring"]["stage"] = "ORIENT"
            session.start(context, project, f)
            i18n.launcher_notice = ""
            return {"FINISHED"}
        except Exception as exc:
            return report_error(self, context, exc)


class ANIME_SDF_GEN_OT_keyframe(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.keyframe"
    bl_label = "Select Shadow Keyframe"
    direction: StringProperty(default=model.LTR)
    index: IntProperty(default=0)

    def execute(self, context):
        try:
            s = current(self, ("EDIT",))
            if s is None:
                return {"CANCELLED"}
            s.select_keyframe(self.direction, self.index)
            return {"FINISHED"}
        except Exception as exc:
            return report_error(self, context, exc)


class ANIME_SDF_GEN_OT_layer(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.layer"
    bl_label = "Select Shape"
    index: IntProperty(default=0)

    def execute(self, context):
        s = current(self, ("EDIT",))
        if s is None:
            return {"CANCELLED"}
        if s:
            s.contour = max(0, min(self.index, len(s.keyframe["contours"]) - 1))
            s.point = 0
            s.reset_selection(whole_curve=True)
            s.sync_launcher()
            s.redraw()
        return {"FINISHED"}


class ANIME_SDF_GEN_OT_action(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.action"
    bl_label = "Edit Shadow Shapes"
    action: StringProperty()

    def execute(self, context):
        s = current(self)
        if s is None:
            return {"CANCELLED"}
        try:
            commands.action(s, self.action)
            return {"FINISHED"}
        except Exception as exc:
            return report_error(self, context, exc)


class ANIME_SDF_GEN_OT_transform(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.transform"
    bl_label = "Transform Closed Shape"
    dx: FloatProperty(name="Move X", precision=3, translation_context=CONTEXT)
    dy: FloatProperty(name="Move Y", precision=3, translation_context=CONTEXT)
    angle: FloatProperty(name="Rotate (degrees)", translation_context=CONTEXT)
    scale: FloatProperty(name="Scale", default=1, min=0.01, max=10, translation_context=CONTEXT)

    def invoke(self, context, event):
        s = current(self, ("EDIT",))
        if s is None:
            return {"CANCELLED"}
        bind(self, s, target=True)
        self.dx = self.dy = self.angle = 0
        self.scale = 1
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        s = current(self, ("EDIT",))
        if s is None:
            return {"CANCELLED"}
        try:
            commands.transform(s, self.dx, self.dy, self.angle, self.scale)
            return {"FINISHED"}
        except Exception as exc:
            return report_error(self, context, exc)


class ANIME_SDF_GEN_OT_settings(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.settings"
    bl_label = "Anime SDF Gen Settings"
    bl_description = "Edit the selected output, source, keyframe or point settings"
    section: StringProperty(default="RESOLUTION", options={"HIDDEN"})
    filename: StringProperty(
        name="File name",
        description="Base name shared by the textures and editable project",
        translation_context=CONTEXT,
    )
    resolution: EnumProperty(
        name="Resolution",
        items=[(str(n), f"{n} × {n}", "") for n in (512, 1024, 2048, 4096)],
        translation_context=CONTEXT,
    )
    bit_depth: EnumProperty(
        name="Output precision", items=DEPTH_ITEMS, default="16", translation_context=CONTEXT
    )
    smoothing: FloatProperty(
        name="Smoothing",
        description=SMOOTHING_HELP,
        min=0,
        max=8,
        default=0,
        precision=2,
        step=10,
        update=smoothing_dialog_changed,
        translation_context=CONTEXT,
    )
    uv_map: StringProperty(name="Output UV map", translation_context=CONTEXT)
    front_only: BoolProperty(name="Frontal surface only", default=True, translation_context=CONTEXT)
    keyframes: IntProperty(
        name="Shadow keyframes",
        description="Number of keyframes in each complete boundary sweep",
        min=2,
        max=33,
        default=9,
        translation_context=CONTEXT,
    )
    point_xy: FloatVectorProperty(
        name="Point (head space)",
        size=2,
        min=-100,
        max=100,
        precision=4,
        translation_context=CONTEXT,
    )
    handle_mode: EnumProperty(
        name="Handles",
        items=[("AUTO", "Smooth", ""), ("CORNER", "Corner", ""), ("FREE", "Free", "")],
        translation_context=CONTEXT,
    )
    handle_left: FloatVectorProperty(
        name="Incoming offset", size=2, precision=4, translation_context=CONTEXT
    )
    handle_right: FloatVectorProperty(
        name="Outgoing offset", size=2, precision=4, translation_context=CONTEXT
    )

    @classmethod
    def poll(cls, context):
        return session.ACTIVE is not None and not session.ACTIVE.busy

    def invoke(self, context, event):
        s = current(self)
        if s is None:
            return {"CANCELLED"}
        bind(self, s, target=self.section == "POINT")
        self.preview_ready = False
        settings = s.project["settings"]
        authoring = s.project["authoring"]
        pt = s.curve["points"][s.point]
        self.initial_smoothing = settings["smoothing"]
        self.bit_depth = str(settings["bit_depth"])
        self.smoothing = settings["smoothing"]
        self.resolution = str(settings["resolution"])
        self.uv_map = authoring["uv_map"]
        self.front_only = authoring["front_only"]
        self.keyframes = authoring["keyframe_count"]
        self.point_xy = pt["co"]
        self.handle_mode = pt["mode"]
        self.handle_left = pt["left"]
        self.handle_right = pt["right"]
        self.filename = Path(bpy.path.abspath(settings["output"])).name
        self.preview_ready = True
        return context.window_manager.invoke_props_dialog(self, width=390)

    def draw(self, context):
        layout = self.layout
        s = session.ACTIVE
        if not s:
            return
        if self.section == "RESOLUTION":
            layout.prop(self, "resolution")
        elif self.section == "BIT_DEPTH":
            layout.prop(self, "bit_depth", expand=True)
        elif self.section == "SMOOTHING":
            layout.prop(self, "smoothing", slider=True)
        elif self.section == "FILENAME":
            layout.prop(self, "filename")
        elif self.section == "SOURCE":
            layout.label(
                text=iface(msg("Source: {name}", name=s.project["source"]["object"])),
                translate=False,
                icon="MESH_DATA",
            )
            layout.label(
                text=iface(msg("Faces: {count}", count=len(s.project["source"]["faces"]))),
                translate=False,
            )
            obj = bpy.data.objects.get(s.project["source"]["object"])
            row = layout.column()
            row.enabled = s.stage == "ORIENT"
            if obj:
                row.prop_search(self, "uv_map", obj.data, "uv_layers")
            row.prop(self, "front_only")
            if s.stage != "ORIENT":
                layout.label(
                    text=iface("Change orientation to choose a different UV map."), translate=False
                )
        elif self.section == "KEYFRAME_COUNT":
            layout.prop(self, "keyframes")
        elif self.section == "POINT":
            layout.prop(self, "point_xy")
            layout.prop(self, "handle_mode")
            if self.handle_mode == "FREE":
                layout.prop(self, "handle_left")
                layout.prop(self, "handle_right")

    def execute(self, context):
        allowed = {
            "POINT": ("EDIT",),
            "KEYFRAME_COUNT": ("ORIENT", "FIT"),
            "RESOLUTION": ("CONFIRM",),
            "BIT_DEPTH": ("CONFIRM",),
            "SMOOTHING": ("CONFIRM",),
            "FILENAME": ("CONFIRM",),
        }
        s = current(self, allowed.get(self.section))
        if s is None:
            return {"CANCELLED"}
        try:
            if self.section == "POINT":
                commands.point(
                    s, self.point_xy, self.handle_mode, self.handle_left, self.handle_right
                )
            elif self.section == "SMOOTHING":
                s.preview.set_smoothing(self.smoothing)
            else:
                with s.edit(history=self.section == "KEYFRAME_COUNT", invalidate=False):
                    if self.section == "RESOLUTION":
                        s.project["settings"]["resolution"] = int(self.resolution)
                    elif self.section == "BIT_DEPTH":
                        s.project["settings"]["bit_depth"] = int(self.bit_depth)
                    elif self.section == "FILENAME":
                        name = self.filename.strip()
                        if name.lower().endswith((".png", ".exr")):
                            name = name[:-4]
                        if (
                            not name
                            or name in (".", "..")
                            or name.endswith(".")
                            or any(c in name for c in '<>:"/\\|?*')
                        ):
                            raise UserError(
                                "Choose a file name without path separators or reserved characters."
                            )
                        s.project["settings"]["output"] = str(
                            Path(bpy.path.abspath(s.project["settings"]["output"])).parent / name
                        )
                    elif self.section == "SOURCE" and s.stage == "ORIENT":
                        s.project["authoring"].update(
                            uv_map=self.uv_map, front_only=self.front_only
                        )
                    elif self.section == "KEYFRAME_COUNT":
                        s.project["authoring"]["keyframe_count"] = max(
                            model.MIN_KEYFRAMES, min(model.MAX_KEYFRAMES, self.keyframes)
                        )
            return {"FINISHED"}
        except Exception as exc:
            return report_error(self, context, exc)

    def cancel(self, context):
        s = current(self, ("CONFIRM",))
        if self.section == "SMOOTHING" and s:
            s.preview.set_smoothing(self.initial_smoothing)


class ANIME_SDF_GEN_OT_packing(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.packing"
    bl_label = "Texture Map Output"
    bl_description = "Choose an RGB channel or an individual grayscale texture"
    map_name: StringProperty(options={"HIDDEN"})
    route: EnumProperty(
        name="Output channel",
        items=[(r, "Separate" if r == "SEPARATE" else r, "") for r in model.OUTPUT_ROUTES],
        translation_context=CONTEXT,
    )

    @classmethod
    def poll(cls, context):
        s = session.ACTIVE
        return s is not None and s.stage == "CONFIRM" and not s.busy

    def execute(self, context):
        s = current(self, ("CONFIRM",))
        if s is None:
            return {"CANCELLED"}
        try:
            with s.edit(history=False, invalidate=False):
                model.set_packing(s.project, self.map_name, self.route)
            return {"FINISHED"}
        except Exception as exc:
            return report_error(self, context, exc)


class ANIME_SDF_GEN_OT_destination(bpy.types.Operator, ExportHelper):
    bl_idname = "anime_sdf_gen.destination"
    bl_label = "Choose Output Location"
    bl_description = (
        "Choose the destination and file name; files are written only by Generate & Finish"
    )
    filename_ext = ".png"
    filter_glob: StringProperty(default="*.png", options={"HIDDEN"})
    check_existing: BoolProperty(default=False, options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        s = session.ACTIVE
        return s is not None and s.stage == "CONFIRM" and not s.busy

    def invoke(self, context, event):
        s = current(self, ("CONFIRM",))
        if s is None:
            return {"CANCELLED"}
        bind(self, s)
        self.filename_ext = output_extension(s.project)
        self.filter_glob = "*" + self.filename_ext
        base = Path(bpy.path.abspath(s.project["settings"]["output"]))
        if base.suffix.lower() in (".png", ".exr"):
            base = base.with_suffix("")
        self.filepath = str(base) + self.filename_ext
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        s = session.ACTIVE
        if current(self, ("CONFIRM",)) is None:
            return {"CANCELLED"}
        path = bpy.path.abspath(self.filepath)
        if not path.strip():
            return report_error(self, context, UserError("Choose a save location."))
        if path.lower().endswith((".png", ".exr")):
            path = path[:-4]
        with s.edit(history=False, invalidate=False):
            s.project["settings"]["output"] = path
        return {"FINISHED"}


class ANIME_SDF_GEN_OT_landmark(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.landmark"
    bl_label = "Select Fitting Landmark"
    name: StringProperty(default="nose")

    def execute(self, context):
        if current(self, ("FIT",)) is None:
            return {"CANCELLED"}
        if session.ACTIVE:
            session.ACTIVE.landmark = self.name
            session.ACTIVE.sync_launcher()
            session.ACTIVE.redraw()
        return {"FINISHED"}


class ANIME_SDF_GEN_OT_generate(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.generate"
    bl_label = "Generate & Finish"
    bl_description = (
        "Verify and export the textures and editable project, then restore your workspace"
    )

    def invoke(self, context, event):
        s = current(self, ("CONFIRM",))
        if s is None:
            return {"CANCELLED"}
        bind(self, s, snapshot=True)
        if s:
            base = bpy.path.abspath(s.project["settings"]["output"])
            try:
                existing = any(path.exists() for path in output_paths(s.project, base))
            except Exception as exc:
                return report_error(self, context, exc)
            if existing:
                return context.window_manager.invoke_confirm(
                    self,
                    event,
                    title=iface("Replace existing SDF output?"),
                    message=iface(
                        "Existing files in this output set will be replaced together after verification."
                    ),
                    confirm_text=iface("Replace & Generate"),
                )
        return self.execute(context)

    def execute(self, context):
        s = current(self, ("CONFIRM",))
        if s is None:
            return {"CANCELLED"}
        try:
            s.export.start()
            return {"FINISHED"}
        except Exception as exc:
            return report_error(self, context, exc)


class ANIME_SDF_GEN_OT_cancel_generation(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.cancel_generation"
    bl_label = "Cancel Generation"

    def execute(self, context):
        if session.ACTIVE:
            session.ACTIVE.export.cancel()
        return {"FINISHED"}


class ANIME_SDF_GEN_OT_close(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.close"
    bl_label = "Discard & Close"

    def execute(self, context):
        if session.ACTIVE and session.ACTIVE.editor:
            session.ACTIVE.close_requested = True
        else:
            session.end_session(remove_draft=True)
        return {"FINISHED"}


class ANIME_SDF_GEN_OT_save_draft(bpy.types.Operator, ExportHelper):
    bl_idname = "anime_sdf_gen.save_draft"
    bl_label = "Save Draft & Close"
    filename_ext = ".sdfproject.json"
    filter_glob: StringProperty(default="*.sdfproject.json", options={"HIDDEN"})

    def invoke(self, context, event):
        s = current(self)
        if s is None:
            return {"CANCELLED"}
        bind(self, s)
        self.filepath = bpy.path.abspath(s.project["settings"]["output"]) + ".draft.sdfproject.json"
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        if current(self) is None:
            return {"CANCELLED"}
        try:
            if session.ACTIVE:
                atomic_text(self.filepath, model.dumps(session.ACTIVE.project))
                try:
                    automatic = session.draft_root() / (
                        session.ACTIVE.project["id"] + ".sdfproject.json"
                    )
                    remove_draft = Path(self.filepath).resolve() != automatic.resolve()
                except OSError:
                    remove_draft = True
                if session.ACTIVE.editor:
                    session.ACTIVE.close_requested = remove_draft
                else:
                    session.end_session(remove_draft=remove_draft)
            self.report({"INFO"}, report("Draft saved; original workspace restored."))
            return {"FINISHED"}
        except Exception as exc:
            return report_error(self, context, exc)


class ANIME_SDF_GEN_OT_open(bpy.types.Operator, ImportHelper):
    bl_idname = "anime_sdf_gen.open_project"
    bl_label = "Edit Existing SDF"
    bl_description = "Open an editable SDF project and validate its source model"
    filename_ext = ".sdfproject.json"
    filter_glob: StringProperty(default="*.sdfproject.json", options={"HIDDEN"})
    relink: BoolProperty(
        name="Relink to Active Source",
        description="Capture the active mesh selection or chosen vertex group, then orient and fit again",
        translation_context=CONTEXT,
    )

    def execute(self, context):
        try:
            if session.ACTIVE:
                raise UserError(
                    "Finish or close the current authoring session before opening another project."
                )
            p = load_project(self.filepath)
            props = context.window_manager.anime_sdf_gen
            if self.relink:
                obj = context.view_layer.objects.active
                f = source.capture(obj, props.source_method, props.vertex_group)
                p["source"], p["alignment"] = f.reference, f.alignment
                p["authoring"].update(stage="ORIENT", anchors={}, uv_map=f.reference["uv_map"])
            else:
                f = source.from_reference(
                    p["source"], p["alignment"], validate=p["authoring"]["stage"] != "ORIENT"
                )
            session.start(context, p, f)
            return {"FINISHED"}
        except Exception as exc:
            return report_error(self, context, exc)


class ANIME_SDF_GEN_OT_recover(bpy.types.Operator):
    bl_idname = "anime_sdf_gen.recover"
    bl_label = "Recover Latest Draft"
    bl_description = "Reopen the most recent automatic recovery draft"

    def execute(self, context):
        try:
            drafts = sorted(
                session.draft_root().glob("*.sdfproject.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not drafts:
                raise UserError("No recovery drafts are available.")
            return bpy.ops.anime_sdf_gen.open_project(filepath=str(drafts[0]))
        except Exception as exc:
            return report_error(self, context, exc)


def wrapped(layout, text, width=44, icon=None, translate=True):
    value = iface(text) if translate else text
    available = max(80 * scale(), min(width * 7 * scale(), bpy.context.region.width - 36 * scale()))
    for index, line in enumerate(wrap(value, available, 12) or [""]):
        if index == 0 and icon:
            layout.label(text=line, icon=icon, translate=False)
        else:
            layout.label(text=line, translate=False)


class ANIME_SDF_GEN_PT_launcher(bpy.types.Panel):
    bl_label = "Anime SDF Gen"
    bl_idname = "ANIME_SDF_GEN_PT_launcher"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Anime SDF Gen"

    @classmethod
    def poll(cls, context):
        s = session.ACTIVE
        return not s or not s.editor or context.window != s.editor.window

    def draw(self, context):
        layout = self.layout
        p = context.window_manager.anime_sdf_gen
        s = session.ACTIVE
        if s:
            wrapped(layout, "Your authoring session is in the Anime SDF Gen popup.", icon="WINDOW")
            return
        obj = context.view_layer.objects.active
        layout.label(
            text=iface(
                msg("Active: {name}", name=obj.name)
                if obj and obj.type == "MESH"
                else "Make a mesh active."
            ),
            translate=False,
            icon="MESH_DATA",
        )
        layout.prop(p, "source_method")
        if p.source_method == "VERTEX_GROUP" and obj and obj.type == "MESH":
            layout.prop_search(p, "vertex_group", obj, "vertex_groups")
        else:
            wrapped(layout, "Select facial geometry in Edit Mode, then Create.")
        layout.prop(p, "keyframes")
        row = layout.row()
        row.scale_y = 1.5
        row.operator("anime_sdf_gen.create", icon="CURVE_BEZCURVE")
        layout.operator("anime_sdf_gen.open_project", icon="FILE_FOLDER")
        layout.operator("anime_sdf_gen.recover", icon="RECOVER_LAST")
        if i18n.launcher_notice:
            wrapped(layout, report(i18n.launcher_notice), icon="ERROR", translate=False)


CLASSES = (
    ANIME_SDF_GEN_Properties,
    ANIME_SDF_GEN_OT_create,
    ANIME_SDF_GEN_OT_keyframe,
    ANIME_SDF_GEN_OT_layer,
    ANIME_SDF_GEN_OT_action,
    ANIME_SDF_GEN_OT_transform,
    ANIME_SDF_GEN_OT_settings,
    ANIME_SDF_GEN_OT_packing,
    ANIME_SDF_GEN_OT_destination,
    ANIME_SDF_GEN_OT_landmark,
    ANIME_SDF_GEN_OT_generate,
    ANIME_SDF_GEN_OT_cancel_generation,
    ANIME_SDF_GEN_OT_close,
    ANIME_SDF_GEN_OT_save_draft,
    ANIME_SDF_GEN_OT_open,
    ANIME_SDF_GEN_OT_recover,
    ANIME_SDF_GEN_OT_interact,
    ANIME_SDF_GEN_PT_launcher,
)


_registered_classes = []


def register():
    try:
        for cls in CLASSES:
            cls.bl_translation_context = CONTEXT
            bpy.utils.register_class(cls)
            _registered_classes.append(cls)
        bpy.types.WindowManager.anime_sdf_gen = PointerProperty(
            type=ANIME_SDF_GEN_Properties, options=SKIP
        )
        session.register_handlers()
    except Exception:
        unregister()
        raise


def unregister():
    session.unregister_handlers()
    if hasattr(bpy.types.WindowManager, "anime_sdf_gen"):
        del bpy.types.WindowManager.anime_sdf_gen
    while _registered_classes:
        bpy.utils.unregister_class(_registered_classes.pop())
