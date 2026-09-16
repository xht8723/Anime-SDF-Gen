"""Full-size projected curves, surface landmarks, and live inspection."""

import time
import math
import traceback
from . import interface
from .i18n import iface
import bpy
import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_texture_2d
from mathutils import Vector
from .viewport import scale
from .canvas import label, lines, disc, rect, to_view, contour_lines
from .core import curves, model


def face_shader():
    info = gpu.types.GPUShaderCreateInfo()
    info.vertex_in(0, "VEC3", "pos")
    info.vertex_in(1, "VEC3", "normal")
    info.vertex_in(2, "VEC2", "texCoord")
    interface = gpu.types.GPUStageInterfaceInfo("anime_sdf_gen_interface")
    interface.smooth("VEC2", "uv")
    interface.smooth("VEC3", "surfaceNormal")
    info.vertex_out(interface)
    info.push_constant("MAT4", "viewProjection")
    info.push_constant("VEC3", "lightDirection")
    info.push_constant("VEC3", "faceForward")
    info.push_constant("FLOAT", "flatView")
    info.sampler(0, "FLOAT_2D", "image")
    info.fragment_out(0, "VEC4", "fragColor")
    info.vertex_source(
        "void main(){uv=texCoord;surfaceNormal=normal;gl_Position=viewProjection*vec4(pos,1.0);}"
    )
    info.fragment_source("""void main(){
        vec3 mask=texture(image,uv).rgb;
        vec3 n=normalize(surfaceNormal);
        float shadow=step(0.5,mask.r);
        vec3 lit=mix(vec3(0.78,0.69,0.56),vec3(1.0),flatView);
        vec3 dark=mix(vec3(0.16,0.21,0.30),vec3(0.0),flatView);
        vec3 color=mix(lit,dark,shadow);
        float form=0.45+0.55*max(0.0,dot(n,lightDirection));
        color*=mix(form,1.0,flatView);
        if(dot(n,faceForward)<=0.0 || mask.b<0.5) color=vec3(0.12);
        if(mask.g>0.5) color=vec3(1.0,0.015,0.38);
        fragColor=vec4(color,1.0);
    }""")
    return gpu.shader.create_from_info(info)


def draw_author(s, region, view):
    if s.stage != "EDIT":
        return
    frames = model.sweep(s.project, s.direction)
    for index in (s.key_index - 1, s.key_index + 1):
        if 0 <= index < len(frames):
            for c in frames[index]["contours"]:
                if c.get("enabled", True):
                    contour_lines(s, c, region, view, (0.4, 0.8, 0.9, 0.3))
    selected_contours = {ci for ci, _ in s.selected}
    for ci, c in enumerate(s.keyframe["contours"]):
        if not c.get("enabled", True):
            continue
        color = (1, 0.65, 0.18, 1) if ci in selected_contours else (0.4, 0.85, 0.9, 0.8)
        contour_lines(s, c, region, view, color, 2)
        for pi, p in enumerate(c["points"]):
            q = to_view(s, p["co"], view)
            if q is None:
                continue
            selected = (ci, pi) in s.selected
            active = ci == s.contour and pi == s.point
            disc(
                *q,
                6 if active and selected else 4,
                (1, 0.65, 0.18, 1) if selected else (0.4, 0.8, 0.88, 0.8)
            )
            if active and selected:
                for handle in curves.handles(c, pi):
                    h = to_view(s, handle, view)
                    if h is not None:
                        lines([q, h], (0.94, 0.9, 0.55, 0.85))
                        disc(*h, 3, (0.95, 0.9, 0.65, 1))


def draw_landmarks(s, view):
    for name, anchor in s.project["authoring"]["anchors"].items():
        q = view.project(anchor["world"])
        if q is None:
            continue
        color = (0.25, 1, 0.55, 1) if name == s.landmark else (0.5, 0.87, 0.75, 1)
        disc(*q, 5, color)
        label(
            iface({"nose": "Nose", "mouth": "Mouth Center", "chin": "Chin"}[name]),
            q.x + 10 * scale(),
            q.y + 5 * scale(),
            12,
            color,
        )


def draw_face(s, view):
    if s.preview._face_shader is None:
        s.preview._face_shader = face_shader()
    if s.preview._face_batch is None:
        mesh = s.preview_object.data
        normals = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("normal", normals)
        indices = s.face.triangles.ravel()
        s.preview._face_batch = batch_for_shader(
            s.preview._face_shader,
            "TRIS",
            {
                "pos": s.face.vertices[indices].astype(np.float32),
                "normal": normals.reshape(-1, 3)[indices],
                "texCoord": ((s.face.projected[..., :2] + model.PAD) / model.SPAN)
                .reshape(-1, 2)
                .astype(np.float32),
            },
        )
    a = s.project["alignment"]
    shader = s.preview._face_shader
    shader.bind()
    shader.uniform_float("viewProjection", view.perspective_matrix)
    angle = math.radians(s.rotation)
    light = (
        Vector(a["forward"]) * math.cos(angle)
        + Vector(a["right"]) * math.sin(angle)
        + Vector(a["up"]) * 0.25
    )
    shader.uniform_float("lightDirection", light.normalized())
    shader.uniform_float("faceForward", a["forward"])
    shader.uniform_float("flatView", 1.0 if s.flat else 0.0)
    # Image.update() does not invalidate every backend's from_image cache in
    # an offscreen draw. Upload this revision explicitly in the GPU context.
    if (
        s.preview._mask_texture is None
        or s.preview._mask_texture_revision != s.preview.mask_revision
    ):
        s.preview._mask_texture = gpu.types.GPUTexture(
            (s.size, s.size),
            format="RGBA32F",
            data=gpu.types.Buffer("FLOAT", s.preview.rgba.size, s.preview.rgba.ravel()),
        )
        s.preview._mask_texture.filter_mode(False)
        s.preview._mask_texture_revision = s.preview.mask_revision
    shader.uniform_sampler("image", s.preview._mask_texture)
    gpu.state.blend_set("NONE")
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.depth_mask_set(True)
    s.preview._face_batch.draw(shader)


