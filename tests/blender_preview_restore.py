"""Compare the restored preview with the actual 0.10.0 release in Blender."""
from pathlib import Path
import ast,hashlib,sys,zipfile
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.ui_helpers import *
from tests.preview_checks import appearance,pixels
from anime_sdf_gen.core import compile,curves


def released_functions():
    archive=ROOT/'dist/anime_sdf_gen-0.10.0.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==(archive.parent/(archive.name+'.sha256')).read_text().split()[0]
    def function(text,name,cls=None):
        nodes=ast.parse(text).body
        if cls:nodes=next(n for n in nodes if isinstance(n,ast.ClassDef) and n.name==cls).body
        node=next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name)
        return ast.get_source_segment(text,node)
    with zipfile.ZipFile(archive) as z:
        namespace=dict(vars(drawing));text=z.read('drawing.py').decode()
        exec(function(text,'face_shader'),namespace)
        exec(function(text,'draw_face'),namespace)
        masks=dict(vars(session))
        exec(function(z.read('session.py').decode(),'render_mask','Session'),masks)
    return namespace['draw_face'],masks['render_mask']


legacy_draw,legacy_mask=released_functions()


def compare_release():
    s=session.ACTIVE;s.render_mask();current=s.rgba.copy()
    legacy_mask(s);np.testing.assert_array_equal(s.rgba,current)
    actual=pixels();draw=drawing.draw_face;shader=s._face_shader;batch=s._face_batch
    try:
        drawing.draw_face=legacy_draw;s._face_shader=None;s._face_batch=None
        expected=pixels()
    finally:
        drawing.draw_face=draw;s._face_shader=shader;s._face_batch=batch
    np.testing.assert_array_equal(actual,expected)
    return actual


def compare_modes():
    s=session.ACTIVE;s.flat=False;compare_release();_,lit,shadow=appearance()
    s.flat=True;compare_release();_,mask_lit,mask_shadow=appearance(flat=True)
    np.testing.assert_array_equal(lit,mask_lit);np.testing.assert_array_equal(shadow,mask_shadow)
    s.flat=False;s.sync_ui();s.redraw()


