"""Build the character's EEVEE toon / directional face-SDF materials via Blender MCP.

Run build_character() in the inspected scene, then connect_export(sidecar_path).
This script never saves over the source .blend or changes mesh geometry.
"""
from pathlib import Path
import hashlib
import json
import math

import bpy
from mathutils import Matrix, Vector

TOON = 'Anime Simple Toon'
SDF = 'Anime Face SDF'
RIG = 'Anime Sun and Face Direction'
FRAME = 'Anime Face Direction'


def node(tree, kind, name, x, y, width=180):
    n = tree.nodes.new(kind)
    n.name = n.label = name
    n.location = (x, y)
    n.width = width
    return n


def value(tree, output, socket):
    if isinstance(output, bpy.types.NodeSocket):
        tree.links.new(output, socket)
    else:
        socket.default_value = output


def math_node(tree, operation, name, a, b=0.0, x=0, y=0):
    n = node(tree, 'ShaderNodeMath', name, x, y)
    n.operation = operation
    value(tree, a, n.inputs[0])
    if len(n.inputs) > 1:
        value(tree, b, n.inputs[1])
    return n.outputs[0]


def vector_node(tree, operation, name, a, b, x, y):
    n = node(tree, 'ShaderNodeVectorMath', name, x, y)
    n.operation = operation
    value(tree, a, n.inputs[0])
    value(tree, b, n.inputs[1])
    return n.outputs['Value'] if operation == 'DOT_PRODUCT' else n.outputs['Vector']


def socket(tree, name, kind='NodeSocketFloat', direction='INPUT', default=None,
           low=None, high=None, description=''):
    s = tree.interface.new_socket(name=name, in_out=direction, socket_type=kind)
    if default is not None:
        s.default_value = default
    if low is not None:
        s.min_value = low
    if high is not None:
        s.max_value = high
    s.description = description
    return s


def group(name):
    if bpy.data.node_groups.get(name):
        raise ValueError(f'{name} already exists. Start from the saved source copy.')
    tree = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    tree.use_fake_user = True
    return tree


def rotation_column(tree, target, column, name, x, y):
    # WORLD_SPACE transform variables include parents and constraints. XYZ is an
    # explicit evaluation convention, independent of the object's rotation mode.
    expressions = {
        0: ('cos(z)*cos(y)', 'sin(z)*cos(y)', '-sin(y)'),
        2: ('cos(z)*sin(y)*cos(x)+sin(z)*sin(x)',
            'sin(z)*sin(y)*cos(x)-cos(z)*sin(x)', 'cos(y)*cos(x)'),
    }[column]
    n = node(tree, 'ShaderNodeCombineXYZ', name, x, y, 260)
    for i, expression in enumerate(expressions):
        driver = n.inputs[i].driver_add('default_value').driver
        driver.type = 'SCRIPTED'
        for axis in 'xyz':
            var = driver.variables.new()
            var.name = axis
            var.type = 'TRANSFORMS'
            t = var.targets[0]
            t.id = target
            t.transform_type = 'ROT_' + axis.upper()
            t.transform_space = 'WORLD_SPACE'
            t.rotation_mode = 'XYZ'
        driver.expression = expression
    return n.outputs[0]


def set_face_frame(frame, alignment):
    # X = character left; Y = head up; Z = head forward.
    rotation = Matrix((alignment['right'], alignment['up'], alignment['forward'])).transposed()
    frame.matrix_world = Matrix.Translation(Vector(alignment['center'])) @ rotation.to_4x4()
    bpy.context.view_layer.update()


