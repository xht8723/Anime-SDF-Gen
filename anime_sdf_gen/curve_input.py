"""Blender key bindings applied to session-owned points on the fixed face plane."""
import time
import bpy
import numpy as np
from .core import model,editing

TRANSFORMS={'transform.translate':'MOVE','transform.rotate':'ROTATE','transform.resize':'SCALE'}
MODES={'TRANSLATE':'MOVE','ROTATE':'ROTATE','RESIZE':'SCALE'}
DIGITS=dict(zip(('ZERO','ONE','TWO','THREE','FOUR','FIVE','SIX','SEVEN','EIGHT','NINE'),'0123456789'))
DIGITS.update({f'NUMPAD_{i}':str(i) for i in range(10)})


def binding(event, names):
    configs=bpy.context.window_manager.keyconfigs;config=configs.user or configs.active
    for name in names:
        keymap=config.keymaps.get(name) if config else None
        # RNA match_event polls the original operator against Blender's mode
        # and skips modal propvalue entries. Our curves are session data, so
        # resolve configured events without requiring a native Edit Mode object.
        item=next((i for i in keymap.keymap_items if i.active and i.type==event.type
            and i.value in ('ANY',event.value) and i.key_modifier=='NONE'
            and (i.any or all(getattr(i,key)==-1 or bool(getattr(i,key))==bool(getattr(event,key,False))
                             for key in ('shift','ctrl','alt','oskey')))),None) if keymap else None
        if item and item.active:return item
    return None


def selection_button():
    config=bpy.context.window_manager.keyconfigs.active
    return 'RIGHTMOUSE' if config and getattr(config.preferences,'select_mouse','LEFT')=='RIGHT' else 'LEFTMOUSE'


