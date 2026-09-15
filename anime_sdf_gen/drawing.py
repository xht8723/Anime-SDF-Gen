"""Full-size projected curves, surface landmarks, and live inspection."""
import time
import math
import json
from functools import lru_cache
import bpy
import blf
import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_texture_2d
from mathutils import Vector
from . import session, source
from .editor import scale, window_region
from .core import curves, model


def label(text, x, y, size=12, color=(.87,.90,.95,1)):
    blf.size(0, size*scale())
    blf.color(0, *color)
    blf.position(0, x, y, 0)
    blf.draw(0, text)


def lines(coords, color, width=1, mode='LINE_STRIP'):
    if len(coords) < 2 or any(p is None for p in coords):
        return
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    shader.bind()
    shader.uniform_float('color', color)
    gpu.state.line_width_set(width*scale())
    batch_for_shader(shader, mode, {'pos': coords}).draw(shader)


def disc(x, y, radius, color):
    radius *= scale()
    coords = [(x,y)]+[(x+radius*math.cos(i*2*math.pi/20), y+radius*math.sin(i*2*math.pi/20)) for i in range(21)]
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    shader.bind(); shader.uniform_float('color',color)
    batch_for_shader(shader, 'TRIS', {'pos': coords}, indices=[(0,i,i+1) for i in range(1,21)]).draw(shader)


def face_shader():
    info=gpu.types.GPUShaderCreateInfo()
    info.vertex_in(0,'VEC3','pos')
    info.vertex_in(1,'VEC3','normal')
    info.vertex_in(2,'VEC2','texCoord')
    interface=gpu.types.GPUStageInterfaceInfo('anime_sdf_gen_interface')
    interface.smooth('VEC2','uv');interface.smooth('VEC3','surfaceNormal')
    info.vertex_out(interface)
    info.push_constant('MAT4','viewProjection')
    info.push_constant('VEC3','lightDirection')
    info.push_constant('VEC3','faceForward')
    info.push_constant('FLOAT','flatView')
    info.sampler(0,'FLOAT_2D','image')
    info.fragment_out(0,'VEC4','fragColor')
    info.vertex_source('void main(){uv=texCoord;surfaceNormal=normal;gl_Position=viewProjection*vec4(pos,1.0);}')
    info.fragment_source('''void main(){
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
    }''')
    return gpu.shader.create_from_info(info)


def rect(x,y,w,h,color):
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    shader.bind();shader.uniform_float('color',color)
    batch_for_shader(shader,'TRI_FAN',{'pos':[(x,y),(x+w,y),(x+w,y+h),(x,y+h)]}).draw(shader)


def to_view(s,xy,region,view):
    return view.project(source.world_point(s.project['alignment'],xy,0))


def from_view(s,xy,region,view):
    origin,direction=view.ray(xy)
    a=s.project['alignment'];normal=Vector(a['forward']);denom=direction.dot(normal)
    if abs(denom)<1e-8:return None
    hit=origin+direction*((Vector(a['center'])-origin).dot(normal)/denom)
    delta=hit-Vector(a['center'])
    return np.array([delta.dot(Vector(a['right']))/a['width']+.5,delta.dot(Vector(a['up']))/a['height']+.5])


@lru_cache(maxsize=64)
def flat_contour(serialized):
    c=json.loads(serialized)
    points=curves.flatten(c,.0007)
    return np.vstack([points,points[0]]) if c['closed'] else points


def project_points(s,points,region,view):
    a=s.project['alignment']
    world=(np.asarray(a['center'])+(points[:,0,None]-.5)*a['width']*np.asarray(a['right'])
           +(points[:,1,None]-.5)*a['height']*np.asarray(a['up']))
    clip=np.column_stack([world,np.ones(len(world))]) @ np.asarray(view.perspective_matrix).T
    if np.any(clip[:,3]<=0):return []
    # GPU vertex buffers consume float32. A float64 NumPy buffer can be accepted
    # without an exception yet draw corrupted coordinates on some backends.
    return np.asarray((clip[:,:2]/clip[:,3,None]+1)*np.array([region.width,region.height])/2,dtype=np.float32)


def contour_lines(s,c,region,view,color,width=1):
    points=flat_contour(json.dumps(c,sort_keys=True))
    lines(project_points(s,points,region,view),color,width)


