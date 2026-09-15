"""Versioned, JSON-only authoring state. Coordinates are in the fitted face plane."""
from copy import deepcopy
import json
import math
import uuid

FORMAT_VERSION = 3
FORMAT_ID = "anime_sdf_gen"
PAD = 0.25
SPAN = 1.0 + 2.0 * PAD
DEFAULT_LANDMARKS = {"nose": [.5, .28], "mouth": [.5, .15], "chin": [.5, .055]}
LTR, RTL = 'left_to_right', 'right_to_left'
SWEEP_LABELS = {LTR: 'Left → Right', RTL: 'Right → Left'}
MIN_KEYFRAMES, MAX_KEYFRAMES = 2, 33
MAP_LABELS = {"character_left": "Left shadow", "character_right": "Right shadow", "face_coverage": "Face coverage"}
OUTPUT_ROUTES = ('R', 'G', 'B', 'SEPARATE')
DEFAULT_PACKING = dict(zip(MAP_LABELS, OUTPUT_ROUTES))
ENCODING = {
    "format": "16-bit PNG", "colorspace": "Non-Color", "unused_rgb": 0,
    "progress": "absolute signed horizontal yaw / 180 degrees",
    "rotation": "0 Front; 90 character left; 180 Back; 270 character right; 360 Front",
    "maps": {"character_left": LTR, "character_right": RTL},
    "always_shadow": 0, "always_lit": 65535,
    "decode": "T == 0 or (T < 1 and progress >= T)",
    "projection_u": "viewer right = up cross forward = character left",
}


def uid():
    return uuid.uuid4().hex


def point(x, y, mode="AUTO", left=None, right=None):
    return {"co": [float(x), float(y)], "mode": mode,
            "left": list([-0.04, 0] if left is None else left),
            "right": list([0.04, 0] if right is None else right)}


def triangle():
    """A generic three-point closed curve, ready to move and reshape."""
    cx,cy=.5,.30;rx,ry=.085,.055
    return {'id':uid(),'name':'Triangle','closed':True,'operation':'ADD','enabled':True,
            'points':[point(cx-rx,cy+ry),point(cx+rx,cy+ry),point(cx,cy-ry)]}


def keyframe(progress, landmarks, accent=False):
    # A complete boundary sweep crosses both face edges. Endpoints remain
    # outside the face even when Nose Accent reshapes intermediate frames.
    levels = [1.23, .86, .62, .35, .20, .07, -.23]
    nose = landmarks["nose"][1]
    mouth = landmarks["mouth"][1]
    levels[3], levels[4], levels[5] = nose, mouth, landmarks['chin'][1]
    xs = [-.20 + progress * 1.40] * len(levels)
    if accent:
        offsets = [.02, .02, .04, .11, -.015, .025, .03]
        weight = 4*progress*(1-progress)
        xs = [x+weight*d for x, d in zip(xs, offsets)]
        for i, name in ((3, 'nose'), (4, 'mouth'), (5, 'chin')):
            xs[i] += (landmarks[name][0]-.5)*weight
    main = {"id": uid(), "name": "Main boundary", "closed": False,
            "operation": "ADD", "enabled": True,
            "points": [point(x, y) for x, y in zip(xs, levels)]}
    return {"id": uid(), "progress": float(progress), "contours": [main]}


def new_project(source, alignment, keyframes=9, mirror_sweeps=True, preset="CLEAN",
                resolution=2048, output=""):
    count = max(MIN_KEYFRAMES, min(MAX_KEYFRAMES, int(keyframes)))
    landmarks = deepcopy(DEFAULT_LANDMARKS)
    primary = [keyframe(i/(count-1), landmarks, preset == 'NOSE') for i in range(count)]
    return {"format": FORMAT_ID, "format_version": FORMAT_VERSION, "id": uid(), "source": deepcopy(source),
            "alignment": deepcopy(alignment), "landmarks": landmarks,
            "mirror_sweeps": bool(mirror_sweeps), "preset": preset,
            "sweeps": {LTR: primary, RTL: [mirror_keyframe(k) for k in primary]},
            "settings": {"resolution": int(resolution), "preview_size": 512,
                         "padding": 8, "output": str(output), "packing": deepcopy(DEFAULT_PACKING)},
            "authoring": {"stage": "EDIT", "anchors": {}, "reference": "NEUTRAL", "keyframe_count": count,
                          "front_only": True, "uv_map": source.get('uv_map','')},
            "encoding": deepcopy(ENCODING)}


def sweep(project, direction):
    return project['sweeps'][direction]


def get_keyframe(project, direction, index):
    return sweep(project, direction)[index]


def mirror_contour(contour):
    c = deepcopy(contour)
    for p in c['points']:
        p['co'][0] = 1-p['co'][0]
        p['left'][0] *= -1
        p['right'][0] *= -1
    return c


