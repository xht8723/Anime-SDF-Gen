"""Blender panels and explicit authoring actions; no persistent scene properties."""
from copy import deepcopy
from pathlib import Path
import traceback
import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)
from bpy_extras.io_utils import ImportHelper, ExportHelper
from . import source, session
from .core import model, curves
from .core.files import load_project, atomic_text, output_paths
from .drawing import ANIME_SDF_GEN_OT_interact

SKIP={'SKIP_SAVE'}


def active_edit(context):
    s=session.ACTIVE
    return s if s and not s.busy and not s._syncing else None


def point_changed(self,context):
    s=active_edit(context)
    if s:
        s.push_history()
        s.curve['points'][s.point]['co']=list(self.point_xy)
        s.changed()


def handles_changed(self,context):
    s=active_edit(context)
    if s:
        s.push_history()
        p=s.curve['points'][s.point]
        if self.handle_mode=='FREE' and p['mode']!='FREE':
            left,right=curves.handles(s.curve,s.point)
            p.update(left=(left-p['co']).tolist(),right=(right-p['co']).tolist())
        else:
            p.update(left=list(self.handle_left),right=list(self.handle_right))
        p['mode']=self.handle_mode
        s.changed()


def mode_changed(self,context):
    s=active_edit(context)
    if s:
        s.push_history()
        for ci,pi in s.selected or {(s.contour,s.point)}:
            c=s.keyframe['contours'][ci];p=c['points'][pi]
            if self.handle_mode=='FREE' and p['mode']!='FREE':
                left,right=curves.handles(c,pi)
                p.update(left=(left-p['co']).tolist(),right=(right-p['co']).tolist())
            p['mode']=self.handle_mode
        s.changed()


def rotation_changed(self,context):
    s=active_edit(context)
    if s:
        s.rotation=self.rotation
        s.orbit_preview=True
        s.render_mask()


def flat_changed(self,context):
    s=active_edit(context)
    if s:
        s.flat=self.flat
        s.redraw()


def operation_changed(self,context):
    s=active_edit(context)
    if s and s.curve['closed']:
        s.push_history()
        s.curve['operation']=self.layer_operation
        s.changed()


def output_changed(self,context):
    s=active_edit(context)
    if s:
        s.project['settings'].update(output=self.output,resolution=int(self.resolution))
        s.draft_due=0.1


def reference_changed(self, context):
    s=active_edit(context)
    if s:
        s.project['authoring']['reference']=self.reference
        if s.editor:s.editor.refresh_appearance()
        s.draft_due=.1


def fitting_settings_changed(self, context):
    s=active_edit(context)
    if s:
        s.project['preset']=self.preset
        s.project['authoring']['keyframe_count']=self.keyframes
        s.draft_due=.1


