"""Read-only extraction of a face region from the user's evaluated source mesh."""
from dataclasses import dataclass
import hashlib
import bpy
import numpy as np
from mathutils import Vector
from .core.geometry import validate_uv

@dataclass
class FaceSource:
    reference: dict
    alignment: dict
    vertices: np.ndarray
    triangles: np.ndarray
    uvs: np.ndarray
    projected: np.ndarray
    triangle_vertices: np.ndarray = None
    material_indices: np.ndarray = None
    materials: list = None
    uv_layers: dict = None


def selected_faces(obj):
    """Read current edit selection, including fully selected vertices/edges."""
    if obj.mode == 'EDIT':
        import bmesh
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        mode = bpy.context.tool_settings.mesh_select_mode
        return [f.index for f in bm.faces if not f.hide and
                (f.select or (mode[0] and all(v.select and not v.hide for v in f.verts))
                 or (mode[1] and all(e.select and not e.hide for e in f.edges)))]
    return [p.index for p in obj.data.polygons if p.select and not p.hide]


def capture(obj, region='SELECTED', group='', uv_name='', require_edit=True):
    if not obj or obj.type != 'MESH':
        raise ValueError('Make a mesh active before creating an SDF project.')
    if region == 'SELECTED' and require_edit and obj.mode != 'EDIT':
        raise ValueError('Select facial geometry in Edit Mode, or choose Vertex Group.')
    uv_name = uv_name or (obj.data.uv_layers.active.name if obj.data.uv_layers.active else '')
    ids = selected_faces(obj) if region == 'SELECTED' else None
    return extract(obj, uv_name, region=region, selected=ids, group=group,
                   validate=False, front_only=False)


def fit_frame(vertices, forward, up):
    f = np.asarray(forward, dtype=float); f /= np.linalg.norm(f)
    u = np.asarray(up, dtype=float); u -= f*np.dot(u, f)
    if np.linalg.norm(u) < 1e-8:
        raise ValueError('Face forward and up must be different directions.')
    u /= np.linalg.norm(u); r = np.cross(u, f)
    center = (vertices.min(axis=0)+vertices.max(axis=0))/2
    raw = (vertices-center) @ np.stack([r,u,f], axis=1)
    extents = np.ptp(raw[:, :2], axis=0)
    if extents.min() < 1e-8:
        raise ValueError('The face projection has zero width or height. Orbit to face the character.')
    center += r*(raw[:,0].max()+raw[:,0].min())/2+u*(raw[:,1].max()+raw[:,1].min())/2
    return {'center':center.tolist(), 'forward':f.tolist(), 'up':u.tolist(),
            'right':r.tolist(), 'width':float(extents[0]), 'height':float(extents[1])}


def extract(obj,*args,**kwargs):
    # UV RNA collections are empty while their mesh is in Edit Mode. Flush via
    # Blender's mode operator, evaluate a temporary mesh, then restore the user's
    # mode/selection even when validation fails. Mesh content is never edited.
    if obj and obj.type=='MESH' and obj.mode=='EDIT':
        layer=bpy.context.view_layer
        active=layer.objects.active
        selection=[o for o in layer.objects if o.select_get()]
        bpy.ops.object.mode_set(mode='OBJECT')
        try:
            return _extract_object_mode(obj,*args,**kwargs)
        finally:
            for item in layer.objects:item.select_set(item in selection)
            layer.objects.active=active
            bpy.ops.object.mode_set(mode='EDIT')
    return _extract_object_mode(obj,*args,**kwargs)


