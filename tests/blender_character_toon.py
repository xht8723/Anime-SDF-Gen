"""Render and driver checks. Run only on a disposable copy of character_toon_sdf.blend."""
from pathlib import Path
import json
import math
import sys
import traceback

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build' / 'validation' / 'toon-sdf'
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from tools import setup_character_toon as setup

report = {'status': 'RUNNING', 'checks': [], 'renders': []}


def update():
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    bpy.context.view_layer.update()


def read_direction(name):
    tree = bpy.data.node_groups[setup.RIG].evaluated_get(bpy.context.evaluated_depsgraph_get())
    return Vector(tuple(s.default_value for s in tree.nodes[name].inputs))


def aim_sun(vector):
    sun = bpy.data.objects['Sun']
    sun.rotation_mode = 'QUATERNION'
    sun.rotation_quaternion = Vector(vector).normalized().to_track_quat('Z', 'Y')
    update()


def render(path, width=512, height=512):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    report['renders'].append(str(path))


def camera_at(position, target, scale):
    scene = bpy.context.scene
    camera = scene.camera
    if not camera or camera.name != 'Toon Validation Camera':
        data = bpy.data.cameras.new('Toon Validation Camera')
        camera = bpy.data.objects.new('Toon Validation Camera', data)
        scene.collection.objects.link(camera)
        scene.camera = camera
    camera.location = position
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = scale
    update()
    return camera


def driver_checks():
    rig = bpy.data.node_groups[setup.RIG]
    assert len(rig.animation_data.drivers) == 9
    assert all(fc.driver.is_valid and fc.driver.is_simple_expression for fc in rig.animation_data.drivers)
    sun = bpy.data.objects['Sun']
    body = bpy.data.objects['body']
    frame = bpy.data.objects[setup.FRAME]
    sun_matrix, body_matrix = sun.matrix_world.copy(), body.matrix_world.copy()
    for angles in ((0, 0, 0), (0.3, -0.8, 2.1), (-1.2, 1.570796, -0.6)):
        sun.rotation_mode = 'XYZ'
        sun.rotation_euler = angles
        update()
        expected = sun.matrix_world.to_quaternion() @ Vector((0, 0, 1))
        assert (read_direction('To Sun') - expected).length < 0.00001
    aim_sun((0.4, -0.8, 0.2))
    before = read_direction('To Sun')
    sun.location += Vector((8, -5, 2))
    update()
    assert (read_direction('To Sun') - before).length < 0.00001
    parent = bpy.data.objects.new('Validation Sun Parent', None)
    bpy.context.scene.collection.objects.link(parent)
    parent.rotation_euler = (0.25, -0.5, 1.1)
    sun.parent = parent
    update()
    expected = sun.matrix_world.to_quaternion() @ Vector((0, 0, 1))
    assert (read_direction('To Sun') - expected).length < 0.00001
    sun.parent = None
    sun.matrix_world = sun_matrix
    bpy.data.objects.remove(parent, do_unlink=True)
    body.rotation_mode = 'QUATERNION'
    body.rotation_quaternion = Euler((0.15, -0.1, 1.05)).to_quaternion()
    update()
    for name, axis in (('Character Left', (1, 0, 0)), ('Face Forward', (0, 0, 1))):
        expected = frame.matrix_world.to_quaternion() @ Vector(axis)
        assert (read_direction(name) - expected).length < 0.00001
    body.matrix_world = body_matrix
    update()
    report['checks'].append('Saved transform drivers evaluate without autorun: Sun rotation, quaternion and Euler modes, parenting, translation invariance, and head rotation.')