class ANIME_SDF_GEN_Properties(bpy.types.PropertyGroup):
    source_method: EnumProperty(name='Source',items=[('SELECTED','Selected Faces','Use visible selected polygons on the active Edit Mode mesh'),('VERTEX_GROUP','Vertex Group','Use polygons whose vertices all have positive weight in a group')],default='SELECTED',options=SKIP)
    vertex_group: StringProperty(name='Face vertex group',options=SKIP)
    uv_map: StringProperty(name='Output UV map',default='',options=SKIP)
    front_only: BoolProperty(name='Frontal subset only',description='Restrict the input region to front-facing triangles before UV validation; back surfaces are outside the output domain',default=True,options=SKIP)
    keyframes: IntProperty(name='Shadow keyframes',description='Number of keyframes in each complete boundary sweep',default=9,min=2,max=33,step=1,update=fitting_settings_changed,options=SKIP)
    mirror_sweeps: BoolProperty(name='Mirror Full Sweep',default=True,options=SKIP)
    preset: EnumProperty(name='Starting preset',items=[('CLEAN','Clean Face','Straight boundaries across the entire face'),('NOSE','Nose Accent','More pronounced nose profile')],default='CLEAN',update=fitting_settings_changed,options=SKIP)
    reference: EnumProperty(name='Reference',items=[('NEUTRAL','Neutral Shading','Sculpt-style neutral lighting'),('MATERIAL','Original Materials','Show copied source materials under preview lighting')],default='NEUTRAL',update=reference_changed,options=SKIP)
    resolution: EnumProperty(name='Texture resolution',items=[(str(n),str(n)+' × '+str(n),'') for n in (512,1024,2048,4096)],default='2048',update=output_changed,options=SKIP)
    output: StringProperty(name='Output file stem',subtype='FILE_PATH',default='//face_sdf',update=output_changed,options=SKIP)
    point_xy: FloatVectorProperty(name='Point',size=2,min=-100,max=100,precision=4,step=.1,update=point_changed,options=SKIP)
    handle_left: FloatVectorProperty(name='Incoming handle',size=2,precision=4,step=.1,update=handles_changed,options=SKIP)
    handle_right: FloatVectorProperty(name='Outgoing handle',size=2,precision=4,step=.1,update=handles_changed,options=SKIP)
    handle_mode: EnumProperty(name='Handles',items=[('AUTO','Smooth','Automatic tangent and handle lengths'),('CORNER','Corner','Sharp point'),('FREE','Free','Adjust handles independently')],update=mode_changed,options=SKIP)
    rotation: FloatProperty(name='Light rotation (degrees)',min=0,max=360,default=0,precision=1,update=rotation_changed,options=SKIP)
    flat: BoolProperty(name='Flat lit/unlit view',update=flat_changed,options=SKIP)
    layer_operation: EnumProperty(name='Area',items=[('ADD','Shadow area','Darken the area inside this curve'),('REMOVE','Lit area','Light the area inside this curve and carry its cutout into earlier keyframes in this sweep')],update=operation_changed,options=SKIP)
    status: StringProperty(options=SKIP)


def report_error(operator,context,exc):
    message=str(exc)
    context.window_manager.anime_sdf_gen.status=message
    if session.ACTIVE:session.ACTIVE.notify_error(exc)
    # An active popup owns its warning footer. Before it opens, use Blender's
    # warning report; ERROR reports would raise through bpy.ops.
    else:operator.report({'WARNING'},message)
    if not isinstance(exc,ValueError):traceback.print_exc()
    return {'CANCELLED'}


class ANIME_SDF_GEN_OT_create(bpy.types.Operator):
    bl_idname='anime_sdf_gen.create'
    bl_label='Create'
    bl_description='Validate the face and open an isolated curve-authoring preview'

    def execute(self,context):
        p=context.window_manager.anime_sdf_gen
        try:
            if session.ACTIVE:
                session.ACTIVE.redraw()
                self.report({'INFO'},'Anime SDF Gen is already open in its editor window.')
                return {'FINISHED'}
            obj=context.view_layer.objects.active
            f=source.capture(obj,p.source_method,p.vertex_group)
            p.uv_map=f.reference['uv_map']
            project=model.new_project(f.reference,f.alignment,p.keyframes,p.mirror_sweeps,p.preset,int(p.resolution),bpy.path.abspath(p.output))
            project['authoring']['stage']='ORIENT'
            session.start(context,project,f)
            p.status=''
            return {'FINISHED'}
        except Exception as exc:return report_error(self,context,exc)


class ANIME_SDF_GEN_OT_keyframe(bpy.types.Operator):
    bl_idname='anime_sdf_gen.keyframe'
    bl_label='Select Shadow Keyframe'
    direction: StringProperty(default=model.LTR)
    index: IntProperty(default=0)
    def execute(self,context):
        try:
            if session.ACTIVE:session.ACTIVE.select_keyframe(self.direction,self.index)
            return {'FINISHED'}
        except Exception as exc:return report_error(self,context,exc)


class ANIME_SDF_GEN_OT_layer(bpy.types.Operator):
    bl_idname='anime_sdf_gen.layer'
    bl_label='Select Shape'
    index: IntProperty(default=0)
    def execute(self,context):
        s=session.ACTIVE
        if s:
            s.contour=max(0,min(self.index,len(s.keyframe['contours'])-1))
            s.point=0;s.reset_selection(whole_curve=True);s.sync_ui();s.redraw()
        return {'FINISHED'}