def build_rig(sun, body, alignment):
    frame = bpy.data.objects.new(FRAME, None)
    body.users_collection[0].objects.link(frame)
    frame.empty_display_type = 'ARROWS'
    frame.empty_display_size = 0.08
    frame.parent = body
    frame.hide_render = True
    frame['Guide'] = 'Local +Z faces forward; +X points to character left; +Y is up. Follows body; reparent to the head bone if rigged.'
    set_face_frame(frame, alignment)
    tree = group(RIG)
    for name in ('To Sun', 'Character Left', 'Face Forward'):
        socket(tree, name, 'NodeSocketVector', 'OUTPUT')
    output = node(tree, 'NodeGroupOutput', 'World Directions', 340, 0)
    for name, target, col, y in (('To Sun', sun, 2, 260),
                                 ('Character Left', frame, 0, 0),
                                 ('Face Forward', frame, 2, -260)):
        direction = rotation_column(tree, target, col, name, -100, y)
        tree.links.new(direction, output.inputs[name])
    tree['Sun'] = sun.name
    tree['Head Reference'] = frame.name
    tree['Direction Convention'] = 'Sun local +Z points toward the light; local -Z is the ray travel direction.'
    return tree


def smooth_step(tree, v, center, softness, x, y, name, hard_zero=False):
    epsilon = math_node(tree, 'MAXIMUM', name + ' Minimum Width', softness, 0.00001, x, y-190)
    half = math_node(tree, 'MULTIPLY', name + ' Half Width', epsilon, 0.5, x+210, y-190)
    lo = math_node(tree, 'SUBTRACT', name + ' Start', center, half, x+420, y)
    hi = math_node(tree, 'ADD', name + ' End', center, half, x+420, y-190)
    ramp = node(tree, 'ShaderNodeMapRange', name, x+640, y)
    ramp.interpolation_type = 'SMOOTHSTEP'
    ramp.clamp = True
    for source, key in ((v, 'Value'), (lo, 'From Min'), (hi, 'From Max')):
        value(tree, source, ramp.inputs[key])
    if not hard_zero:
        return ramp.outputs['Result']
    below = math_node(tree, 'LESS_THAN', name + ' Below Threshold', v, center, x+640, y-420)
    hard = math_node(tree, 'SUBTRACT', name + ' Hard Comparison', 1, below, x+850, y-420)
    soft_on = math_node(tree, 'GREATER_THAN', name + ' Use Soft Edge', softness, 0, x+640, y-640)
    mix = node(tree, 'ShaderNodeMixRGB', name + ' Hard or Soft', x+1070, y-200)
    value(tree, soft_on, mix.inputs[0])
    value(tree, hard, mix.inputs[1])
    value(tree, ramp.outputs['Result'], mix.inputs[2])
    return mix.outputs[0]


