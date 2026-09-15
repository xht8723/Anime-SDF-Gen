"""Current popup regression. Run in a disposable event-enabled Blender process."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.ui_helpers import *
from anime_sdf_gen.core import curves,compile,files
from tests.preview_checks import appearance


def action(name,**kwargs):
    e=session.ACTIVE.editor
    with bpy.context.temp_override(window=e.window,area=e.native_area):
        return getattr(bpy.ops.anime_sdf_gen,name)(**kwargs)


def authored_mask():
    s=session.ACTIVE
    return curves.raster_keyframe(s.project,s.keyframe,s.direction,s.size)


def workflow():
    # Reset only this disposable test's known generated output set.
    for name in ('face.png','face_right.png','face.sdfproject.json'):(OUT/name).unlink(missing_ok=True)
    anime_sdf_gen.register()
    before={k:len(getattr(bpy.data,k)) for k in ('objects','meshes','materials','images','scenes','worlds','screens','workspaces')}
    face=fixture_face(source);fingerprint=face.reference['fingerprint']
    p=model.new_project(face.reference,face.alignment,keyframes=8,resolution=512,output=str(OUT/'face'))
    p['authoring']['stage']='ORIENT';s=session.start(bpy.context,p,face)
    yield from wait_for(lambda:s.editor.ready and s.editor.widgets)
    e=s.editor;yield .3;redraw();metadata()
    report['window_dimensions']=[e.window.width,e.window.height]
    report['ui_scale_preference']=bpy.context.preferences.view.ui_scale
    assert 'PREVIEW' not in e.boxes and 'AUTHOR' in e.boxes
    click('KEYFRAMES_MORE');yield .15;assert s.project['authoring']['keyframe_count']==9
    click('KEYFRAMES_LESS');yield .15;assert s.project['authoring']['keyframe_count']==8
    assert action('settings',section='KEYFRAME_COUNT',keyframes=9)=={'FINISHED'}
    click('NEXT');yield .25;assert s.stage=='FIT' and len(s.project['authoring']['anchors'])==3
    click('NEXT');yield .3;assert s.stage=='EDIT';redraw()
    assert (s.direction,s.key_index,s.rotation)==(model.LTR,0,0) and not s.playing
    assert len([w for w in e.widgets if w['key'].startswith('KEYFRAME:')])==18,([w['key'] for w in e.widgets],s.project['authoring'])
    assert all(title in [t[0] for t in labels()] for title in model.SWEEP_LABELS.values())
    for direction in model.SWEEP_LABELS:
        for frame in model.sweep(s.project,direction):
            assert len(set(p['co'][0] for p in frame['contours'][0]['points']))==1
    click('KEYFRAME:left_to_right:4');yield .2;shot('01-two-complete-sweeps.png')
    hover('MIRROR');yield from await_tooltip('MIRROR');metadata();shot('02-full-sweep-tooltip.png')
    report['checks'].append('single fitting view, default markers, even count controls, first-frame entry, two labelled full rows and straight presets')

    click('MIRROR');yield .15;assert not s.project['mirror_sweeps']
    primary=json.dumps(model.sweep(s.project,model.LTR),sort_keys=True)
    click('KEYFRAME:right_to_left:4');yield .15
    click('ADD_KEYFRAME');yield .15
    assert len(model.sweep(s.project,model.RTL))==10 and len(model.sweep(s.project,model.LTR))==9
    click('UNDO');yield .15;assert len(model.sweep(s.project,model.RTL))==9
    click('REDO');yield .15;assert len(model.sweep(s.project,model.RTL))==10
    click('REMOVE_KEYFRAME');yield .15
    assert json.dumps(model.sweep(s.project,model.LTR),sort_keys=True)==primary
    click('KEYFRAME:right_to_left:0');yield .15
    saved=model.dumps(s.project)
    assert action('action',action='REMOVE_KEYFRAME')=={'CANCELLED'}
    assert model.dumps(s.project)==saved and s.error
    redraw();assert e.warning_bounds.y==0
    click('DISMISS_ERROR');yield .15
    click('KEYFRAME:right_to_left:4');yield .15

    # Cancelling a real control-point drag restores artwork and keeps input alive.
    view=e.views['AUTHOR'];r=view.region;co=s.curve['points'][3]['co']
    xy=drawing.to_view(s,co,r,view);start=(r.x+xy.x,r.y+xy.y)
    saved=model.dumps(s.project)
    event('MOUSEMOVE','NOTHING',start);event('LEFTMOUSE',xy=start);yield .1
    event('MOUSEMOVE','NOTHING',(start[0]+20,start[1]));yield .15
    assert s.dragging and model.dumps(s.project)!=saved
    event('ESC');event('ESC','RELEASE');yield .15
    assert not s.dragging and model.dumps(s.project)==saved and s._modal_running
    report['checks'].append('independent insertion/removal, undo/redo, protected endpoints and actual drag cancellation preserve the other row and modal controls')

    click('KEYFRAME:left_to_right:6');yield .15
    opposite=json.dumps(model.sweep(s.project,model.RTL),sort_keys=True)
    click('TRIANGLE');yield .15;action('transform',dx=-.14)
    click('LIT');yield .15
    yield from wait_for(lambda:s.thresholds is not None or bool(s.error));assert not s.error,s.error
    hole=curves.fill_polygon(curves.polygon(s.curve,tolerance=model.SPAN/(s.size*4)),s.size)
    assert not authored_mask()[hole].any() and not s.rgba[...,1].any()
    assert json.dumps(model.sweep(s.project,model.RTL),sort_keys=True)==opposite
    click('KEYFRAME:left_to_right:4');yield .15;assert not authored_mask()[hole].any()
    click('KEYFRAME:left_to_right:6');yield .15;click('LAYER:1');yield .15
    original_mask=authored_mask()
    xy=drawing.to_view(s,s.curve['points'][0]['co'],r,view);start=(r.x+xy.x,r.y+xy.y)
    event('MOUSEMOVE','NOTHING',start);event('LEFTMOUSE',xy=start);yield .1
    s.frame_times=[]
    for i in range(24):
        event('MOUSEMOVE','NOTHING',(start[0]-(i+1)*1.2,start[1]+(i+1)*.35));yield .012
    assert s.dragging and np.any(authored_mask()!=original_mask)
    event('LEFTMOUSE','RELEASE',(start[0]-28.8,start[1]+8.4));yield .2
    intervals=np.diff(s.frame_times)*1000
    report['drag_frame_median_ms']=float(np.median(intervals)) if len(intervals) else None
    click('UNDO');yield .15;np.testing.assert_array_equal(authored_mask(),original_mask)
    click('REDO');yield .15;assert np.any(authored_mask()!=original_mask)
    click('MIRROR');yield .2;assert s.project['mirror_sweeps']
    yield from wait_for(lambda:s.thresholds is not None or bool(s.error));assert not s.error,s.error
    np.testing.assert_array_equal(s.thresholds[...,0],s.thresholds[:,::-1,1])
    np.testing.assert_array_equal(s.thresholds,compile.compile_project(s.project,s.size,s.domain))
    shot('03-local-lit-cutout.png')
    report['checks'].append('lit cutouts carry only within their row, update during real dragging, survive undo/redo and mirror only into corresponding opposite frames')

    # Back endpoints may differ, but they must remain representable and editable.
    click('KEYFRAME:left_to_right:8');yield .15;click('TRIANGLE');yield .15
    action('transform',dx=-.14);click('LIT');yield .15
    yield from wait_for(lambda:s.thresholds is not None or bool(s.error))
    assert not s.error and s.seam_warning and 'Back' in s.seam_warning,s.error
    redraw();assert e.warning_bounds.y==0;shot('04-endpoint-seam-warning.png')
    click('DELETE_SHAPE');yield .15
    yield from wait_for(lambda:s.thresholds is not None);assert not s.seam_warning
    report['checks'].append('different orbit endpoints report a nonblocking footer seam warning without merging artwork')

    # A complete automatic orbit must cross both hemispheres and wrap, not bounce.
    click('KEYFRAME:left_to_right:0');yield .15;click('PLAY');yield .15
    samples=[];deadline=time.perf_counter()+12.5
    while time.perf_counter()<deadline:
        samples.append(s.rotation);yield .2
    assert any(90<a<180 for a in samples) and any(270<a<360 for a in samples)
    assert any(b<a for a,b in zip(samples,samples[1:])),samples
    assert all(b>=a or (a>330 and b<30) for a,b in zip(samples,samples[1:]))
    report['orbit_samples_degrees']=samples
    click('PLAY');yield .15
    # Actual progress-bar input samples all four cardinal light directions.
    masks=[];s.flat=True;s.sync_ui()
    for angle in (0,90,180,270,360):
        redraw();x,y,w,h=e.boxes['SLIDER'];pos=(x+w*angle/360,y+h/2)
        if angle==360:pos=(pos[0]-.1,pos[1])
        event('MOUSEMOVE','NOTHING',pos);event('LEFTMOUSE',xy=pos);event('LEFTMOUSE','RELEASE',pos);yield .15
        assert abs(s.rotation-angle)<.4,(s.rotation,angle)
        _,lit,shadow=appearance(flat=True);masks.append((int(lit.sum()),int(shadow.sum())))
    assert masks[0][1]==0 and masks[2][0]==0 and masks[4][1]==0,masks
    s.flat=False;s.sync_ui()
    report['checks'].append('12-second automatic 360-degree orbit advances through both maps and wraps; slider input decodes both hemispheres and cardinal endpoints')

    click('NEXT');yield .2
    assert s.stage=='CONFIRM' and s.playing and s.rotation<30 and 'AUTHOR' not in e.boxes
    click('PACK:character_left:B');yield .15
    click('PACK:character_right:SEPARATE');yield .15
    assert s.project['settings']['packing']=={'character_left':'B','character_right':'SEPARATE','face_coverage':'R'}
    assert s.playing
    projection=s.face.projected.copy();rotation=list(e.views['PREVIEW'].view_rotation)
    r=e.views['PREVIEW'].region;pos=(r.x+r.width/2,r.y+r.height/2)
    event('NUMPAD_6',xy=pos);event('NUMPAD_6','RELEASE',pos);yield .25
    assert rotation!=list(e.views['PREVIEW'].view_rotation)
    np.testing.assert_array_equal(projection,s.face.projected)
    click('FRAME');yield .15;shot('05-confirm-full-orbit.png')
    art=model.dumps(s.project);old_id=s.registry.id
    with bpy.context.temp_override(window=e.window,area=e.native_area):
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'save-during-confirm.blend'),check_existing=False)
    yield from wait_for(lambda:session.ACTIVE is not None and session.ACTIVE.registry.id!=old_id and session.ACTIVE.editor.ready)
    s=session.ACTIVE;e=s.editor;yield .3
    assert s.stage=='CONFIRM' and s.playing and 'AUTHOR' not in e.boxes
    assert model.dumps(s.project)==art
    yield from wait_for(lambda:s.thresholds is not None)
    shot('06-resumed-confirm.png')
    report['checks'].append('Confirm restarts a full orbit, keeps packing settings, delegates native orbit without moving projection, and resumes artwork/playback after save')

    painter=e.painter;click('GENERATE');yield from wait_for(lambda:session.ACTIVE is None,90)
    assert painter.shader is None and not s.field_cache and s._mask_texture is None
    assert before=={k:len(getattr(bpy.data,k)) for k in before}
    assert fixture_face(source).reference['fingerprint']==fingerprint
    layout,sidecar=files.output_layout(s.project,s.project['settings']['output'])
    assert len(layout)==2 and len(s.output_paths)==3
    saved=files.load_project(sidecar)
    artwork=dict(saved);artwork.pop('textures',None)
    assert model.dumps(artwork)==model.dumps(s.project)
    for entry in layout:
        codes=files.read_png16(entry['path'])
        assert codes.dtype==np.uint16 and codes.shape[:2]==(512,512)
    assert bpy.ops.anime_sdf_gen.open_project(filepath=str(sidecar))=={'FINISHED'}
    yield from wait_for(lambda:session.ACTIVE.editor.ready)
    assert model.dumps(session.ACTIVE.project)==model.dumps(saved)
    session.end_session(True);yield .2
    assert before=={k:len(getattr(bpy.data,k)) for k in before}
    report['checks'].append('mixed RGB/grayscale export and project reopening preserve new schema, artwork and map routes; no source or datablock changes after finish/reopen/cancel')
    anime_sdf_gen.unregister()


steps=workflow()
def tick():
    try:
        if time.perf_counter()-started>240:raise AssertionError('Full sweep UI timed out')
        delay=next(steps);(OUT/'full-sweeps.json').write_text(json.dumps(report,indent=2));return delay
    except StopIteration:report['status']='PASS'
    except Exception:
        report.update(status='FAIL',traceback=traceback.format_exc());traceback.print_exc()
        try:anime_sdf_gen.unregister()
        except Exception:traceback.print_exc()
    (OUT/'full-sweeps.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    with bpy.context.temp_override(window=origin):bpy.ops.wm.quit_blender()
    return None
bpy.app.timers.register(tick,first_interval=1)