class ANIME_SDF_GEN_OT_action(bpy.types.Operator):
    bl_idname='anime_sdf_gen.action'
    bl_label='Edit Shadow Shapes'
    action: StringProperty()

    def execute(self,context):
        s=session.ACTIVE
        if not s or s.busy:return {'CANCELLED'}
        before=s.checkpoint()
        try:
            action=self.action
            if action=='NEXT':
                action={'ORIENT':'SET_FRONT','FIT':'FIT','EDIT':'CONFIRM'}.get(s.stage,'')
            if action=='CONFIRM':s.confirm();return {'FINISHED'}
            if action in ('KEYFRAMES_MORE','KEYFRAMES_LESS'):
                s.push_history()
                count=s.project['authoring']['keyframe_count']+(1 if action=='KEYFRAMES_MORE' else -1)
                s.project['authoring']['keyframe_count']=max(2,min(33,count))
                s.draft_due=.1;s.sync_ui();s.redraw();return {'FINISHED'}
            if action=='UNDO':
                s.restore_project(s.history.undo(s.project));return {'FINISHED'}
            if action=='REDO':
                s.restore_project(s.history.redo(s.project));return {'FINISHED'}
            if action=='PLAY':
                s.playing=not s.playing;s.orbit_preview=True;s.redraw();return {'FINISHED'}
            if action=='FRAME':s.frame_view();return {'FINISHED'}
            if action=='SET_FRONT':s.set_front();return {'FINISHED'}
            if action=='FIT':
                s.project['preset']=context.window_manager.anime_sdf_gen.preset
                s.fit(context.window_manager.anime_sdf_gen.keyframes);return {'FINISHED'}
            if action in ('FOCUS_AUTHOR','FOCUS_PREVIEW'):
                if s.editor:s.editor.maximize(action.removeprefix('FOCUS_'))
                return {'FINISHED'}
            if action=='BACK':
                if s.stage=='ORIENT':return {'CANCELLED'}
                if s.stage=='CONFIRM':
                    s.project['authoring']['stage']='EDIT';s.activate_stage();return {'FINISHED'}
                s.push_history();s.project['authoring']['stage']='FIT' if s.stage=='EDIT' else 'ORIENT'
                if s.stage=='FIT':s.seed_landmarks()
                s.playing=s.orbit_preview=False;s.changed();return {'FINISHED'}
            s.push_history()
            if action=='TRIANGLE':
                curve=model.triangle()
                names={c['name'] for c in s.keyframe['contours']};number=2
                while curve['name'] in names:curve['name']=f'Triangle {number}';number+=1
                s.keyframe['contours'].append(curve)
                s.contour=len(s.keyframe['contours'])-1;s.point=0
            elif action=='DUPLICATE':
                if not s.curve['closed']:raise ValueError('Only closed shapes can be duplicated.')
                c=deepcopy(s.curve);c['id']=model.uid();c['name']+=' copy'
                model.transform_contour(c,dx=.025,dy=.025)
                s.keyframe['contours'].insert(s.contour+1,c);s.contour+=1
            elif action=='DELETE_SHAPE':
                if not s.curve['closed']:raise ValueError('The main boundary cannot be deleted.')
                del s.keyframe['contours'][s.contour];s.contour=max(0,s.contour-1)
            elif action=='TOGGLE':s.curve['enabled']=not s.curve.get('enabled',True)
            elif action in ('UP','DOWN'):
                target=s.contour+(-1 if action=='UP' else 1)
                if s.contour==0 or not 1<=target<len(s.keyframe['contours']):raise ValueError('The main boundary stays first.')
                cs=s.keyframe['contours'];cs[s.contour],cs[target]=cs[target],cs[s.contour];s.contour=target
            elif action=='INSERT_POINT':
                segment=min(s.point,len(s.curve['points'])-(1 if s.curve['closed'] else 2))
                s.point=curves.insert_point(s.curve,segment)
            elif action=='DELETE_POINT':
                if len(s.curve['points'])<=(3 if s.curve['closed'] else 2):raise ValueError('This contour needs its remaining points.')
                if not s.curve['closed'] and s.point in (0,len(s.curve['points'])-1):raise ValueError('Keep the main boundary endpoints; move them instead.')
                del s.curve['points'][s.point];s.point=max(0,s.point-1)
            elif action=='ADD_KEYFRAME':s.key_index=model.insert_keyframe(s.project,s.direction,s.key_index)
            elif action=='REMOVE_KEYFRAME':s.key_index=model.remove_keyframe(s.project,s.direction,s.key_index)
            elif action=='COPY_KEYFRAME':model.copy_previous(s.project,s.direction,s.key_index)
            elif action=='MIRROR':
                s.project['mirror_sweeps']=not s.project['mirror_sweeps']
            else:raise ValueError('Unknown authoring action.')
            if action in ('TRIANGLE','DUPLICATE','UP','DOWN'):s.reset_selection(whole_curve=True)
            elif action in ('DELETE_SHAPE','INSERT_POINT','DELETE_POINT','ADD_KEYFRAME','REMOVE_KEYFRAME','COPY_KEYFRAME'):s.reset_selection()
            s.changed()
            return {'FINISHED'}
        except Exception as exc:
            s.rollback(before)
            return report_error(self,context,exc)


