"""Import the actual ZIP under a Blender extension namespace in an isolated process."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import time
import zipfile
import bpy
from math import pi
from mathutils import Quaternion

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build'/'validation'/'v014'
DEST=OUT/'installed-v014'/'anime_sdf_gen'
DEST.mkdir(parents=True,exist_ok=True)
ZIP=ROOT/'dist'/'anime_sdf_gen-0.14.0.zip'
with zipfile.ZipFile(ZIP) as archive:
    assert all(not n.startswith(('/', '\\')) and '..' not in Path(n).parts for n in archive.namelist())
    archive.extractall(DEST)
for name in ('bl_ext','bl_ext.sdf_qa'):
    if name not in sys.modules:
        module=types.ModuleType(name);module.__path__=[];sys.modules[name]=module
name='bl_ext.sdf_qa.anime_sdf_gen'
spec=importlib.util.spec_from_file_location(name,DEST/'__init__.py',submodule_search_locations=[str(DEST)])
module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
assert importlib.import_module(name+'.curve_input').CurveInput
module.register()
before={k:len(getattr(bpy.data,k)) for k in ('objects','meshes','materials','images','scenes','worlds')}
session=sys.modules[name+'.session']
model=sys.modules[name+'.core.model']
drafts=OUT/'archive-drafts';drafts.mkdir(exist_ok=True)
session.draft_root=lambda:drafts
p=bpy.context.window_manager.anime_sdf_gen
obj=bpy.data.objects['body']
for o in bpy.context.view_layer.objects:o.select_set(o==obj)
bpy.context.view_layer.objects.active=obj
slots={i for i,m in enumerate(obj.data.materials) if m and m.name=='head'}
for polygon in obj.data.polygons:polygon.select=polygon.material_index in slots
bpy.context.tool_settings.mesh_select_mode=(False,False,True)
bpy.ops.object.mode_set(mode='EDIT')
p.source_method='SELECTED'
assert bpy.ops.anime_sdf_gen.create()=={'FINISHED'}
assert session.ACTIVE and type(session.ACTIVE).__module__.startswith('bl_ext.sdf_qa.')
assert session.ACTIVE.stage=='ORIENT'
assert module.bl_info['name']=='Anime SDF Gen' and module.bl_info['author']=='xht8723'
assert module.bl_info['version']==(0,14,0)
assert p.bl_rna.properties['keyframes'].name=='Shadow keyframes'
session.ACTIVE.set_front(Quaternion((1,0,0),pi/2))
assert session.ACTIVE.stage=='FIT' and len(session.ACTIVE.project['authoring']['anchors'])==3
session.ACTIVE.fit()
assert session.ACTIVE.stage=='EDIT' and session.ACTIVE.key_index==0
assert len({p['co'][0] for p in session.ACTIVE.curve['points']})==1
bpy.ops.anime_sdf_gen.keyframe(direction=model.LTR,index=6)
bpy.ops.anime_sdf_gen.action(action='TRIANGLE')
assert session.ACTIVE.curve['name']=='Triangle'
assert session.ACTIVE.selected=={(1,0),(1,1),(1,2)}
assert all(p['mode']=='AUTO' for p in session.ACTIVE.curve['points'])
p.layer_operation='REMOVE'
bpy.ops.anime_sdf_gen.transform(dx=-.14)
assert session.run(session.compile_steps(session.ACTIVE.project,64)).shape==(64,64,2)
active=session.ACTIVE;deadline=time.perf_counter()+45
while active.thresholds is None:
    active.tick()
    assert not active.error,active.error
    assert time.perf_counter()<deadline,'Packaged sweep interpolation timed out'
assert tuple(active.image.size)==(512,512) and active.image.colorspace_settings.name=='Non-Color'
assert active.thresholds.shape==(512,512,2)
assert active.rgba.shape==(512,512,4)
session.ACTIVE.confirm()
assert session.ACTIVE.stage=='CONFIRM' and session.ACTIVE.playing and session.ACTIVE.rotation==0
assert bpy.ops.anime_sdf_gen.packing(map_name='character_left',route='B')=={'FINISHED'}
assert bpy.ops.anime_sdf_gen.packing(map_name='character_right',route='SEPARATE')=={'FINISHED'}
assert session.ACTIVE.project['settings']['packing']==dict(character_left='B',character_right='SEPARATE',face_coverage='R')
assert session.ACTIVE.playing
session.end_session(True)
assert active.preview_job is None and not active.field_cache and not active.mask_cache
module.unregister()
assert {k:len(getattr(bpy.data,k)) for k in before}==before
report={'status':'PASS','module':name,'source':str(DEST),'zip_bytes':ZIP.stat().st_size}
(OUT/'archive_import.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