def view_buffer(s, role, native_region):
    e = s.editor
    v = e.views[role]
    r = v.region
    size = (max(1, r.width), max(1, r.height))
    buffer = e.buffers.get(role)
    if buffer is None or (buffer.width, buffer.height) != size:
        if buffer:
            buffer.free()
        buffer = e.buffers[role] = gpu.types.GPUOffScreen(*size)
        e.reference_keys.pop(role, None)
    if role == "PREVIEW" and s.stage in ("EDIT", "CONFIRM"):
        e.reference_keys.pop(role, None)
        with buffer.bind(), gpu.matrix.push_pop():
            gpu.state.active_framebuffer_get().clear(color=(0.055, 0.065, 0.083, 1), depth=1.0)
            draw_face(s, v)
    else:
        key = (
            e.geometry_revision,
            s.project["authoring"]["reference"],
            tuple(v.view_location),
            tuple(v.view_rotation),
            v.view_distance,
            v.view_perspective,
            size,
        )
        if e.reference_keys.get(role) != key:
            buffer.draw_view3d(
                s.scene,
                s.scene.view_layers[0],
                e.reference_space,
                native_region,
                v.view_matrix,
                v.projection_matrix,
                do_color_management=True,
            )
            e.reference_keys[role] = key
    return buffer


def draw_popup(s):
    if s.closed or not s.editor or not s.editor.owns_context(bpy.context):
        return
    start = time.perf_counter()
    e = s.editor
    region = bpy.context.region
    old_blend = gpu.state.blend_get()
    old_depth = gpu.state.depth_test_get()
    old_mask = gpu.state.depth_mask_get()
    old_scissor = gpu.state.scissor_get()
    old_viewport = gpu.state.viewport_get()
    old_model = gpu.matrix.get_model_view_matrix()
    old_projection = gpu.matrix.get_projection_matrix()
    try:
        e.navigation.drawing = True
        s.normalize_selection()
        e.navigation.poll()
        e.resize(region)
        buffers = {
            name: view_buffer(s, name, region) for name in ("AUTHOR", "PREVIEW") if name in e.boxes
        }
        gpu.state.depth_test_set("NONE")
        gpu.state.depth_mask_set(False)
        gpu.state.blend_set("ALPHA")
        gpu.state.viewport_set(*old_viewport)
        gpu.matrix.load_matrix(old_model)
        gpu.matrix.load_projection_matrix(old_projection)
        rect(0, 0, region.width, region.height, interface.BG)
        for name, buffer in buffers.items():
            v = e.views[name]
            r = v.region
            draw_texture_2d(buffer.texture_color, (r.x, r.y), r.width, r.height)
            gpu.state.scissor_test_set(True)
            gpu.state.scissor_set(r.x, r.y, r.width, r.height)
            with gpu.matrix.push_pop():
                gpu.matrix.translate((r.x, r.y, 0))
                if name == "AUTHOR":
                    draw_author(s, r, v)
                if name == "AUTHOR" and s.curve_edit:
                    s.curve_edit.draw(r, v)
                if s.stage == "FIT":
                    draw_landmarks(s, v)
            gpu.state.scissor_test_set(False)
        interface.build(s, region)
        s._draw_error = None
        if s.dragging or s.playing:
            if not hasattr(s, "frame_times"):
                s.frame_times = []
            s.frame_times.append(time.perf_counter())
            s.frame_times = s.frame_times[-512:]
    except Exception as exc:
        if getattr(s, "_draw_error", None) != str(exc):
            traceback.print_exc()
            s._draw_error = str(exc)
            s.notify_error(exc)
        # A failed preview must not remove the controls needed to recover/close.
        gpu.state.scissor_test_set(False)
        gpu.state.viewport_set(*old_viewport)
        gpu.state.depth_test_set("NONE")
        gpu.state.depth_mask_set(False)
        gpu.matrix.load_matrix(old_model)
        gpu.matrix.load_projection_matrix(old_projection)
        interface.build(s, region)
    finally:
        e.navigation.drawing = False
        gpu.state.scissor_set(*old_scissor)
        gpu.state.scissor_test_set(False)
        gpu.state.viewport_set(*old_viewport)
        gpu.matrix.load_matrix(old_model)
        gpu.matrix.load_projection_matrix(old_projection)
        gpu.state.depth_test_set(old_depth)
        gpu.state.depth_mask_set(old_mask)
        gpu.state.line_width_set(1)
        gpu.state.blend_set(old_blend)
        s.last_draw_ms = (time.perf_counter() - start) * 1000


def attach(s):
    s.registry.draw_handlers.append(
        (bpy.types.SpaceView3D.draw_handler_add(draw_popup, (s,), "WINDOW", "POST_PIXEL"), "WINDOW")
    )