class ANIME_SDF_GEN_OT_transform(bpy.types.Operator):
    bl_idname='anime_sdf_gen.transform'
    bl_label='Transform Closed Shape'
    dx: FloatProperty(name='Move X',precision=3)
    dy: FloatProperty(name='Move Y',precision=3)
    angle: FloatProperty(name='Rotate (degrees)')
    scale: FloatProperty(name='Scale',default=1,min=.01,max=10)
    def invoke(self,context,event):
        self.dx=self.dy=self.angle=0;self.scale=1
        return context.window_manager.invoke_props_dialog(self)
    def execute(self,context):
        s=session.ACTIVE
        if not s:return {'CANCELLED'}
        try:
            if not s.curve['closed']:raise ValueError('Select a closed nose/chin shape first.')
            s.push_history();model.transform_contour(s.curve,self.dx,self.dy,self.angle,self.scale);s.changed()
            return {'FINISHED'}
        except Exception as exc:return report_error(self,context,exc)


class ANIME_SDF_GEN_OT_settings(bpy.types.Operator):
    bl_idname='anime_sdf_gen.settings'
    bl_label='Anime SDF Gen Settings'
    bl_description='Edit the selected output, source, keyframe or point settings'
    section: StringProperty(default='RESOLUTION',options={'HIDDEN'})
    filename: StringProperty(name='File name',description='Base name shared by the PNG and editable project')
    resolution: EnumProperty(name='Resolution',items=[(str(n),f'{n} × {n}','') for n in (512,1024,2048,4096)])
    uv_map: StringProperty(name='Output UV map')
    front_only: BoolProperty(name='Frontal surface only',default=True)
    keyframes: IntProperty(name='Shadow keyframes',description='Number of keyframes in each complete boundary sweep',min=2,max=33,default=9)
    point_xy: FloatVectorProperty(name='Point (head space)',size=2,min=-100,max=100,precision=4)
    handle_mode: EnumProperty(name='Handles',items=[('AUTO','Smooth',''),('CORNER','Corner',''),('FREE','Free','')])
    handle_left: FloatVectorProperty(name='Incoming offset',size=2,precision=4)
    handle_right: FloatVectorProperty(name='Outgoing offset',size=2,precision=4)

    @classmethod
    def poll(cls,context):
        return session.ACTIVE is not None and not session.ACTIVE.busy

    def invoke(self,context,event):
        s=session.ACTIVE;p=context.window_manager.anime_sdf_gen
        self.owner=s.registry.id
        for name in ('resolution','uv_map','front_only','keyframes','point_xy','handle_mode','handle_left','handle_right'):
            setattr(self,name,getattr(p,name))
        self.filename=Path(bpy.path.abspath(p.output)).name
        self.point_target=(s.direction,s.key_index,s.contour,s.point)
        return context.window_manager.invoke_props_dialog(self,width=390)

    def draw(self,context):
        layout=self.layout;s=session.ACTIVE
        if not s:return
        if self.section=='RESOLUTION':layout.prop(self,'resolution')
        elif self.section=='FILENAME':layout.prop(self,'filename')
        elif self.section=='SOURCE':
            layout.label(text='Source: '+s.project['source']['object'],icon='MESH_DATA')
            layout.label(text='Faces: '+str(len(s.project['source']['faces'])))
            obj=bpy.data.objects.get(s.project['source']['object'])
            row=layout.column();row.enabled=s.stage=='ORIENT'
            if obj:row.prop_search(self,'uv_map',obj.data,'uv_layers')
            row.prop(self,'front_only')
            if s.stage!='ORIENT':layout.label(text='Change orientation to choose a different UV map.')
        elif self.section=='KEYFRAME_COUNT':
            layout.prop(self,'keyframes')
        elif self.section=='POINT':
            layout.prop(self,'point_xy');layout.prop(self,'handle_mode')
            if self.handle_mode=='FREE':layout.prop(self,'handle_left');layout.prop(self,'handle_right')

    def execute(self,context):
        s=session.ACTIVE
        if not s or (hasattr(self,'owner') and self.owner!=s.registry.id):return {'CANCELLED'}
        p=context.window_manager.anime_sdf_gen
        if self.section=='RESOLUTION':
            s.project['settings']['resolution']=int(self.resolution)
        elif self.section=='FILENAME':
            name=self.filename.strip()
            if name.lower().endswith('.png'):name=name[:-4]
            if not name or name in ('.','..') or name.endswith('.') or any(c in name for c in '<>:"/\\|?*'):
                return report_error(self,context,ValueError('Choose a file name without path separators or reserved characters.'))
            s.project['settings']['output']=str(Path(bpy.path.abspath(s.project['settings']['output'])).parent/name)
        elif self.section=='SOURCE' and s.stage=='ORIENT':
            s.project['authoring'].update(uv_map=self.uv_map,front_only=self.front_only)
        elif self.section=='KEYFRAME_COUNT':
            s.push_history()
            count=self.keyframes
            s.project['authoring']['keyframe_count']=min(33,count)
        elif self.section=='POINT':
            if hasattr(self,'point_target') and self.point_target!=(s.direction,s.key_index,s.contour,s.point):return {'CANCELLED'}
            s.push_history();pt=s.curve['points'][s.point]
            if self.handle_mode=='FREE' and pt['mode']!='FREE':
                left,right=curves.handles(s.curve,s.point)
                pt.update(left=(left-pt['co']).tolist(),right=(right-pt['co']).tolist())
            else:pt.update(left=list(self.handle_left),right=list(self.handle_right))
            pt.update(co=list(self.point_xy),mode=self.handle_mode)
            s.changed();return {'FINISHED'}
        s.draft_due=.1;s.sync_ui();s.redraw()
        return {'FINISHED'}


