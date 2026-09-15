"""An isolated floating window with hidden Blender chrome and virtual views."""
from copy import deepcopy
from dataclasses import dataclass
import time
import bpy
from mathutils import Matrix, Quaternion, Vector


def scale():
    return max(1., bpy.context.preferences.system.ui_scale)


def window_region(area):
    return next((r for r in area.regions if r.type == 'WINDOW'), None)


@dataclass
class Rect:
    x: int = 0
    y: int = 0
    width: int = 1
    height: int = 1

    @property
    def box(self):
        return self.x, self.y, self.width, self.height

    def contains(self, xy):
        return self.x <= xy[0] < self.x+self.width and self.y <= xy[1] < self.y+self.height


class View:
    """One popup camera, projected and navigated by Blender's RegionView3D."""
    def __init__(self,editor):
        self.editor=editor
        self.region = Rect()
        self.view_location = Vector((0, 0, 0))
        self.view_rotation = Quaternion()
        self.view_distance = 1.
        self.view_perspective = 'ORTHO'
        self.view_matrix = Matrix.Identity(4)
        self.perspective_matrix = Matrix.Identity(4)
        self.projection_matrix = Matrix.Identity(4)
        self.frame_pending=False

    def update(self):
        if not self.editor.navigation.drawing:
            return
        self.editor.navigation.matrices(self)
        if self.frame_pending:
            a=self.editor.session.project['alignment']
            self.view_distance*=max(a['height']*self.projection_matrix[1][1],
                                    a['width']*self.projection_matrix[0][0])/1.66
            self.frame_pending=False
            self.editor.navigation.matrices(self)

    def project(self, world):
        clip = self.perspective_matrix @ Vector((*world, 1))
        if clip.w<=0:return None
        return Vector(((clip.x/clip.w+1)*self.region.width/2, (clip.y/clip.w+1)*self.region.height/2))

    def ray(self, mouse):
        inv = self.perspective_matrix.inverted()
        p = inv @ Vector((2*mouse[0]/self.region.width-1, 2*mouse[1]/self.region.height-1, -1, 1))
        q = inv @ Vector((2*mouse[0]/self.region.width-1,2*mouse[1]/self.region.height-1,1,1))
        origin=Vector(p[:3])/p.w
        return origin,(Vector(q[:3])/q.w-origin).normalized()