def workflow():
    anime_sdf_gen.register()
    before={k:len(getattr(bpy.data,k)) for k in ('objects','meshes','materials','images','scenes','worlds','screens','workspaces')}
    face=fixture_face(source);p=model.new_project(face.reference,face.alignment,resolution=512,output=str(OUT/'face'))
    s=session.start(bpy.context,p,face)
    yield from wait_for(lambda:s.editor.ready and s.editor.widgets)
    e=s.editor;yield .3
    report['window_dimensions']=[e.window.width,e.window.height]
    report['blender']=bpy.app.version_string
    assert tuple(s.image.size)==(512,512) and s.image.colorspace_settings.name=='Non-Color'
    assert np.isin(s.rgba[...,:3],(0,1)).all()
    for index in (0,4,8):
        click(f'KEYFRAME:left_to_right:{index}');yield .15;compare_modes()
    shot('01-restored-shadow.png')
    report['checks'].append('projected 512-pixel masks and shaded/flat GPU frames exactly match archived 0.10.0 functions at first, middle and last keyframes')

    click('KEYFRAME:left_to_right:4');yield .15
    saved=deepcopy(s.project);original=s.rgba.copy();view=e.views['AUTHOR'];r=view.region
    q=drawing.to_view(s,s.curve['points'][3]['co'],r,view);start=(r.x+q.x,r.y+q.y)
    event('MOUSEMOVE','NOTHING',start);event('LEFTMOUSE',xy=start);yield .1
    revisions=[];s.frame_times=[]
    for i in range(20):
        event('MOUSEMOVE','NOTHING',(start[0]+(i+1)*2,start[1]));yield .025
        revisions.append(s.mask_revision)
        expected=curves.raster_keyframe(s.project,s.keyframe,s.direction,s.size,False)
        np.testing.assert_array_equal(s.rgba[...,0],expected)
    assert s.dragging and not np.array_equal(s.rgba,original)
    assert len(set(revisions))>10
    event('ESC');event('ESC','RELEASE');yield .15
    assert s.project==saved and s._modal_running
    np.testing.assert_array_equal(s.rgba,original)
    compare_release();shot('02-cancelled-drag.png')
    report['checks'].append('mask follows the current curve during real dragging, without waiting for SDF compilation; Escape restores the project and mask immediately')

    click('KEYFRAME:left_to_right:6');yield .1;click('TRIANGLE');yield .1
    with bpy.context.temp_override(window=e.window,area=e.native_area):bpy.ops.anime_sdf_gen.transform(dx=-.14)
    click('LIT');yield .15
    compare_modes();shot('03-restored-lit-cutout.png')
    yield from wait_for(lambda:s.thresholds is not None or bool(s.error),60);assert not s.error,s.error
    for angle in (0,45,90,135,180,225,270,315,360):
        s.rotation=angle;s.orbit_preview=True;s.render_mask();yield .05
        direction,progress=model.rotation_sample(angle)
        np.testing.assert_array_equal(s.rgba[...,0],compile.decode(s.thresholds[...,0 if direction==model.LTR else 1],progress))
        compare_modes()
    report['checks'].append('lit cutouts, both sweep directions and all sampled 360-degree angles match the original shaded preview and mask decoding')

    # Compilation errors must remain recoverable with the restored data path.
    saved=deepcopy(s.project);s.select_keyframe(model.LTR,4)
    model.sweep(s.project,model.LTR)[4]['contours']=deepcopy(model.sweep(s.project,model.LTR)[0]['contours'])
    s.changed();yield from wait_for(lambda:bool(s.error),60)
    assert s.conflict is not None and s.rgba[...,1].any()
    compare_release();redraw();assert e.warning_bounds.y==0
    s.restore_project(saved);yield from wait_for(lambda:s.thresholds is not None or bool(s.error),60)
    assert not s.error and not s.rgba[...,1].any(),s.error
    report['checks'].append('invalid keyframe ordering displays the original magenta conflict overlay; restoring artwork clears the error and recompiles')

    projection=s.face.projected.copy();r=e.views['PREVIEW'].region;xy=(r.x+r.width/2,r.y+r.height/2)
    event('NUMPAD_6',xy=xy);event('NUMPAD_6','RELEASE',xy);yield .2
    compare_modes();np.testing.assert_array_equal(s.face.projected,projection)
    click('FRAME');yield .15;click('NEXT');yield .15
    assert s.stage=='CONFIRM' and s.playing
    angle=s.rotation;revision=s.mask_revision;yield .5
    assert s.rotation>angle and s.mask_revision>revision
    click('PLAY');yield .1;compare_modes();shot('04-restored-confirm.png')
    metadata();hover('FLAT');yield from await_tooltip('FLAT');shot('05-preview-tooltip.png')
    report['checks'].append('native orbit preserves fixed projection; Confirm starts a 360-degree sweep with the restored shaded/flat toggle')
    session.end_session(True);yield .2
    assert s._face_shader is None and s._face_batch is None and s._mask_texture is None
    assert s.preview_job is None and not s.field_cache and not s.mask_cache
    assert before=={k:len(getattr(bpy.data,k)) for k in before}
    assert fixture_face(source).reference['fingerprint']==face.reference['fingerprint']
    report['checks'].append('closing releases all preview resources and preserves the original model and datablock counts')
    anime_sdf_gen.unregister()


steps=workflow()
def tick():
    try:
        if time.perf_counter()-started>240:raise AssertionError('Preview restoration test timed out')
        delay=next(steps);(OUT/'preview-restore.json').write_text(json.dumps(report,indent=2));return delay
    except StopIteration:report['status']='PASS'
    except Exception:
        report.update(status='FAIL',traceback=traceback.format_exc());traceback.print_exc()
        try:anime_sdf_gen.unregister()
        except Exception:traceback.print_exc()
    (OUT/'preview-restore.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    with bpy.context.temp_override(window=origin):bpy.ops.wm.quit_blender()
    return None
bpy.app.timers.register(tick,first_interval=1)