def _extract_object_mode(obj, uv_name, region="SELECTED", selected=None,
            alignment=None, validate=True, front_only=False, group=''):
    if not obj or obj.type != 'MESH':
        raise ValueError("Select a source mesh first.")
    if uv_name not in obj.data.uv_layers:
        raise ValueError(f"The source has no UV map named {uv_name}.")
    if selected is None:
        selected = [p.index for p in obj.data.polygons if p.select and not p.hide]
    if region == "SELECTED":
        face_ids = set(selected)
    elif region == 'VERTEX_GROUP':
        vg = obj.vertex_groups.get(group)
        if vg is None:
            raise ValueError(f"Vertex group '{group}' is missing on {obj.name}.")
        members = {v.index for v in obj.data.vertices if any(g.group == vg.index and g.weight > 0 for g in v.groups)}
        face_ids = {p.index for p in obj.data.polygons if all(v in members for v in p.vertices)}
    else:
        raise ValueError('Unknown face region type.')
    if not face_ids:
        raise ValueError("The face region is empty. Select complete visible faces or a group containing complete faces.")
    if any(i < 0 or i >= len(obj.data.polygons) for i in face_ids):
        raise ValueError('The saved face region no longer matches the mesh. Relink the source.')
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get())
    try:
        if len(mesh.vertices) != len(obj.data.vertices) or len(mesh.polygons) != len(obj.data.polygons):
            raise ValueError("This version needs topology-preserving evaluation. Disable topology-changing modifiers on a source copy before authoring.")
        if uv_name not in mesh.uv_layers:
            raise ValueError("The evaluated mesh has lost the selected UV map.")
        mesh.calc_loop_triangles()
        tris = [t for t in mesh.loop_triangles if t.polygon_index in face_ids]
        if not tris:
            raise ValueError("No face triangles were found.")
        vids = sorted({v for t in tris for v in t.vertices})
        remap = {v: i for i, v in enumerate(vids)}
        vertices = np.asarray([list(obj.matrix_world @ mesh.vertices[v].co) for v in vids], dtype=np.float64)
        triangles = np.asarray([[remap[v] for v in t.vertices] for t in tris], dtype=np.int32)
        layer = mesh.uv_layers[uv_name]
        uvs = np.asarray([[list(layer.data[li].uv) for li in t.loops] for t in tris], dtype=np.float64)
        all_uvs = {uv.name: np.asarray([[list(uv.data[li].uv) for li in t.loops] for t in tris], dtype=np.float64)
                   for uv in mesh.uv_layers}
        triangle_vertices = np.asarray([list(t.vertices) for t in tris], dtype=np.int32)
        material_indices = np.asarray([t.material_index for t in tris], dtype=np.int32)
        materials = list(obj.data.materials)
        if alignment is None:
            alignment = fit_frame(vertices, (0,-1,0), (0,0,1))
        matrix = np.stack([alignment["right"], alignment["up"], alignment["forward"]], axis=1)
        local = (vertices-np.asarray(alignment["center"])) @ matrix
        local[:, 0] = local[:, 0]/alignment["width"]+.5
        local[:, 1] = local[:, 1]/alignment["height"]+.5
        local[:, 2] /= max(alignment["width"], alignment["height"])
        excluded = 0
        if front_only:
            from .core.geometry import area
            keep = area(local[triangles][..., :2]) > 1e-10
            excluded = int((~keep).sum())
            triangles, uvs = triangles[keep], uvs[keep]
            triangle_vertices, material_indices = triangle_vertices[keep], material_indices[keep]
            all_uvs = {name: arr[keep] for name, arr in all_uvs.items()}
            if not len(triangles):
                raise ValueError("The frontal subset is empty. Reset the face orientation.")
        if validate:
            validate_uv(uvs, vertices[triangles])
        digest = hashlib.sha256()
        for array in (vertices, triangles, uvs):
            digest.update(np.ascontiguousarray(array).tobytes())
        reference = {"blend_file": bpy.data.filepath, "object": obj.name, "mesh": obj.data.name,
                     "uv_map": uv_name, "region": region,
                     "faces": sorted(face_ids), "front_only": front_only,
                     "vertex_group": group,
                     "excluded_triangles": excluded, "fingerprint": digest.hexdigest()}
        return FaceSource(reference, alignment, vertices, triangles, uvs, local[triangles],
                          triangle_vertices, material_indices, materials, all_uvs)
    finally:
        evaluated.to_mesh_clear()


def from_reference(ref, alignment, obj=None, validate=True, allow_relink=False):
    target = obj or bpy.data.objects.get(ref["object"])
    face = extract(target, ref["uv_map"], region=ref["region"],
                   selected=ref["faces"], alignment=alignment, validate=validate,
                   front_only=ref.get('front_only',False), group=ref.get('vertex_group',''))
    if not allow_relink and face.reference['faces'] != ref['faces']:
        raise ValueError('Vertex-group membership changed. Relink the source before regenerating.')
    if not allow_relink and face.reference["fingerprint"] != ref["fingerprint"]:
        raise ValueError("The source geometry, pose, or UVs changed. Reopen with 'Relink to Active Source' after checking its face region.")
    return face


def world_point(alignment, xy, depth):
    return (Vector(alignment["center"])+Vector(alignment["right"])*(xy[0]-.5)*alignment["width"]+
            Vector(alignment["up"])*(xy[1]-.5)*alignment["height"]+Vector(alignment["forward"])*depth)
