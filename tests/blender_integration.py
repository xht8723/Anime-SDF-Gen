"""Run in a fresh background Blender with the untouched fixture already loaded."""
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback
from unittest.mock import patch
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import anime_sdf_gen
from anime_sdf_gen import source,session
from tests.fixture import fixture_face
from anime_sdf_gen.core import model,files

OUT=ROOT/'build'/'validation'/'v014'
OUT.mkdir(parents=True,exist_ok=True)
DRAFTS=OUT/'drafts'
DRAFTS.mkdir(exist_ok=True)
session.draft_root=lambda:DRAFTS


def original_digest():
    obj=bpy.data.objects['body'];mesh=obj.data
    mode=obj.mode
    if mode=='EDIT':bpy.ops.object.mode_set(mode='OBJECT')
    h=hashlib.sha256()
    co=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',co);h.update(co.tobytes())
    loops=np.empty(len(mesh.loops),dtype=np.int32);mesh.loops.foreach_get('vertex_index',loops);h.update(loops.tobytes())
    for uv in mesh.uv_layers:
        vals=np.empty(len(mesh.loops)*2,dtype=np.float32);uv.data.foreach_get('uv',vals);h.update(vals.tobytes())
    data={'digest':h.hexdigest(),'materials':[m.name for m in mesh.materials],
          'scene':bpy.context.scene.name,'view_layer':bpy.context.view_layer.name,
          'selected':[o.name for o in bpy.context.view_layer.objects if o.select_get()],
          'active':bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else None,
          'mode':mode,'engine':bpy.context.scene.render.engine,
          'matrix':[list(row) for row in obj.matrix_world],
          'counts':{k:len(getattr(bpy.data,k)) for k in ('objects','meshes','materials','images','scenes','worlds','collections','node_groups')}}
    if mode=='EDIT':bpy.ops.object.mode_set(mode='EDIT')
    return data


def assert_clean(before):
    after=original_digest()
    assert before==after,(before,after)
    assert not any(session.OWNER_KEY in x for k in ('objects','meshes','materials','images','scenes','worlds') for x in getattr(bpy.data,k))


def create():
    props=bpy.context.window_manager.anime_sdf_gen
    props.uv_map='UVMap'
    props.resolution='512';props.output=str(OUT/'face_sdf');props.front_only=True
    # The engine/lifecycle suite starts from fitted artwork. UI source capture
    # and the new fitting workflow have separate integration and GUI tests.
    face=fixture_face(source)
    project=model.new_project(face.reference,face.alignment,resolution=512,output=str(OUT/'face_sdf'))
    return session.start(bpy.context,project,face)