def build_sdf(rig):
    tree = group(SDF)
    socket(tree, 'Left Threshold', default=0.5, low=0, high=1,
           description='Character-left light map; use the existing UVs without flipping U.')
    socket(tree, 'Right Threshold', default=0.5, low=0, high=1,
           description='Character-right light map; use the existing UVs without flipping U.')
    socket(tree, 'Coverage', default=1, low=0, high=1,
           description='Optional face coverage mask; 1 uses the front-facing head material region.')
    socket(tree, 'Enable SDF', default=0, low=0, high=1,
           description='Set to 1 after assigning both SDF images as Non-Color data.')
    socket(tree, 'Edge Softness', default=0.006, low=0, high=0.1,
           description='Transition width in front-to-side progress. 0 gives a hard toon edge.')
    for name in ('Shadow', 'Coverage', 'Use Left Map', 'Light Progress'):
        socket(tree, name, direction='OUTPUT')
    inp = node(tree, 'NodeGroupInput', 'SDF Maps', -1100, -300, 210)
    directions = node(tree, 'ShaderNodeGroup', 'Automatic Sun / Head Directions', -1550, 600, 250)
    directions.node_tree = rig
    side = vector_node(tree, 'DOT_PRODUCT', 'Sun on Character Left', directions.outputs['To Sun'],
                       directions.outputs['Character Left'], -1240, 740)
    front = vector_node(tree, 'DOT_PRODUCT', 'Sun in Front', directions.outputs['To Sun'],
                        directions.outputs['Face Forward'], -1240, 530)
    right_side = math_node(tree, 'LESS_THAN', 'Use Right Map', side, 0, -1000, 740)
    left_side = math_node(tree, 'SUBTRACT', 'Use Left Map', 1, right_side, -790, 850)
    abs_side = math_node(tree, 'ABSOLUTE', 'Horizontal Side Magnitude', side, x=-1000, y=510)
    yaw = math_node(tree, 'ARCTAN2', 'Absolute Head Yaw', abs_side, front, -790, 510)
    progress = math_node(tree, 'MULTIPLY', 'Yaw / 90 Degrees', yaw, 2 / math.pi, -580, 510)
    tree.nodes['Yaw / 90 Degrees'].use_clamp = True
    # Exact map selection avoids blending distinct authored thresholds at the front.
    left = math_node(tree, 'MULTIPLY', 'Selected Left', inp.outputs['Left Threshold'], left_side, -550, -250)
    right = math_node(tree, 'MULTIPLY', 'Selected Right', inp.outputs['Right Threshold'], right_side, -550, -450)
    threshold = math_node(tree, 'ADD', 'Selected SDF Threshold', left, right, -320, -250)
    soft_shadow = smooth_step(tree, progress, threshold, inp.outputs['Edge Softness'], -90, -100, 'SDF Edge', hard_zero=True)
    nonzero = math_node(tree, 'GREATER_THAN', 'Not Always Shadow', threshold, 0, 340, -680)
    always_shadow = math_node(tree, 'SUBTRACT', 'Zero Always Shadow', 1, nonzero, 550, -680)
    not_always_lit = math_node(tree, 'LESS_THAN', 'One Always Lit', threshold, 1, 550, -880)
    shadow = math_node(tree, 'MAXIMUM', 'Respect Zero Sentinel', soft_shadow, always_shadow, 800, -100)
    shadow = math_node(tree, 'MULTIPLY', 'Respect One Sentinel', shadow, not_always_lit, 1020, -100)
    # The authoring domain is frontal/horizontal: behind the head becomes shadow;
    # a vertical Sun falls back to normal toon shading instead of an arbitrary map.
    rear = math_node(tree, 'LESS_THAN', 'Rear Light', front, -0.00001, -790, 280)
    shadow = math_node(tree, 'MAXIMUM', 'Rear Light Shadows Face', shadow, rear, 1240, -100)
    side_sq = math_node(tree, 'MULTIPLY', 'Side Squared', side, side, -1000, 60)
    front_sq = math_node(tree, 'MULTIPLY', 'Front Squared', front, front, -1000, -130)
    horizontal = math_node(tree, 'ADD', 'Horizontal Length Squared', side_sq, front_sq, -790, 60)
    valid = math_node(tree, 'GREATER_THAN', 'Horizontal Direction Exists', horizontal, 0.00000001, -560, 60)
    coverage = math_node(tree, 'MULTIPLY', 'Valid Face Coverage', inp.outputs['Coverage'], valid, 1020, -390)
    geometry = node(tree, 'ShaderNodeNewGeometry', 'Head Geometry', 340, -1110)
    facing = vector_node(tree, 'DOT_PRODUCT', 'Head Front Surface', geometry.outputs['True Normal'],
                         directions.outputs['Face Forward'], 550, -1110)
    facing = math_node(tree, 'GREATER_THAN', 'Front Facing Head Only', facing, 0, 780, -1110)
    coverage = math_node(tree, 'MULTIPLY', 'Restrict To Head Front', coverage, facing, 1240, -390)
    coverage = math_node(tree, 'MULTIPLY', 'Enable Face SDF', coverage, inp.outputs['Enable SDF'], 1460, -390)
    out = node(tree, 'NodeGroupOutput', 'Face SDF Result', 1730, 100, 220)
    for output, name in ((shadow, 'Shadow'), (coverage, 'Coverage'),
                         (left_side, 'Use Left Map'), (progress, 'Light Progress')):
        tree.links.new(output, out.inputs[name])
    return tree