class ANIME_SDF_GEN_OT_packing(bpy.types.Operator):
    bl_idname='anime_sdf_gen.packing'
    bl_label='Texture Map Output'
    bl_description='Choose an RGB channel or an individual grayscale texture'
    map_name: StringProperty(options={'HIDDEN'})
    route: EnumProperty(items=[(r,'Separate' if r=='SEPARATE' else r,'') for r in model.OUTPUT_ROUTES])

    @classmethod
    def poll(cls,context):
        s=session.ACTIVE
        return s is not None and s.stage=='CONFIRM' and not s.busy

    def execute(self,context):
        s=session.ACTIVE
        try:
            model.set_packing(s.project,self.map_name,self.route)
            s.draft_due=.1;s.redraw()
            return {'FINISHED'}
        except Exception as exc:return report_error(self,context,exc)


class ANIME_SDF_GEN_OT_destination(bpy.types.Operator,ExportHelper):
    bl_idname='anime_sdf_gen.destination'
    bl_label='Choose Output Location'
    bl_description='Choose the destination and file name; files are written only by Generate & Finish'
    filename_ext='.png'
    filter_glob: StringProperty(default='*.png',options={'HIDDEN'})
    check_existing: BoolProperty(default=False,options={'HIDDEN'})

    @classmethod
    def poll(cls,context):
        s=session.ACTIVE
        return s is not None and s.stage=='CONFIRM' and not s.busy

    def invoke(self,context,event):
        s=session.ACTIVE;self.owner=s.registry.id
        self.filepath=bpy.path.abspath(s.project['settings']['output'])+'.png'
        return ExportHelper.invoke(self,context,event)

    def execute(self,context):
        s=session.ACTIVE
        if not s or s.busy or s.stage!='CONFIRM' or (hasattr(self,'owner') and self.owner!=s.registry.id):return {'CANCELLED'}
        path=bpy.path.abspath(self.filepath)
        if not path.strip():return report_error(self,context,ValueError('Choose a save location.'))
        if path.lower().endswith('.png'):path=path[:-4]
        s.project['settings']['output']=path
        s.draft_due=.1;s.sync_ui();s.redraw()
        return {'FINISHED'}