def mirror_keyframe(frame):
    result = deepcopy(frame)
    result['contours'] = [mirror_contour(c) for c in frame['contours']]
    return result


def synchronize_mirror(project, edited=LTR):
    if project['mirror_sweeps']:
        opposite = RTL if edited == LTR else LTR
        project['sweeps'][opposite] = [mirror_keyframe(k) for k in sweep(project, edited)]


def refit(project, count=None):
    """Fit complete boundaries; retain local shapes at the nearest keyframe."""
    for direction in SWEEP_LABELS:
        old = sweep(project, direction)
        n = len(old) if count is None else max(MIN_KEYFRAMES, min(MAX_KEYFRAMES, int(count)))
        frames = []
        for i in range(n):
            progress = i/(n-1)
            frame = keyframe(progress, project['landmarks'], project['preset']=='NOSE')
            if direction == RTL: frame = mirror_keyframe(frame)
            frame['contours'].extend(deepcopy(min(old,key=lambda k:abs(k['progress']-progress))['contours'][1:]))
            frames.append(frame)
        project['sweeps'][direction] = frames
    synchronize_mirror(project)
    if count is not None: project['authoring']['keyframe_count'] = len(sweep(project,LTR))
    project['authoring']['stage'] = 'EDIT'


def copy_previous(project, direction, index):
    if index <= 0: raise ValueError('The first keyframe has no previous keyframe.')
    frames = sweep(project, direction)
    frames[index]['contours'] = deepcopy(frames[index-1]['contours'])
    for c in frames[index]['contours']: c['id'] = uid()
    synchronize_mirror(project, direction)


def insert_keyframe(project, direction, index):
    frames = sweep(project, direction)
    if len(frames) >= MAX_KEYFRAMES: raise ValueError('The maximum is 33 keyframes per sweep.')
    index = max(0, min(index, len(frames)-2))
    new = deepcopy(frames[index])
    new['id'], new['progress'] = uid(), (frames[index]['progress']+frames[index+1]['progress'])/2
    frames.insert(index+1, new)
    synchronize_mirror(project, direction)
    return index+1


def remove_keyframe(project, direction, index):
    frames = sweep(project, direction)
    if index <= 0 or index >= len(frames)-1: raise ValueError('Keep the first and last keyframes of each sweep.')
    del frames[index]
    synchronize_mirror(project, direction)
    return index-1


def rotation_sample(degrees):
    """Clockwise horizontal orbit, independent of light movement history."""
    angle = float(degrees) % 360
    return (LTR, angle/180) if angle <= 180 else (RTL, (360-angle)/180)


def keyframe_rotation(direction, progress):
    return 180*progress if direction == LTR else 360-180*progress


def advance_rotation(degrees, delta):
    return (float(degrees)+max(0., float(delta))) % 360


def transform_contour(c, dx=0, dy=0, angle=0, scale=1):
    if not c["closed"]:
        raise ValueError("Shape transforms apply to closed shapes.")
    cx = sum(p["co"][0] for p in c["points"]) / len(c["points"])
    cy = sum(p["co"][1] for p in c["points"]) / len(c["points"])
    a = math.radians(angle)
    def vector(x, y):
        return [scale*(x*math.cos(a)-y*math.sin(a)), scale*(x*math.sin(a)+y*math.cos(a))]
    for p in c["points"]:
        x, y = vector(p["co"][0]-cx, p["co"][1]-cy)
        p["co"] = [cx+x+dx, cy+y+dy]
        p["left"] = vector(*p["left"])
        p["right"] = vector(*p["right"])


def validate_packing(packing):
    if not isinstance(packing, dict) or set(packing) != set(MAP_LABELS):
        raise ValueError('Choose an output channel or Separate for each texture map.')
    if any(route not in OUTPUT_ROUTES for route in packing.values()):
        raise ValueError('Texture maps must use R, G, B, or Separate.')
    channels = [route for route in packing.values() if route != 'SEPARATE']
    if len(channels) != len(set(channels)):
        raise ValueError('Each packed RGB channel can contain only one texture map.')
    return packing


def set_packing(project, name, route):
    """Move a map, swapping assignments when its destination is occupied."""
    if name not in MAP_LABELS or route not in OUTPUT_ROUTES:
        raise ValueError('Unknown texture map or output channel.')
    packing = dict(validate_packing(project['settings']['packing']))
    previous = packing[name]
    if route != 'SEPARATE':
        for other in packing:
            if other != name and packing[other] == route:
                packing[other] = previous
    packing[name] = route
    project['settings']['packing'] = validate_packing(packing)