def build_toon():
    tree = group(TOON)
    socket(tree, 'Base Color', 'NodeSocketColor', default=(0.8, 0.8, 0.8, 1))
    socket(tree, 'Shadow Tint', 'NodeSocketColor', default=(0.52, 0.43, 0.50, 1))
    socket(tree, 'Light Threshold', default=0.18, low=0, high=2,
           description='EEVEE diffuse illumination cutoff between the two tones.')
    socket(tree, 'Edge Softness', default=0.015, low=0, high=0.5)
    socket(tree, 'Face Shadow', default=0, low=0, high=1)
    socket(tree, 'Face Coverage', default=0, low=0, high=1)
    socket(tree, 'Shader', 'NodeSocketShader', 'OUTPUT')
    inp = node(tree, 'NodeGroupInput', 'Toon Controls', -1160, -220, 220)
    diffuse = node(tree, 'ShaderNodeBsdfDiffuse', 'White Diffuse Lighting', -1160, 300)
    diffuse.inputs['Color'].default_value = (1, 1, 1, 1)
    rgb = node(tree, 'ShaderNodeShaderToRGB', 'EEVEE Light and Cast Shadows', -930, 300, 230)
    tree.links.new(diffuse.outputs[0], rgb.inputs[0])
    bw = node(tree, 'ShaderNodeRGBToBW', 'Light Level', -650, 300)
    tree.links.new(rgb.outputs['Color'], bw.inputs[0])
    lit = smooth_step(tree, bw.outputs[0], inp.outputs['Light Threshold'],
                      inp.outputs['Edge Softness'], -880, 0, 'Toon Edge')
    shadow = math_node(tree, 'SUBTRACT', 'Regular Toon Shadow', 1, lit, 0, 250)
    remaining = math_node(tree, 'SUBTRACT', 'Outside Face Coverage', 1, inp.outputs['Face Coverage'], 0, -30)
    regular = math_node(tree, 'MULTIPLY', 'Body and Uncovered Head', shadow, remaining, 230, 240)
    facial = math_node(tree, 'MULTIPLY', 'Authored Face Shadow', inp.outputs['Face Shadow'], inp.outputs['Face Coverage'], 230, -40)
    combined = math_node(tree, 'ADD', 'Final Two Tone Mask', regular, facial, 460, 240)
    tint = node(tree, 'ShaderNodeMixRGB', 'Lit White / Shadow Tint', 690, 240)
    tint.blend_type = 'MIX'
    value(tree, combined, tint.inputs[0])
    tint.inputs[1].default_value = (1, 1, 1, 1)
    value(tree, inp.outputs['Shadow Tint'], tint.inputs[2])
    color = node(tree, 'ShaderNodeMixRGB', 'Preserve Base Color', 930, 240)
    color.blend_type = 'MULTIPLY'
    color.inputs[0].default_value = 1
    value(tree, inp.outputs['Base Color'], color.inputs[1])
    value(tree, tint.outputs[0], color.inputs[2])
    emission = node(tree, 'ShaderNodeEmission', 'Flat Toon Surface', 1170, 240)
    value(tree, color.outputs[0], emission.inputs['Color'])
    out = node(tree, 'NodeGroupOutput', 'Toon Surface', 1400, 240)
    tree.links.new(emission.outputs[0], out.inputs['Shader'])
    return tree