def draw_author(s,region,view):
    u=scale()
    if s.stage!='EDIT':return
    frames=model.sweep(s.project,s.direction)
    for index in (s.key_index-1,s.key_index+1):
        if 0<=index<len(frames):
            for c in frames[index]['contours']:
                if c.get('enabled',True):contour_lines(s,c,region,view,(.4,.8,.9,.3))
    selected_contours={ci for ci,_ in s.selected}
    for ci,c in enumerate(s.keyframe['contours']):
        if not c.get('enabled',True):continue
        color=(1,.65,.18,1) if ci in selected_contours else (.4,.85,.9,.8)
        contour_lines(s,c,region,view,color,2)
        for pi,p in enumerate(c['points']):
            q=to_view(s,p['co'],region,view)
            if q is None:continue
            selected=(ci,pi) in s.selected;active=ci==s.contour and pi==s.point
            disc(*q,6 if active and selected else 4,(1,.65,.18,1) if selected else (.4,.8,.88,.8))
            if active and selected:
                for handle in curves.handles(c,pi):
                    h=to_view(s,handle,region,view)
                    if h is not None:lines([q,h],(.94,.9,.55,.85));disc(*h,3,(.95,.9,.65,1))


def draw_landmarks(s,region,view):
    for name,anchor in s.project['authoring']['anchors'].items():
        q=view.project(anchor['world'])
        if q is None:continue
        color=(.25,1,.55,1) if name==s.landmark else (.5,.87,.75,1)
        disc(*q,5,color)
        label({'nose':'Nose','mouth':'Mouth Center','chin':'Chin'}[name],q.x+10*scale(),q.y+5*scale(),12,color)


def pick(s,mouse,region,view):
    candidates=[]
    if s.stage=='FIT':
        for name,anchor in s.project['authoring']['anchors'].items():
            q=view.project(anchor['world'])
            if q is not None:candidates.append((np.linalg.norm(np.array(q)-mouse),('landmark',name)))
    else:
        for ci,c in enumerate(s.keyframe['contours']):
            if not c.get('enabled',True):continue
            for pi,p in enumerate(c['points']):
                q=to_view(s,p['co'],region,view)
                if q is not None:candidates.append((np.linalg.norm(np.array(q)-mouse),('co',ci,pi)))
                if ci==s.contour and pi==s.point and (ci,pi) in s.selected:
                    for kind,h in zip(('left','right'),curves.handles(c,pi)):
                        q=to_view(s,h,region,view)
                        if q is not None:candidates.append((np.linalg.norm(np.array(q)-mouse),(kind,ci,pi)))
    if not candidates:return None
    distance,item=min(candidates,key=lambda p:p[0])
    return item if distance<=12*scale() else None


def inside(point,box):
    x,y,w,h=box
    return x<=point[0]<=x+w and y<=point[1]<=y+h


def draw_face(s,view):
    if getattr(s,'_face_shader',None) is None:s._face_shader=face_shader()
    if getattr(s,'_face_batch',None) is None:
        mesh=s.preview_object.data;normals=np.empty(len(mesh.vertices)*3,dtype=np.float32)
        mesh.vertices.foreach_get('normal',normals);indices=s.face.triangles.ravel()
        s._face_batch=batch_for_shader(s._face_shader,'TRIS',{
            'pos':s.face.vertices[indices].astype(np.float32),'normal':normals.reshape(-1,3)[indices],
            'texCoord':((s.face.projected[...,:2]+model.PAD)/model.SPAN).reshape(-1,2).astype(np.float32)})
    a=s.project['alignment'];shader=s._face_shader;shader.bind()
    shader.uniform_float('viewProjection',view.perspective_matrix)
    angle=math.radians(s.rotation)
    light=Vector(a['forward'])*math.cos(angle)+Vector(a['right'])*math.sin(angle)+Vector(a['up'])*.25
    shader.uniform_float('lightDirection',light.normalized());shader.uniform_float('faceForward',a['forward'])
    shader.uniform_float('flatView',1. if s.flat else 0.)
    # Image.update() does not invalidate every backend's from_image cache in
    # an offscreen draw. Upload this revision explicitly in the GPU context.
    if s._mask_texture is None or s._mask_texture_revision!=s.mask_revision:
        s._mask_texture=gpu.types.GPUTexture((s.size,s.size),format='RGBA32F',
            data=gpu.types.Buffer('FLOAT',s.rgba.size,s.rgba.ravel()))
        s._mask_texture.filter_mode(False)
        s._mask_texture_revision=s.mask_revision
    shader.uniform_sampler('image',s._mask_texture)
    gpu.state.blend_set('NONE');gpu.state.depth_test_set('LESS_EQUAL');gpu.state.depth_mask_set(True)
    s._face_batch.draw(shader)