class CurveInput:
    def __init__(self,session):
        self.s=session;self.state=None;self.before=None;self.transform=None
        self.mouse=np.zeros(2);self.last_draw=0.;self.snap=self.precise=False
        self.box_start=None;self.box_mode='SET';self.box_selected=set()

    @property
    def active(self):return self.state is not None

    def show_keyframe(self):
        s=self.s
        if s.playing or s.orbit_preview:
            s.playing=s.orbit_preview=False
            s.rotation=model.keyframe_rotation(s.direction,s.keyframe['progress'])
            s.render_mask();s.sync_ui()

    def choose(self, selection):
        s=self.s;s.selected=set(selection)&editing.available(s.keyframe);s.handle='co'
        if s.selected and (s.contour,s.point) not in s.selected:s.contour,s.point=sorted(s.selected)[-1]
        s.sync_ui();s.redraw()

    def begin(self, kind, mouse, region, view, direct=False):
        from .drawing import from_view
        s=self.s;xy=from_view(s,mouse,region,view)
        if xy is None:return
        self.show_keyframe()
        self.transform=editing.Transform(s.keyframe,s.selected,kind,xy,
            s.project['alignment']['height']/s.project['alignment']['width'],s.handle)
        self.before=s.checkpoint();s.push_history()
        self.state='DIRECT' if direct else 'TRANSFORM'
        self.snap=self.precise=False;self.last_draw=0.;s.dragging=True;s.redraw()

    def apply(self, final=False):
        s=self.s
        try:frame=self.transform.evaluate(self.snap,self.precise)
        except ValueError as exc:s.notify_error(exc);return False
        if frame!=s.keyframe:
            model.sweep(s.project,s.direction)[s.key_index]=frame
            now=time.perf_counter()
            if final or now-self.last_draw>=1/60:
                s.changed(dragging=True);self.last_draw=now
        s.redraw();return True

    def finish(self):
        if not self.apply(final=True):return
        s=self.s;before=self.before
        self.state=self.before=self.transform=None;s.dragging=False
        if s.project==before['project']:
            s.history.undo_stack,s.history.redo_stack=before['undo'],before['redo']
            s.redraw()
        else:s.changed()

    def cancel(self):
        if not self.active:return
        s=self.s;before=self.before;boxed=self.state in ('BOX','BOX_WAIT')
        self.state=self.before=self.transform=None;self.box_start=None;s.dragging=False
        if boxed:self.choose(self.box_selected)
        elif before:s.rollback(before)
        s.redraw()

    def start_box(self, mouse, wait=False, mode='SET'):
        self.show_keyframe();self.state='BOX_WAIT' if wait else 'BOX'
        self.box_start=None if wait else np.asarray(mouse).copy();self.mouse=np.asarray(mouse).copy()
        self.box_mode=mode;self.box_selected=self.s.selected.copy();self.s.redraw()
        self.box_button=None

    def boxed(self, operation,region,view):
        from .drawing import to_view
        s=self.s
        projected={key:to_view(s,s.keyframe['contours'][key[0]]['points'][key[1]]['co'],region,view) for key in editing.available(s.keyframe)}
        projected={key:xy for key,xy in projected.items() if xy is not None and 0<=xy[0]<region.width and 0<=xy[1]<region.height}
        hits=editing.box_selection(projected,self.box_start,self.mouse)
        self.choose(editing.combine_selection(self.box_selected,hits,operation))

    def modal(self,event,mouse,region,view):
        from .drawing import from_view,pick
        s=self.s;self.mouse=np.asarray(mouse).copy()
        if self.active and event.ctrl and event.type in ('S','Z') and event.value=='PRESS':
            self.cancel()
            if event.type=='S':s.save_requested=True
            return True
        if self.state in ('BOX_WAIT','BOX'):
            item=binding(event,('Gesture Box',));action=item.propvalue if item else None
            if action=='CANCEL':self.cancel();return True
            if self.state=='BOX_WAIT':
                if action=='BEGIN':
                    self.state='BOX';self.box_start=self.mouse.copy();self.box_button=event.type
                    if event.shift or event.ctrl or event.type=='MIDDLEMOUSE':self.box_mode='SUB'
                s.redraw();return True
            operation='SUB' if event.ctrl or (getattr(self,'box_button','')=='MIDDLEMOUSE') else self.box_mode
            if event.type=='MOUSEMOVE':self.boxed(operation,region,view)
            elif event.value=='RELEASE' and event.type in ('LEFTMOUSE','MIDDLEMOUSE','RIGHTMOUSE'):
                if action=='DESELECT':operation='SUB'
                self.boxed(operation,region,view);self.state=None;self.box_start=None
            s.redraw();return True
        if self.state in ('DIRECT','TRANSFORM'):
            item=binding(event,('Transform Modal Map',));action=item.propvalue if item else None
            if action=='CANCEL':self.cancel();return True
            if self.state=='TRANSFORM' and action=='CONFIRM':self.finish();return True
            if self.state=='DIRECT' and event.type==self.drag_button and event.value=='RELEASE':
                xy=from_view(s,mouse,region,view)
                if xy is not None:self.transform.move(xy,self.precise)
                self.finish();return True
            if action=='PRECISION':self.precise=event.value!='RELEASE'
            elif action=='SNAP_INV_ON':self.snap=True
            elif action=='SNAP_INV_OFF':self.snap=False
            elif action and (action.startswith('AXIS_') or action.startswith('PLANE_')):
                axis=action[-1]
                if action.startswith('PLANE_'):axis={'X':'Y','Y':'X','Z':None}[axis]
                self.transform.axis=None if self.transform.axis==axis else axis
            elif self.state=='TRANSFORM' and action in MODES:
                xy=from_view(s,mouse,region,view)
                self.transform=editing.Transform(self.transform.original,s.selected,MODES[action],xy,
                    s.project['alignment']['height']/s.project['alignment']['width'],s.handle)
            elif event.type=='MOUSEMOVE':
                xy=from_view(s,mouse,region,view)
                if xy is not None:self.transform.move(xy,self.precise or event.shift)
            elif self.state=='TRANSFORM' and event.value=='PRESS':
                character=DIGITS.get(event.type,{'PERIOD':'.','NUMPAD_PERIOD':'.','MINUS':'-','NUMPAD_MINUS':'-','BACK_SPACE':'BACK_SPACE'}.get(event.type))
                if character:self.transform.numeric(character)
            self.apply();return True

        item=binding(event,('Curve','3D View'))
        if item and item.idname in TRANSFORMS and event.value=='PRESS':
            self.begin(TRANSFORMS[item.idname],mouse,region,view)
            self.snap,self.precise=event.ctrl,event.shift;return True
        if item and item.idname=='curve.select_all':
            self.show_keyframe();all_points=editing.available(s.keyframe);action=item.properties.action
            self.choose(set() if action=='DESELECT' or (action=='TOGGLE' and s.selected) else all_points-s.selected if action=='INVERT' else all_points)
            return True
        if item and item.idname=='view3d.select_box':
            self.start_box(mouse,wait=True,mode=item.properties.mode);return True
        button=selection_button()
        if event.type==button and event.value=='DOUBLE_CLICK':
            hit=pick(s,mouse,region,view)
            if hit:
                s.handle,s.contour,s.point=hit;s.selected={(s.contour,s.point)};s.sync_ui()
                bpy.ops.anime_sdf_gen.settings('INVOKE_DEFAULT',section='POINT')
            return True
        if event.type!=button or event.value!='PRESS':return False
        self.show_keyframe();hit=pick(s,mouse,region,view)
        if not hit:
            self.start_box(mouse,mode='SUB' if event.ctrl else 'ADD' if event.shift else 'SET')
            self.box_button=button;return True
        handle,ci,pi=hit;key=(ci,pi)
        if event.shift and handle=='co':
            self.choose(s.selected^{key})
            if key in s.selected:s.contour,s.point=ci,pi
            s.sync_ui();return True
        if key not in s.selected or handle!='co':s.selected={key}
        s.handle,s.contour,s.point=handle,ci,pi;s.sync_ui()
        self.drag_button=button;self.begin('MOVE',mouse,region,view,direct=True)
        self.snap,self.precise=event.ctrl,event.shift
        return True

    def draw(self,region,view):
        from .drawing import rect,lines,label,to_view
        from .editor import scale
        if not self.active:return
        u=scale()
        if self.state in ('BOX','BOX_WAIT'):
            if self.box_start is None:
                x,y=self.mouse;lines([(x-14*u,y),(x+14*u,y)],(.48,.8,.9,1));lines([(x,y-14*u),(x,y+14*u)],(.48,.8,.9,1))
            else:
                lo,hi=np.minimum(self.box_start,self.mouse),np.maximum(self.box_start,self.mouse)
                rect(*lo,*(hi-lo),(.2,.6,.85,.12))
                lines([lo,(hi[0],lo[1]),hi,(lo[0],hi[1]),lo],(.48,.8,.95,1))
        elif self.transform:
            q=to_view(self.s,self.transform.pivot,region,view)
            if q is not None:
                lines([(q.x-5*u,q.y),(q.x+5*u,q.y)],(.9,.9,.9,.8))
                lines([(q.x,q.y-5*u),(q.x,q.y+5*u)],(.9,.9,.9,.8))
            caption=self.transform.caption(self.snap,self.precise)
            if self.transform.axis=='Z' and self.transform.kind!='ROTATE':caption+=' · Fixed face plane'
            rect(12*u,10*u,max(200*u,min(region.width-24*u,len(caption)*8*u)),29*u,(.055,.065,.083,.94))
            label(caption,22*u,19*u,12)