def build_character():
    sun, body = bpy.data.objects.get('Sun'), bpy.data.objects.get('body')
    if not sun or sun.type != 'LIGHT' or sun.data.type != 'SUN' or not body or body.type != 'MESH':
        raise ValueError('Expected the inspected body mesh and Sun light.')
    if any(bpy.data.node_groups.get(name) for name in (TOON, SDF, RIG)):
        raise ValueError('The toon setup already exists; do not rebuild over authored changes.')
    alignment = {'right': [1, 0, 0], 'up': [0, 0, 1], 'forward': [0, -1, 0],
                 'center': [0, 0.014457762241363525, 1.4504539966583252]}
    rig = build_rig(sun, body, alignment)
    sdf = build_sdf(rig)
    toon = build_toon()
    replacements = {}
    for obj in list(bpy.context.scene.objects):
        if obj.type != 'MESH':
            continue
        for slot in obj.material_slots:
            original = slot.material
            if original is None:
                continue
            if original.name not in replacements:
                original.use_fake_user = True
                material = original.copy()
                material.name = original.name + ' | Toon'
                material.use_fake_user = False
                material['Source Material'] = original.name
                tree = material.node_tree
                principled = next(n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED')
                base_socket = principled.inputs['Base Color']
                base_value = tuple(base_socket.default_value)
                base_source = base_socket.links[0].from_socket if base_socket.is_linked else None
                out = next(n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL')
                keep = {out}
                if base_source:
                    keep.add(base_source.node)
                for n in list(tree.nodes):
                    if n not in keep:
                        tree.nodes.remove(n)
                surface = node(tree, 'ShaderNodeGroup', 'Simple Toon Controls', 420, 300, 260)
                surface.node_tree = toon
                value(tree, base_source if base_source else base_value, surface.inputs['Base Color'])
                if base_source:
                    base_source.node.location = (-700, 400)
                    base_source.node.label = 'Original Base Color'
                    base_source.node.width = 260
                out.location = (770, 300)
                tree.links.new(surface.outputs['Shader'], out.inputs['Surface'])
                if original.name == 'head':
                    surface.inputs['Shadow Tint'].default_value = (0.62, 0.46, 0.48, 1)
                    face = node(tree, 'ShaderNodeGroup', 'Face SDF Controls', 70, -80, 260)
                    face.node_tree = sdf
                    tree.links.new(face.outputs['Shadow'], surface.inputs['Face Shadow'])
                    tree.links.new(face.outputs['Coverage'], surface.inputs['Face Coverage'])
                    uv = node(tree, 'ShaderNodeUVMap', 'Face UV', -1000, -80, 190)
                    uv.uv_map = 'UVMap'
                    uv['SDF Placeholder'] = True
                    for label, input_name, y in (('LEFT SDF - Non-Color', 'Left Threshold', -80),
                                                 ('RIGHT SDF - Non-Color', 'Right Threshold', -390)):
                        tex = node(tree, 'ShaderNodeTexImage', label, -710, y, 260)
                        tex.interpolation = 'Linear'
                        tex.extension = 'EXTEND'
                        tex['SDF Placeholder'] = True
                        tree.links.new(uv.outputs['UV'], tex.inputs['Vector'])
                        tree.links.new(tex.outputs['Color'], face.inputs[input_name])
                    material['SDF Status'] = 'Ready: assign left/right Non-Color maps, then set Enable SDF to 1. Optional coverage mask connects to Coverage.'
                for n in tree.nodes:
                    n.select = False
                surface.select = True
                tree.nodes.active = surface
                replacements[original.name] = material
            slot.material = replacements[original.name]
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene['Toon Shader'] = 'EEVEE two-tone diffuse. Rotate Sun to drive face SDF map choice and yaw. See Character Toon - Read Me.'
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.type = 'MATERIAL'
                area.spaces.active.shading.use_scene_lights = True
                area.spaces.active.shading.use_scene_world = True
                area.tag_redraw()
    bpy.context.view_layer.update()
    return {'materials': {k: v.name for k, v in replacements.items()},
            'groups': [TOON, SDF, RIG], 'sun': sun.name, 'frame': FRAME}


def connect_export(sidecar_path):
    """Read the current export schema and connect logical maps without changing files."""
    path = Path(sidecar_path).resolve()
    project = json.loads(path.read_text(encoding='utf-8'))
    if project.get('format') != 'anime_sdf_gen' or project.get('format_version') != 2:
        raise ValueError('Expected a current Anime SDF Gen project export (format version 2).')
    entries = project.get('textures', [])
    routes = {}
    for entry in entries:
        image_path = (path.parent / entry['file']).resolve()
        if not image_path.is_file():
            raise ValueError(f'Missing SDF image: {image_path}')
        if hashlib.sha256(image_path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f'SDF image does not match its export metadata: {image_path}')
        for channel, logical in entry['channels'].items():
            if channel not in {'R', 'G', 'B', 'Y'} or logical in routes:
                raise ValueError('Invalid or duplicate SDF map channel assignment.')
            routes[logical] = (image_path, channel)
    expected = {'character_left', 'character_right', 'face_coverage'}
    if set(routes) != expected:
        raise ValueError('The sidecar must describe left, right, and coverage maps.')
    ref = project['source']
    body = bpy.data.objects.get(ref['object'])
    if body is None or body.type != 'MESH' or ref['uv_map'] not in body.data.uv_layers:
        raise ValueError('The source object or exported UV map is missing.')
    # Use the project's read-only fingerprint check, with no registration or UI.
    from anime_sdf_gen import source
    source.from_reference(ref, project['alignment'])
    material = bpy.data.materials['head | Toon']
    if material.get('SDF Project'):
        raise ValueError('Maps are already connected. Edit the labeled image nodes to change maps.')
    tree = material.node_tree
    face = tree.nodes['Face SDF Controls']
    for n in list(tree.nodes):
        if n.get('SDF Placeholder'):
            tree.nodes.remove(n)
    uv = node(tree, 'ShaderNodeUVMap', 'Exported Face UV', -1380, -40, 200)
    uv.uv_map = ref['uv_map']
    images = {}
    channels = {}
    for index, image_path in enumerate(dict.fromkeys(p for p, c in routes.values())):
        image = bpy.data.images.load(str(image_path), check_existing=False)
        image.colorspace_settings.name = 'Non-Color'
        image.pack()
        image.use_fake_user = True
        tex = node(tree, 'ShaderNodeTexImage', 'SDF Map - ' + image_path.stem,
                   -1090, -60-index*370, 260)
        tex.image = image
        tex.interpolation = 'Linear'
        tex.extension = 'EXTEND'
        tree.links.new(uv.outputs['UV'], tex.inputs['Vector'])
        separate = node(tree, 'ShaderNodeSeparateColor', 'SDF Channels - ' + image_path.stem,
                        -760, -60-index*370, 230)
        separate.mode = 'RGB'
        tree.links.new(tex.outputs['Color'], separate.inputs['Color'])
        images[image_path] = image
        channels[image_path] = separate
    channel_names = {'R': 'Red', 'Y': 'Red', 'G': 'Green', 'B': 'Blue'}
    for logical, label in (('character_left', 'Left Threshold'),
                           ('character_right', 'Right Threshold'), ('face_coverage', 'Coverage')):
        image_path, channel = routes[logical]
        tree.links.new(channels[image_path].outputs[channel_names[channel]], face.inputs[label])
    set_face_frame(bpy.data.objects[FRAME], project['alignment'])
    face.inputs['Enable SDF'].default_value = 1
    material['SDF Status'] = 'Connected: automatic Sun direction, left/right thresholds, face coverage.'
    material['SDF Project'] = str(path)
    material['SDF Routes'] = json.dumps({k: {'file': str(p), 'channel': c} for k, (p, c) in routes.items()})
    bpy.context.view_layer.update()
    return {'project': str(path), 'uv_map': ref['uv_map'],
            'routes': json.loads(material['SDF Routes']), 'packed': True}