def run_all():
    started=time.perf_counter()
    result={'blender':bpy.app.version_string,'tests':[]}
    anime_sdf_gen.register()
    before=original_digest()
    result['original_counts']={k:len(getattr(bpy.data,k)) for k in ('objects','meshes','materials','images','scenes','worlds','collections','node_groups','screens','workspaces')}
    fixture_hash=hashlib.sha256((ROOT/'test_sdf.blend').read_bytes()).hexdigest()
    try:
        fixture_face(source,front_only=False)
        raise AssertionError('Full-head UV overlaps were not rejected')
    except ValueError as exc:
        assert 'Overlapping' in str(exc)
        result['tests'].append('full-head UV overlap rejected')
    for _ in range(3):
        s=create()
        assert s.scene!=bpy.data.scenes['Scene']
        assert s.preview_object.data!=bpy.data.objects['body'].data
        assert s.image.colorspace_settings.name=='Non-Color'
        session.end_session(True)
        assert_clean(before)
    result['tests'].append('three independent preview/cancel cycles restore all original data and counts')
    orphan=bpy.data.images.new('Unrelated orphan',width=2,height=2)
    with_orphan=original_digest()
    create();session.end_session(True);assert_clean(with_orphan)
    assert orphan.users==0
    bpy.data.images.remove(orphan)
    result['tests'].append('unrelated orphan image preserved')
    obj=bpy.data.objects['body'];obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.object.mode_set(mode='EDIT')
    edit_before=original_digest()
    create();session.end_session(True);assert_clean(edit_before)
    bpy.ops.object.mode_set(mode='OBJECT');obj.select_set(False)
    bpy.context.view_layer.objects.active=bpy.data.objects.get(before['active'])
    assert_clean(before)
    result['tests'].append('edit mode and selection restored')
    with patch.object(session.Session,'write_draft',side_effect=OSError('injected unavailable recovery directory')):
        create();session.save_pre(None)
        assert session.ACTIVE is None and session.SUSPENDED
        assert_clean(before)
        session.resume();assert session.ACTIVE is not None
        session.end_session(True)
    assert_clean(before)
    result['tests'].append('recovery IO failure does not prevent cleanup, save suspension, or resume')
    s=create()
    bpy.ops.anime_sdf_gen.keyframe(direction=model.LTR,index=2)
    original=model.dumps(s.project)
    bpy.ops.anime_sdf_gen.action(action='TRIANGLE')
    assert s.curve['closed']
    bpy.ops.anime_sdf_gen.transform(dx=.02,dy=.01,angle=12,scale=1.1)
    bpy.ops.anime_sdf_gen.action(action='INSERT_POINT')
    assert len(s.curve['points'])==4
    bpy.ops.anime_sdf_gen.action(action='UNDO')
    assert len(s.curve['points'])==3
    bpy.ops.anime_sdf_gen.action(action='REDO')
    assert len(s.curve['points'])==4
    s.project=model.loads(original);s.changed()
    bpy.ops.anime_sdf_gen.action(action='ADD_KEYFRAME')
    assert len(model.sweep(s.project,model.LTR))==10
    bpy.ops.anime_sdf_gen.action(action='UNDO')
    assert len(model.sweep(s.project,model.LTR))==9
    with bpy.context.temp_override(scene=s.state.scene,view_layer=s.state.view_layer):
        obj=bpy.data.objects['body'];old=obj.location.copy()
        try:
            obj.location.x+=.01;bpy.context.view_layer.update()
            try:
                source.from_reference(s.project['source'],s.project['alignment'],validate=False)
                raise AssertionError('Source mismatch was not rejected')
            except ValueError as exc:assert 'changed' in str(exc)
        finally:obj.location=old;bpy.context.view_layer.update()
    result['tests'].append('changed source transform detected before regeneration')
    result['tests'].append('keyframe, patch, transform, point editing, undo, redo operators')
    s.confirm()
    assert s.stage=='CONFIRM' and s.rotation==0 and s.playing
    # Fault before export must leave the session editable.
    s.project['settings']['output']=str(OUT/'invalid'/'face')
    blocker=OUT/'invalid';blocker.write_text('not a directory')
    s.start_export()
    while s.busy:s.advance_export(.05,finish=False)
    assert s.error and session.ACTIVE is s and not s.closed
    blocker.unlink()
    result['tests'].append('export error retains authoring')
    s.project['settings']['output']=str(OUT/'face_sdf')
    s.start_export();s.advance_export(.001,finish=False);s.cancel_export()
    assert not s.busy and session.ACTIVE is s
    result['tests'].append('generation cancellation retains authoring')
    session.end_session(True)
    draft_session=create()
    explicit=DRAFTS/(draft_session.project['id']+'.sdfproject.json')
    assert bpy.ops.anime_sdf_gen.save_draft(filepath=str(explicit))=={'FINISHED'}
    assert session.ACTIVE is None and explicit.exists()
    assert model.loads(explicit.read_text())['id']==draft_session.project['id']
    explicit.unlink()
    assert_clean(before)
    result['tests'].append('explicit Save Draft survives close even at the automatic-draft path')
    s=create()
    s.confirm();st=time.perf_counter();s.start_export()
    while s.busy:s.advance_export(.05)
    assert s.output_paths,s.error
    result['export_512_seconds']=time.perf_counter()-st
    assert session.ACTIVE is None
    assert_clean(before)
    result['tests'].append('RGB16 PNG + sidecar export and automatic cleanup')
    tex,side=s.output_paths
    png=files.read_png16(tex)
    assert png.dtype==np.uint16 and png.shape==(512,512,3)
    assert np.unique(png[...,0]).size>256
    img=bpy.data.images.load(tex,check_existing=False)
    try:
        img.colorspace_settings.name='Non-Color'
        pixels=np.empty(512*512*4,dtype=np.float32);img.pixels.foreach_get(pixels)
        np.testing.assert_allclose(pixels.reshape(512,512,4)[...,:3],png.astype(float)/65535,atol=1e-6)
    finally:bpy.data.images.remove(img)
    result['tests'].append('Blender reload preserves 16-bit channel values without color conversion')
    assert bpy.ops.anime_sdf_gen.open_project(filepath=side)=={'FINISHED'}
    s=session.ACTIVE
    assert s.project['source']['fingerprint']==files.load_project(side)['source']['fingerprint']
    # Save must not serialize a preview scene or its ID dependencies.
    test_blend=OUT/'save_while_editing.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(test_blend),check_existing=False)
    assert session.ACTIVE is None and session.SUSPENDED
    assert not any(session.OWNER_KEY in sc for sc in bpy.data.scenes)
    session.resume()
    assert session.ACTIVE is not None
    result['tests'].append('save suspends preview and resumes editable project')
    session.save_pre(None)
    session.save_post(None)
    session.resume()
    assert session.ACTIVE is not None
    result['tests'].append('failed-save resume pathway')
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'test_sdf.blend'),load_ui=False,use_scripts=False)
    assert session.ACTIVE is None
    assert_clean(before)
    result['tests'].append('file load disposes previous preview and preserves recovery')
    create()
    anime_sdf_gen.unregister()
    assert session.ACTIVE is None
    assert_clean(before)
    assert session.save_pre not in bpy.app.handlers.save_pre
    assert not bpy.app.timers.is_registered(session.resume)
    result['tests'].append('disable restores original state and unregisters callbacks')
    assert fixture_hash==hashlib.sha256((ROOT/'test_sdf.blend').read_bytes()).hexdigest()
    result['fixture_sha256']=fixture_hash
    result['seconds']=time.perf_counter()-started
    result['status']='PASS'
    return result


try:
    report=run_all()
except Exception:
    report={'status':'FAIL','traceback':traceback.format_exc()}
    traceback.print_exc()
finally:
    (OUT/'blender_integration.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
if report['status']!='PASS':
    sys.exit(1)