class ANIME_SDF_GEN_OT_landmark(bpy.types.Operator):
    bl_idname='anime_sdf_gen.landmark'
    bl_label='Select Fitting Landmark'
    name: StringProperty(default='nose')
    def execute(self,context):
        if session.ACTIVE:
            session.ACTIVE.landmark=self.name;session.ACTIVE.sync_ui();session.ACTIVE.redraw()
        return {'FINISHED'}


class ANIME_SDF_GEN_OT_generate(bpy.types.Operator):
    bl_idname='anime_sdf_gen.generate'
    bl_label='Generate & Finish'
    bl_description='Verify and export the textures and editable project, then restore your workspace'
    def invoke(self,context,event):
        s=session.ACTIVE
        if s:
            base=bpy.path.abspath(s.project['settings']['output'])
            try:
                existing=any(path.exists() for path in output_paths(s.project,base))
            except Exception as exc:return report_error(self,context,exc)
            if existing:
                return context.window_manager.invoke_confirm(self,event,title='Replace existing SDF output?',message='Existing files in this output set will be replaced together after verification.',confirm_text='Replace & Generate')
        return self.execute(context)
    def execute(self,context):
        try:
            if session.ACTIVE:session.ACTIVE.start_export()
            return {'FINISHED'}
        except Exception as exc:return report_error(self,context,exc)


class ANIME_SDF_GEN_OT_cancel_generation(bpy.types.Operator):
    bl_idname='anime_sdf_gen.cancel_generation'
    bl_label='Cancel Generation'
    def execute(self,context):
        if session.ACTIVE:session.ACTIVE.cancel_export()
        return {'FINISHED'}


class ANIME_SDF_GEN_OT_close(bpy.types.Operator):
    bl_idname='anime_sdf_gen.close'
    bl_label='Discard & Close'
    def execute(self,context):
        if session.ACTIVE and session.ACTIVE.editor:session.ACTIVE.close_requested=True
        else:session.end_session(remove_draft=True)
        return {'FINISHED'}


class ANIME_SDF_GEN_OT_save_draft(bpy.types.Operator,ExportHelper):
    bl_idname='anime_sdf_gen.save_draft'
    bl_label='Save Draft & Close'
    filename_ext='.sdfproject.json'
    filter_glob: StringProperty(default='*.sdfproject.json',options={'HIDDEN'})
    def invoke(self,context,event):
        if session.ACTIVE:self.filepath=bpy.path.abspath(session.ACTIVE.project['settings']['output'])+'.draft.sdfproject.json'
        return ExportHelper.invoke(self,context,event)
    def execute(self,context):
        try:
            if session.ACTIVE:
                atomic_text(self.filepath,model.dumps(session.ACTIVE.project))
                try:
                    automatic=session.draft_root()/(session.ACTIVE.project['id']+'.sdfproject.json')
                    remove_draft=Path(self.filepath).resolve()!=automatic.resolve()
                except OSError:
                    remove_draft=True
                if session.ACTIVE.editor:session.ACTIVE.close_requested=remove_draft
                else:session.end_session(remove_draft=remove_draft)
            self.report({'INFO'},'Draft saved; original workspace restored.')
            return {'FINISHED'}
        except Exception as exc:return report_error(self,context,exc)


class ANIME_SDF_GEN_OT_open(bpy.types.Operator,ImportHelper):
    bl_idname='anime_sdf_gen.open_project'
    bl_label='Edit Existing SDF'
    bl_description='Open an editable SDF project and validate its source model'
    filename_ext='.sdfproject.json'
    filter_glob: StringProperty(default='*.sdfproject.json',options={'HIDDEN'})
    relink: BoolProperty(name='Relink to Active Source',description='Capture the active mesh selection or chosen vertex group, then orient and fit again')
    def execute(self,context):
        try:
            p=load_project(self.filepath)
            props=context.window_manager.anime_sdf_gen
            if self.relink:
                obj=context.view_layer.objects.active
                f=source.capture(obj,props.source_method,props.vertex_group)
                p['source'],p['alignment']=f.reference,f.alignment
                p['authoring'].update(stage='ORIENT',anchors={},uv_map=f.reference['uv_map'])
            else:
                f=source.from_reference(p['source'],p['alignment'],validate=p['authoring']['stage']!='ORIENT')
            props.output=p['settings']['output'];props.resolution=str(p['settings']['resolution'])
            props.uv_map=p['source']['uv_map'];props.front_only=p['source'].get('front_only',True)
            session.start(context,p,f)
            return {'FINISHED'}
        except Exception as exc:return report_error(self,context,exc)