def view_buffer(s,role,native_region):
    e=s.editor;v=e.views[role];r=v.region
    size=(max(1,r.width),max(1,r.height))
    buffer=e.buffers.get(role)
    if buffer is None or (buffer.width,buffer.height)!=size:
        if buffer:buffer.free()
        buffer=e.buffers[role]=gpu.types.GPUOffScreen(*size)
        e.reference_keys.pop(role,None)
    if role=='PREVIEW' and s.stage in ('EDIT','CONFIRM'):
        e.reference_keys.pop(role,None)
        with buffer.bind(),gpu.matrix.push_pop():
            gpu.state.active_framebuffer_get().clear(color=(.055,.065,.083,1),depth=1.)
            draw_face(s,v)
    else:
        key=(e.geometry_revision,s.project['authoring']['reference'],tuple(v.view_location),
             tuple(v.view_rotation),v.view_distance,v.view_perspective,size)
        if e.reference_keys.get(role)!=key:
            buffer.draw_view3d(s.scene,s.scene.view_layers[0],e.reference_space,native_region,
                               v.view_matrix,v.projection_matrix,do_color_management=True)
            e.reference_keys[role]=key
    return buffer


def draw_popup(s):
    if s.closed or not s.editor or not s.editor.owns_context(bpy.context):return
    from . import interface
    start=time.perf_counter();e=s.editor;region=bpy.context.region
    old_blend=gpu.state.blend_get();old_depth=gpu.state.depth_test_get();old_mask=gpu.state.depth_mask_get()
    old_scissor=gpu.state.scissor_get();old_viewport=gpu.state.viewport_get()
    old_model=gpu.matrix.get_model_view_matrix();old_projection=gpu.matrix.get_projection_matrix()
    try:
        e.navigation.drawing=True
        s.normalize_selection();e.navigation.poll();e.resize(region)
        buffers={name:view_buffer(s,name,region) for name in ('AUTHOR','PREVIEW') if name in e.boxes}
        gpu.state.depth_test_set('NONE');gpu.state.depth_mask_set(False)
        gpu.state.blend_set('ALPHA')
        gpu.state.viewport_set(*old_viewport)
        gpu.matrix.load_matrix(old_model);gpu.matrix.load_projection_matrix(old_projection)
        rect(0,0,region.width,region.height,interface.BG)
        for name,buffer in buffers.items():
            v=e.views[name];r=v.region
            draw_texture_2d(buffer.texture_color,(r.x,r.y),r.width,r.height)
            gpu.state.scissor_test_set(True);gpu.state.scissor_set(r.x,r.y,r.width,r.height)
            with gpu.matrix.push_pop():
                gpu.matrix.translate((r.x,r.y,0))
                if name=='AUTHOR':draw_author(s,r,v)
                if name=='AUTHOR' and s.curve_edit:s.curve_edit.draw(r,v)
                if s.stage=='FIT':draw_landmarks(s,r,v)
            gpu.state.scissor_test_set(False)
        interface.build(s,region)
        s._draw_error=None
        if s.dragging or s.playing:
            if not hasattr(s,'frame_times'):s.frame_times=[]
            s.frame_times.append(time.perf_counter())
            s.frame_times=s.frame_times[-512:]
    except Exception as exc:
        if getattr(s,'_draw_error',None)!=str(exc):
            import traceback
            traceback.print_exc();s._draw_error=str(exc);s.notify_error(exc)
        # A failed preview must not remove the controls needed to recover/close.
        gpu.state.scissor_test_set(False);gpu.state.viewport_set(*old_viewport)
        gpu.state.depth_test_set('NONE');gpu.state.depth_mask_set(False)
        gpu.matrix.load_matrix(old_model);gpu.matrix.load_projection_matrix(old_projection)
        interface.build(s,region)
    finally:
        e.navigation.drawing=False
        gpu.state.scissor_set(*old_scissor);gpu.state.scissor_test_set(False)
        gpu.state.viewport_set(*old_viewport)
        gpu.matrix.load_matrix(old_model);gpu.matrix.load_projection_matrix(old_projection)
        gpu.state.depth_test_set(old_depth);gpu.state.depth_mask_set(old_mask)
        gpu.state.line_width_set(1);gpu.state.blend_set(old_blend)
        s.last_draw_ms=(time.perf_counter()-start)*1000


def attach(s):
    s.registry.draw_handlers.append((bpy.types.SpaceView3D.draw_handler_add(draw_popup,(s,),'WINDOW','POST_PIXEL'),'WINDOW'))


