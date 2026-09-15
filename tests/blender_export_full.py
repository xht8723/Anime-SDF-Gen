"""Default-resolution export benchmark, writing only to build/validation."""
import json
from pathlib import Path
import sys
import time
import traceback
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import anime_sdf_gen
from anime_sdf_gen import session, source
from tests.fixture import fixture_face
from anime_sdf_gen.core import model
from anime_sdf_gen.core.files import read_png16
OUT=ROOT/'build'/'validation'/'v014'
OUT.mkdir(parents=True,exist_ok=True)
DRAFTS=OUT/'full-drafts';DRAFTS.mkdir(exist_ok=True)
session.draft_root=lambda:DRAFTS

try:
    anime_sdf_gen.register()
    p=bpy.context.window_manager.anime_sdf_gen
    p.uv_map='UVMap'
    p.front_only=True;p.resolution='2048';p.output=str(OUT/'face_sdf_2048')
    face=fixture_face(source)
    project=model.new_project(face.reference,face.alignment,output=str(OUT/'face_sdf_2048'))
    cutout=model.triangle();cutout['operation']='REMOVE';model.transform_contour(cutout,dx=-.14)
    model.sweep(project,model.LTR)[6]['contours'].append(cutout);model.synchronize_mirror(project)
    s=session.start(bpy.context,project,face)
    t=time.perf_counter();s.confirm();s.start_export()
    longest=0.;last=''
    while s.busy:
        start=time.perf_counter();s.advance_export(.01);longest=max(longest,time.perf_counter()-start)
        stage=s.message.split(' · ')[0]
        if stage!=last:
            print(stage,flush=True);last=stage
    assert s.output_paths,s.error
    png=read_png16(s.output_paths[0])
    assert png.shape==(2048,2048,3)
    assert np.unique(png[...,0]).size>4096
    report={'status':'PASS','seconds':time.perf_counter()-t,'largest_generation_tick_seconds':longest,
            'includes_carried_lit_cutout':True,
            'shape':list(png.shape),'unique_R_values':int(np.unique(png[...,0]).size),
            'coverage_texels':int(np.count_nonzero(png[...,2])),
            'texture':s.output_paths[0],'project':s.output_paths[1]}
    anime_sdf_gen.unregister()
except Exception:
    report={'status':'FAIL','traceback':traceback.format_exc()};traceback.print_exc()
(OUT/'export_2048.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
if report['status']!='PASS':sys.exit(1)