class ANIME_SDF_GEN_OT_recover(bpy.types.Operator):
    bl_idname='anime_sdf_gen.recover'
    bl_label='Recover Latest Draft'
    bl_description='Reopen the most recent automatic recovery draft'
    def execute(self,context):
        try:
            drafts=sorted(session.draft_root().glob('*.sdfproject.json'),key=lambda p:p.stat().st_mtime,reverse=True)
            if not drafts:raise ValueError('No recovery drafts are available.')
            return bpy.ops.anime_sdf_gen.open_project(filepath=str(drafts[0]))
        except Exception as exc:return report_error(self,context,exc)


def action(layout,text,code,icon='NONE'):
    op=layout.operator('anime_sdf_gen.action',text=text,icon=icon);op.action=code
    return op


def wrapped(layout,text,width=44,icon=None):
    import textwrap
    for index,line in enumerate(textwrap.wrap(text,width=width) or ['']):
        if index==0 and icon:layout.label(text=line,icon=icon)
        else:layout.label(text=line)


class ANIME_SDF_GEN_PT_launcher(bpy.types.Panel):
    bl_label='Anime SDF Gen'
    bl_idname='ANIME_SDF_GEN_PT_launcher'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='Anime SDF Gen'

    @classmethod
    def poll(cls,context):
        s=session.ACTIVE
        return not s or not s.editor or context.window!=s.editor.window

    def draw(self,context):
        layout=self.layout;p=context.window_manager.anime_sdf_gen;s=session.ACTIVE
        if s:
            wrapped(layout,'Your authoring session is in the Anime SDF Gen popup.',icon='WINDOW')
            return
        obj=context.view_layer.objects.active
        layout.label(text='Active: '+obj.name if obj and obj.type=='MESH' else 'Make a mesh active.',icon='MESH_DATA')
        layout.prop(p,'source_method')
        if p.source_method=='VERTEX_GROUP' and obj and obj.type=='MESH':
            layout.prop_search(p,'vertex_group',obj,'vertex_groups')
        else:
            wrapped(layout,'Select facial geometry in Edit Mode, then Create.')
        layout.prop(p,'keyframes')
        row=layout.row();row.scale_y=1.5;row.operator('anime_sdf_gen.create',icon='CURVE_BEZCURVE')
        layout.operator('anime_sdf_gen.open_project',icon='FILE_FOLDER')
        layout.operator('anime_sdf_gen.recover',icon='RECOVER_LAST')
        if p.status:wrapped(layout,p.status,icon='ERROR')


CLASSES=(ANIME_SDF_GEN_Properties,ANIME_SDF_GEN_OT_create,ANIME_SDF_GEN_OT_keyframe,ANIME_SDF_GEN_OT_layer,ANIME_SDF_GEN_OT_action,ANIME_SDF_GEN_OT_transform,
         ANIME_SDF_GEN_OT_settings,ANIME_SDF_GEN_OT_packing,ANIME_SDF_GEN_OT_destination,ANIME_SDF_GEN_OT_landmark,ANIME_SDF_GEN_OT_generate,ANIME_SDF_GEN_OT_cancel_generation,ANIME_SDF_GEN_OT_close,ANIME_SDF_GEN_OT_save_draft,
         ANIME_SDF_GEN_OT_open,ANIME_SDF_GEN_OT_recover,ANIME_SDF_GEN_OT_interact,ANIME_SDF_GEN_PT_launcher)


def register():
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.WindowManager.anime_sdf_gen=PointerProperty(type=ANIME_SDF_GEN_Properties,options=SKIP)
    session.register_handlers()


def unregister():
    session.unregister_handlers()
    if hasattr(bpy.types.WindowManager,'anime_sdf_gen'):del bpy.types.WindowManager.anime_sdf_gen
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)