def shader_probe():
    # Four independent GPU-rendered threshold swatches include both sentinels.
    scene = bpy.context.scene
    original_meshes = [o for o in scene.objects if o.type == 'MESH']
    visibility = {o: o.hide_render for o in original_meshes}
    for obj in original_meshes:
        obj.hide_render = True
    mesh = bpy.data.meshes.new('Validation SDF Swatches')
    mesh.from_pydata([(-1, 0, -0.5), (1, 0, -0.5), (1, 0, 0.5), (-1, 0, 0.5)], [], [(0, 1, 2, 3)])
    mesh.uv_layers.new(name='UVMap')
    for i, uv in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        mesh.uv_layers[0].data[i].uv = uv
    plane = bpy.data.objects.new('Validation SDF Swatches', mesh)
    scene.collection.objects.link(plane)
    material = bpy.data.materials.new('Validation SDF Probe')
    material.use_nodes = True
    material.node_tree.nodes.clear()
    plane.data.materials.append(material)
    tree = material.node_tree
    tex = setup.node(tree, 'ShaderNodeTexImage', 'Known Thresholds', -500, 0)
    img = bpy.data.images.new('Known Thresholds', width=4, height=1, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    left = np.array([0, 0.25, 0.75, 1], dtype=float)
    right = np.array([1, 0.75, 0.25, 0], dtype=float)
    img.pixels[:] = np.column_stack((left, right, np.ones(4), np.ones(4))).ravel().tolist()
    tex.image = img
    tex.interpolation = 'Closest'
    separate = setup.node(tree, 'ShaderNodeSeparateColor', 'Channels', -250, 0)
    separate.mode = 'RGB'
    tree.links.new(tex.outputs['Color'], separate.inputs['Color'])
    face = setup.node(tree, 'ShaderNodeGroup', 'Face Decoder', 0, 0)
    face.node_tree = bpy.data.node_groups[setup.SDF]
    face.inputs['Enable SDF'].default_value = 1
    face.inputs['Edge Softness'].default_value = 0
    for channel, name in (('Red', 'Left Threshold'), ('Green', 'Right Threshold')):
        tree.links.new(separate.outputs[channel], face.inputs[name])
    emission = setup.node(tree, 'ShaderNodeEmission', 'Diagnostic', 300, 0)
    tree.links.new(face.outputs['Shadow'], emission.inputs['Color'])
    out = setup.node(tree, 'ShaderNodeOutputMaterial', 'Output', 540, 0)
    tree.links.new(emission.outputs[0], out.inputs['Surface'])
    camera_at((0, -4, 0), (0, 0, 0), 2)
    scene.render.film_transparent = True
    scenarios = [
        ('front', (0, -1, 0), [1, 0, 0, 0]),
        ('left45', (1, -1, 0), [1, 1, 0, 0]),
        ('right45', (-1, -1, 0), [0, 0, 1, 1]),
        ('left90', (1, 0, 0), [1, 1, 1, 0]),
        ('right90', (-1, 0, 0), [0, 1, 1, 1]),
        ('rear', (0, 1, 0), [1, 1, 1, 1]),
    ]
    samples = {}
    for name, direction, expected in scenarios:
        aim_sun(direction)
        path = OUT / ('probe-' + name + '.png')
        render(path, 128, 64)
        image = bpy.data.images.load(str(path), check_existing=False)
        pixels = np.array(image.pixels[:], dtype=float).reshape(64, 128, 4)
        actual = pixels[32, [16, 48, 80, 112], 0]
        np.testing.assert_allclose(actual, expected, atol=0.005, err_msg=name)
        samples[name] = actual.tolist()
        bpy.data.images.remove(image)
    tree.links.new(face.outputs['Coverage'], emission.inputs['Color'])
    aim_sun((0, 0, 1))
    path = OUT / 'probe-vertical-coverage.png'
    render(path, 128, 64)
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = np.array(image.pixels[:], dtype=float).reshape(64, 128, 4)
    assert pixels[32, 64, 0] < 0.005
    bpy.data.images.remove(image)
    report['probe_samples'] = samples
    report['checks'].append('GPU-rendered left/front/right map selection, 0 and 1 sentinels at side endpoints, rear shadow, and vertical-light coverage fallback.')
    bpy.data.objects.remove(plane, do_unlink=True)
    for obj, hidden in visibility.items():
        obj.hide_render = hidden


def character_renders():
    scene = bpy.context.scene
    scene.world.color = (0.05, 0.05, 0.05)
    scene.render.film_transparent = True
    camera_at((0.0, -4, 1.43), (0, 0, 1.43), 0.40)
    aim_sun((0.65, -1, 0.4))
    render(OUT / 'toon-ready-for-maps.png', 700, 700)
    # Load the verified sample only in this disposable process, never the deliverable.
    setup.connect_export(ROOT / 'build' / 'validation' / 'v09' / 'face_sdf_2048.sdfproject.json')
    for label, direction in (('left', (3, -1, 0.25)), ('front', (0, -1, 0.25)),
                             ('right', (-3, -1, 0.25))):
        aim_sun(direction)
        render(OUT / ('sdf-example-' + label + '.png'), 700, 700)
    report['checks'].append('Rendered the delivered toon material with SDF disabled, then verified the matching packed export on a disposable copy at left/front/right lighting.')


def main():
    if Path(bpy.data.filepath).name == 'test_sdf.blend':
        raise RuntimeError('Run this test only on the separate toon file in a disposable process.')
    assert bpy.context.scene.render.engine == 'BLENDER_EEVEE'
    head = bpy.data.materials['head | Toon']
    assert head.node_tree.nodes['Face SDF Controls'].inputs['Enable SDF'].default_value == 0
    assert all(head.node_tree.nodes[name].image is None for name in ('LEFT SDF - Non-Color', 'RIGHT SDF - Non-Color'))
    originals = ['body', 'arms', 'legs', 'head', 'hair', 'eye', 'eye_brows', 'eye_lashes', 'teeth']
    for name in originals:
        assert bpy.data.materials[name].use_fake_user
        assert bpy.data.materials[name + ' | Toon']['Source Material'] == name
    update()
    driver_checks()
    shader_probe()
    character_renders()
    report['status'] = 'PASS'
    return report


if __name__ == '__main__':
    try:
        main()
    except Exception:
        report['status'] = 'FAIL'
        report['traceback'] = traceback.format_exc()
        traceback.print_exc()
    (OUT / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)
    if report['status'] != 'PASS':
        raise RuntimeError(report['traceback'])