class Editor:
    def __init__(self, session, layout=None):
        self.session = session
        self.window = self.workspace = self.reference_space = None
        self.native_area = None
        from .navigation import NativeNavigation
        self.navigation=NativeNavigation(self)
        self.views = {'AUTHOR': View(self), 'PREVIEW': View(self)}
        self.boxes, self.widgets = {}, []
        self.ready = False
        self.phase = 'NEW'
        self.saved = deepcopy(layout or {})
        self.split_ratio = self.saved.get('split_ratio', .54)
        self.focus = self.saved.get('focus')
        self.panel_scroll = 0
        self._native_fullscreen = False
        self.buffers = {}
        self.reference_keys = {}
        self.geometry_revision = 0
        self.hover = None
        self.hover_pos=(0,0)
        self.hover_since=0.
        self.tooltip_ready=False
        self.tooltip_box=None
        self.warning_text=''
        self.warning_scroll=0
        self.warning_scroll_max=0
        self.warning_bounds=None
        from .widgets import Painter
        self.painter=Painter()
        self.layout_stage = session.stage

    def own_screen(self, screen):
        for kind, owned in self.session.registry.ids:
            if kind == 'screens':
                try:
                    if owned.as_pointer() == screen.as_pointer():return
                except ReferenceError:pass
        self.session.registry.own('screens', screen)

    def open(self):
        self.started = time.perf_counter()
        origin = self.session.state.window
        windows = set(bpy.context.window_manager.windows)
        # A main window owns its scene. Blender child windows synchronize their
        # scene/workspace with the parent and cannot isolate authoring data.
        self.workspace = self.session.registry.own('workspaces', origin.workspace.copy())
        self.workspace.name = 'Anime SDF Gen'
        for screen in self.workspace.screens:self.own_screen(screen)
        with bpy.context.temp_override(window=origin, screen=self.workspace.screens[0]):
            bpy.ops.wm.window_new_main()
        self.window = next(w for w in bpy.context.window_manager.windows if w not in windows)
        for screen in self.workspace.screens:self.own_screen(screen)
        self.window.scene = self.session.scene
        self.phase = 'OPEN'
        self.advance()

    @staticmethod
    def configure(area):
        area.type = 'VIEW_3D'
        space = area.spaces.active
        space.show_region_toolbar = space.show_region_tool_header = False
        space.show_region_header = space.show_region_ui = False
        space.overlay.show_overlays = False
        space.show_gizmo = False
        # Native frame-selected and orbit-around-selection need a visible face.
        # The popup composite covers this host view; its keymap blocks editing.
        space.show_object_viewport_mesh = True
        space.use_local_collections = False
        space.region_3d.use_clip_planes = False
        space.shading.type = 'SOLID'
        space.shading.light = 'STUDIO'
        space.shading.color_type = 'SINGLE'
        space.shading.single_color = (.65,.65,.65)
        space.shading.show_cavity = True
        space.shading.cavity_type = 'BOTH'
        space.shading.background_type = 'VIEWPORT'
        space.shading.background_color = (.055,.06,.075)
        return space

    def advance(self):
        if not self.alive():return
        if time.perf_counter()-self.started > 30:
            raise RuntimeError('The floating editor could not initialize.')
        w = self.window
        if self.phase in ('OPEN', 'SPLIT'):
            areas = list(w.screen.areas)
            if self.phase == 'SPLIT' and len(areas) < 2:return
            main = max(areas, key=lambda a:a.width*a.height)
            if len(areas) == 1:
                with bpy.context.temp_override(window=w, area=main):
                    bpy.ops.screen.area_split(direction='VERTICAL', factor=.5)
                self.phase = 'SPLIT'
                return
            # Retain one hidden SpaceView3D solely for native reference shading.
            other = next(a for a in areas if a != main)
            self.reference_space = self.configure(other)
            self.configure(main)
            before = set(bpy.data.screens)
            with bpy.context.temp_override(window=w, area=main):
                bpy.ops.screen.screen_full_area(use_hide_panels=True)
            self._native_fullscreen = True
            for screen in bpy.data.screens:
                if screen not in before:self.own_screen(screen)
            self.phase = 'CONFIGURE'
            return
        if self.phase == 'CONFIGURE':
            main = max(w.screen.areas, key=lambda a:a.width*a.height)
            self.configure(main)
            self.native_area = main
            extent=max(self.session.project['alignment'][k] for k in ('width','height'))
            main.spaces.active.clip_start=max(1e-6,extent*.001)
            main.spaces.active.clip_end=max(100,extent*100)
            self.ready, self.phase = True, 'READY'
            self.resize(window_region(main))
            self.frame()
            self.restore_views()
            self.refresh_appearance()
            self.session.state.area = main
            from . import drawing
            drawing.attach(self.session)
            with bpy.context.temp_override(window=w, area=main, region=window_region(main)):
                bpy.ops.anime_sdf_gen.interact('INVOKE_DEFAULT')

    def resize(self, region):
        if not region:return
        u = scale(); w, h = region.width, region.height
        setup=self.session.stage in ('ORIENT','FIT');confirm=self.session.stage=='CONFIRM'
        top = round(90*u); shelf = 0 if setup else round((100 if confirm else 158)*u); panel = round(min(330*u, w*.32))
        available = max(2, w-panel)
        bottom = min(shelf, h//3)
        body_h = max(1,h-top-bottom)
        self.boxes = {'TOP':Rect(0,h-top,w,top), 'SHELF':Rect(0,0,available,bottom),
                      'PANEL':Rect(available,0,panel,h-top),
                      'SLIDER':(130*u,34*u,max(1,available-152*u),22*u)}
        focus = 'AUTHOR' if setup else 'PREVIEW' if confirm else self.focus or ('AUTHOR' if available < 560*u else None)
        divider = max(1,round(3*u))
        split = int(available*self.split_ratio)
        if focus:
            bounds = {focus:Rect(0,bottom,available,body_h)}
        else:
            bounds = {'AUTHOR':Rect(0,bottom,split,body_h),
                      'PREVIEW':Rect(split+divider,bottom,available-split-divider,body_h)}
            self.boxes['DIVIDER'] = Rect(split,bottom,divider,body_h)
        for name,b in bounds.items():
            self.boxes[name] = b
            help_height=round(56*u)
            self.views[name].region = Rect(b.x,b.y,b.width,max(1,b.height-help_height))
            self.views[name].update()

    def alive(self):
        try:return self.window is not None and self.window in list(bpy.context.window_manager.windows)
        except ReferenceError:return False

    def owns_context(self, context):
        return self.alive() and context.window == self.window and context.area == self.native_area

    def redraw(self):
        if self.alive():
            for area in self.window.screen.areas:area.tag_redraw()

    def clear_hover(self):
        visible=self.hover is not None or self.tooltip_ready
        self.hover=None;self.tooltip_ready=False;self.tooltip_box=None;self.hover_since=0.
        if visible:self.redraw()

    def set_hover(self,key,position):
        changed=key!=self.hover
        moved=abs(position[0]-self.hover_pos[0])+abs(position[1]-self.hover_pos[1])>3*scale()
        self.hover_pos=tuple(position)
        if changed or (moved and not self.tooltip_ready):
            self.hover_since=time.perf_counter();self.tooltip_ready=False;self.tooltip_box=None
        self.hover=key
        if changed:self.redraw()

    def tick_tooltip(self,now):
        if self.hover and not self.tooltip_ready and now-self.hover_since>=.6:
            self.tooltip_ready=True;self.redraw()

    def frame(self, role=None):
        self.navigation.stop()
        a = self.session.project['alignment']
        rotation = Matrix((Vector(a['right']),Vector(a['up']),Vector(a['forward']))).transposed().to_quaternion()
        for name,v in self.views.items():
            if role and role != name:continue
            v.view_location = Vector(a['center'])
            v.view_rotation = rotation.copy()
            v.view_perspective='ORTHO'
            v.view_distance=max(a['height'],a['width'])
            # Fit from Blender's lens during the next real GPU draw. Its update
            # API must not run from app timers after a window context is closed.
            v.frame_pending=True
            v.update()
        self.redraw()

    def lock_author(self):
        if self.session.stage == 'EDIT':
            a = self.session.project['alignment'];v=self.views['AUTHOR']
            v.view_rotation = Matrix((Vector(a['right']),Vector(a['up']),Vector(a['forward']))).transposed().to_quaternion()
            v.view_perspective='ORTHO'
            v.update()

    def refresh_appearance(self):
        if not self.ready:return
        if self.layout_stage!=self.session.stage:
            self.clear_hover()
            self.navigation.stop();self.focus=None;self.panel_scroll=0
            self.layout_stage=self.session.stage
            self.resize(window_region(self.native_area))
            self.frame()
        space = self.reference_space
        space.shading.type = 'MATERIAL' if self.session.project['authoring']['reference']=='MATERIAL' else 'SOLID'
        if space.shading.type == 'MATERIAL':
            space.shading.use_scene_lights = space.shading.use_scene_world = False
        self.lock_author()
        self.redraw()

    def maximize(self, role):
        if self.session.stage!='EDIT':return
        self.navigation.stop()
        self.clear_hover()
        self.focus = None if self.focus == role else role
        self.resize(window_region(self.native_area))
        self.redraw()

    def snapshot(self):
        self.navigation.poll()
        return {'split_ratio':self.split_ratio, 'focus':self.focus, 'views':{
            name:{'location':list(v.view_location),'rotation':list(v.view_rotation),'distance':v.view_distance,'perspective':v.view_perspective}
            for name,v in self.views.items()}}

    def restore_views(self):
        for name,values in self.saved.get('views',{}).items():
            v = self.views[name]
            v.frame_pending=False
            v.view_location = Vector(values['location']);v.view_rotation=Quaternion(values['rotation'])
            v.view_distance = values['distance'];v.update()
            v.view_perspective=values['perspective'];v.update()

    def free_buffers(self):
        for buffer in self.buffers.values():
            try:buffer.free()
            except (ReferenceError,RuntimeError):pass  # GPU context may already be gone after native X.
        self.buffers.clear();self.reference_keys.clear()

    def close(self):
        self.clear_hover();self.painter.close()
        self.free_buffers()
        if self.alive():
            if len(bpy.context.window_manager.windows)>1:
                with bpy.context.temp_override(window=self.window):bpy.ops.wm.window_close()
            else:
                # Never quit Blender when this became the last remaining window.
                # Leave native full-content mode before synchronously rebinding.
                if self._native_fullscreen:
                    with bpy.context.temp_override(window=self.window,area=self.native_area):
                        bpy.ops.screen.screen_full_area(use_hide_panels=True)
                state=self.session.state
                with bpy.context.temp_override(window=self.window,screen=state.workspace.screens[0]):
                    self.window.scene=state.scene;self.window.view_layer=state.view_layer
                    self.session.registry.dispose()
        self.window=None;self.ready=False;self.native_area=None;self.reference_space=None