class ANIME_SDF_GEN_OT_interact(bpy.types.Operator):
    bl_idname='anime_sdf_gen.interact'
    bl_label='Anime SDF Gen Interaction'
    bl_options={'INTERNAL'}

    def invoke(self,context,event):
        s=session.ACTIVE
        if not s or s._modal_running:return {'CANCELLED'}
        self.owner=s.registry.id;self.drag=None;self.before=None;self.last_draw=0.
        from .curve_input import CurveInput
        s.curve_edit=CurveInput(s)
        self._event_timer=context.window_manager.event_timer_add(.025,window=context.window)
        s._event_timer=self._event_timer;s._modal_running=True
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _finish(self,context):
        s=session.ACTIVE
        if s and s.registry.id==self.owner:
            s.cancel_curve_edit()
            s._modal_running=False;s.dragging=False
        if getattr(self,'_event_timer',None):
            try:context.window_manager.event_timer_remove(self._event_timer)
            except (ReferenceError,ValueError):pass
            self._event_timer=None
        return {'FINISHED'}

    def modal(self,context,event):
        try:return self._modal(context,event)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            s=session.ACTIVE
            if not s or s.closed:return {'FINISHED'}
            if s.registry.id!=self.owner:return self._finish(context)
            try:
                s.cancel_curve_edit()
                if self.before:s.rollback(self.before)
                else:s.normalize_selection()
            except Exception:
                traceback.print_exc()
            self.before=None;self.drag=None;s.dragging=False;s.playing=False
            s.notify_error(exc)
            # Never terminate the only input handler because an edit failed.
            return {'RUNNING_MODAL'}

    def _modal(self,context,event):
        s=session.ACTIVE
        if not s or s.closed or s.registry.id!=self.owner:return self._finish(context)
        if not s.editor or not s.editor.owns_context(context):return {'PASS_THROUGH'}
        e=s.editor;native=window_region(e.native_area)
        e.navigation.poll()
        if event.type=='WINDOW_DEACTIVATE':
            e.clear_hover();s.cancel_curve_edit()
            if self.before:s.rollback(self.before)
            self.before=self.drag=None;s.dragging=False
            return {'PASS_THROUGH'}
        if event.type=='TIMER':return {'PASS_THROUGH'}
        # Blender's modal orbit/pan/zoom receives its own moves, snapping keys,
        # release and Esc. Its actual camera is mirrored by the draw/timer path.
        if e.navigation.running():e.clear_hover();return {'PASS_THROUGH'}
        s.normalize_selection()
        mouse=np.array([event.mouse_x-native.x,event.mouse_y-native.y],dtype=float)
        e.resize(native)
        role=next((name for name in ('AUTHOR','PREVIEW') if name in e.boxes and e.views[name].region.contains(mouse)),None)
        if self.drag and self.drag[0] not in ('rotation','divider'):role=self.drag_role
        if s.curve_edit.active:role='AUTHOR'
        view=e.views.get(role);region=view.region if view else None
        local=mouse-np.array([region.x,region.y]) if region else None
        if s.curve_edit.active and s.curve_edit.modal(event,local,region,view):return {'RUNNING_MODAL'}
        if event.ctrl and event.type=='Z' and event.value=='PRESS':
            e.clear_hover()
            if not s.busy and not self.drag:
                self.before=s.checkpoint()
                s.restore_project(s.history.redo(s.project) if event.shift else s.history.undo(s.project))
                self.before=None
            return {'RUNNING_MODAL'}
        if event.ctrl and event.type=='S' and event.value=='PRESS' and not self.drag:
            e.clear_hover()
            s.save_requested=True;return {'RUNNING_MODAL'}
        if event.ctrl and event.type=='SPACE' and event.value=='PRESS' and role and not self.drag:
            e.maximize(role);return {'RUNNING_MODAL'}
        if not self.drag:
            hovered=next((widget for widget in reversed(e.widgets) if inside(mouse,widget['box']) and
                          ('clip' not in widget or inside(mouse,widget['clip']))),None)
            hover=hovered['key'] if hovered else None
            e.set_hover(hover,mouse)
            if event.type=='LEFTMOUSE' and event.value=='PRESS' and hovered:
                e.clear_hover()
                if hovered['enabled']:
                    from .interface import dispatch
                    e.navigation.stop();self.before=s.checkpoint()
                    dispatch(s,hovered['key'])
                    self.before=None
                    if not s.closed:s.redraw()
                return {'RUNNING_MODAL'}
        if s.busy:return {'RUNNING_MODAL'}
        if event.type in ('WHEELUPMOUSE','WHEELDOWNMOUSE') and event.value=='PRESS' and not self.drag:
            e.clear_hover()
            direction=1 if event.type=='WHEELUPMOUSE' else -1
            if e.warning_bounds and e.warning_bounds.contains(mouse):
                e.warning_scroll=max(0,min(e.warning_scroll_max,e.warning_scroll-direction*36*scale()))
            elif e.boxes['PANEL'].contains(mouse):e.panel_scroll=max(0,min(getattr(e,'panel_scroll_max',0),e.panel_scroll-direction*48*scale()))
            elif s.stage=='EDIT' and e.boxes['SHELF'].contains(mouse):s.keyframe_scroll=max(0,getattr(s,'keyframe_scroll',0)-direction)
            else:direction=None
            if direction is not None:e.redraw();return {'RUNNING_MODAL'}
        if not self.drag and view:
            from .navigation import LOCKED_NAVIGATION
            navigation=e.navigation.match(event)
            if navigation:
                e.clear_hover()
                if s.stage=='EDIT' and role=='AUTHOR' and navigation not in LOCKED_NAVIGATION:
                    return {'RUNNING_MODAL'}
                e.navigation.prepare(role,interactive=True)
                return {'PASS_THROUGH'}
        if not self.drag and s.stage=='EDIT' and role=='AUTHOR':
            if s.curve_edit.modal(event,local,region,view):
                e.clear_hover();return {'RUNNING_MODAL'}
        if not self.drag and event.type=='LEFTMOUSE' and event.value=='PRESS':
            e.clear_hover()
            e.navigation.stop()
            divider=e.boxes.get('DIVIDER')
            if divider and inside(mouse,(divider.x-4*scale(),divider.y,divider.width+8*scale(),divider.height)):
                self.drag=('divider',);return {'RUNNING_MODAL'}
            if s.stage in ('EDIT','CONFIRM'):
                x,y,w,h=e.boxes['SLIDER'];margin=6*scale()
                # Include the endpoint knob, even when DPI scaling places its
                # center between integer mouse coordinates.
                if inside(mouse,(x-margin,y,w+2*margin,h)):
                    self.drag=('rotation',);s.playing=False
        if self.drag and self.drag[0] in ('divider','rotation'):
            mode=self.drag[0]
            if event.type=='MOUSEMOVE' or (mode=='rotation' and event.type=='LEFTMOUSE'):
                if mode=='divider':e.split_ratio=float(np.clip(mouse[0]/e.boxes['SHELF'].width,.25,.75))
                else:
                    x,y,w,h=e.boxes['SLIDER'];s.rotation=float(np.clip((mouse[0]-x)/w*360,0,360))
                    s.orbit_preview=True;s.render_mask();s.sync_ui()
                e.redraw()
            if (event.type in ('LEFTMOUSE','MIDDLEMOUSE') and event.value=='RELEASE') or event.type=='ESC':self.drag=None
            return {'RUNNING_MODAL'}
        if event.type=='LEFTMOUSE' and event.value=='PRESS' and region and s.stage=='FIT':
            hit=pick(s,local,region,view) or ('landmark',s.landmark);self.before=s.checkpoint()
            if not s.pick_landmark(region,view,local,hit[1]):
                self.before=None;return {'RUNNING_MODAL'}
            s.history.push(self.before['project']);s.landmark=hit[1]
            self.drag=hit;self.drag_role=role
            s.dragging=True;s.playing=False;s.sync_ui();s.redraw();return {'RUNNING_MODAL'}
        if self.drag:
            if event.type=='ESC' and event.value=='PRESS':
                s.rollback(self.before)
                s.dragging=False;self.drag=None;self.before=None;return {'RUNNING_MODAL'}
            if event.type in ('MOUSEMOVE','LEFTMOUSE'):
                s.pick_landmark(region,view,local,s.landmark)
                released=event.type=='LEFTMOUSE' and event.value=='RELEASE';now=time.perf_counter()
                if released or now-self.last_draw>=1/60:s.changed(dragging=not released);self.last_draw=now
                if released:
                    s.dragging=False;self.drag=None;self.before=None;s.redraw()
                return {'RUNNING_MODAL'}
        # The popup owns its keymap. N/T, native fullscreen, editor switches and
        # transform keys cannot expose Blender chrome or edit the preview mesh.
        return {'RUNNING_MODAL'}

    def cancel(self,context):
        self._finish(context)