def validate_project(p):
    if not isinstance(p, dict) or (p.get("format") != FORMAT_ID or p.get("format_version") != FORMAT_VERSION):
        raise ValueError("Unsupported project format. Create a new Anime SDF Gen project with this release.")
    for key in ('source','alignment','landmarks','sweeps','settings','mirror_sweeps'):
        if key not in p: raise ValueError(f'Project is missing {key}.')
    if not isinstance(p['mirror_sweeps'], bool) or set(p['sweeps']) != set(SWEEP_LABELS):
        raise ValueError('The project requires two complete boundary sweeps.')
    if p['settings']['resolution'] not in (512,1024,2048,4096):
        raise ValueError('Unsupported texture resolution.')
    validate_packing(p['settings'].get('packing'))
    if p.get('encoding') != ENCODING: raise ValueError('Unsupported texture encoding convention.')
    for direction in SWEEP_LABELS:
        frames = sweep(p, direction)
        if not MIN_KEYFRAMES <= len(frames) <= MAX_KEYFRAMES:
            raise ValueError('Each sweep requires 2–33 keyframes.')
        ts = [k['progress'] for k in frames]
        if any(not isinstance(t,(float,int)) or not math.isfinite(t) for t in ts) or ts[0]!=0 or ts[-1]!=1 or any(a>=b for a,b in zip(ts,ts[1:])):
            raise ValueError('Keyframe positions must increase from 0 to 1 within each sweep.')
        for frame in frames:
            cs = frame['contours']
            if not cs or cs[0]['closed'] or any(not c['closed'] for c in cs[1:]):
                raise ValueError('Each keyframe needs one main boundary followed by closed shapes.')
            if len(cs)>128: raise ValueError('Too many shapes in a keyframe.')
            for c in cs:
                if c['operation'] not in ('ADD','REMOVE') or not (3 if c['closed'] else 2)<=len(c['points'])<=256:
                    raise ValueError('Invalid contour operation or point count.')
                for pt in c['points']:
                    if pt['mode'] not in ('AUTO','CORNER','FREE'): raise ValueError('Invalid handle mode.')
                    for k in ('co','left','right'):
                        if len(pt[k])!=2 or any(not isinstance(v,(float,int)) or not math.isfinite(v) or abs(v)>100 for v in pt[k]):
                            raise ValueError('Invalid point or handle coordinates.')
    if p['mirror_sweeps'] and [k['progress'] for k in sweep(p,LTR)] != [k['progress'] for k in sweep(p,RTL)]:
        raise ValueError('Mirrored sweeps must have matching keyframe positions.')
    authoring = p.get('authoring', {})
    if authoring.get('stage') not in ('ORIENT', 'FIT', 'EDIT', 'CONFIRM'):
        raise ValueError('Invalid authoring stage.')
    if authoring.get('reference') not in ('NEUTRAL', 'MATERIAL'):
        raise ValueError('Invalid reference appearance.')
    if not isinstance(authoring.get('front_only'),bool) or not isinstance(authoring.get('uv_map'),str):
        raise ValueError('Missing or invalid authoring source settings.')
    if not isinstance(authoring.get('keyframe_count'),int) or not MIN_KEYFRAMES <= authoring['keyframe_count'] <= 33:
        raise ValueError('Invalid shadow keyframe count.')
    for name, anchor in authoring.get('anchors', {}).items():
        if name not in ('nose', 'mouth', 'chin') or not isinstance(anchor, dict):
            raise ValueError('Invalid landmark anchor.')
        if len(anchor.get('world', [])) != 3 or any(not math.isfinite(v) for v in anchor['world']):
            raise ValueError('Invalid landmark position.')
        if len(anchor.get('barycentric', [])) != 3 or any(not math.isfinite(v) or v < -1e-6 or v > 1+1e-6 for v in anchor['barycentric']):
            raise ValueError('Invalid landmark barycentric coordinates.')
        if abs(sum(anchor['barycentric'])-1) > 1e-5 or len(anchor.get('vertices', [])) != 3:
            raise ValueError('Invalid landmark surface reference.')
    return p


def dumps(project):
    validate_project(project)
    return json.dumps(project, indent=2, ensure_ascii=False, allow_nan=False)


def loads(text):
    if len(text) > 16_000_000:
        raise ValueError("Project file exceeds the 16 MB limit.")
    return validate_project(json.loads(text))


class History:
    def __init__(self, limit=100):
        self.undo_stack, self.redo_stack = [], []
        self.limit = limit

    def push(self, state):
        self.undo_stack.append(deepcopy(state))
        self.undo_stack = self.undo_stack[-self.limit:]
        self.redo_stack.clear()

    def undo(self, state):
        if not self.undo_stack:
            return state
        self.redo_stack.append(deepcopy(state))
        return self.undo_stack.pop()

    def redo(self, state):
        if not self.redo_stack:
            return state
        self.undo_stack.append(deepcopy(state))
        return self.redo_stack.pop()
