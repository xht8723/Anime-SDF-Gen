"""Preview ownership, reversible window state, background jobs, and recovery."""
from copy import deepcopy
from pathlib import Path
import time
import traceback
import uuid
import bpy
import numpy as np
from mathutils import Vector
from . import source
from .core import model, curves, editing
from .core.compile import compile_steps, decode, KeyframeConflict, endpoint_seams
from .core.distance import run
from .core.geometry import projection_steps, bake_steps, pad_steps, visible
from .core.files import atomic_text, export_steps

ACTIVE = None
SUSPENDED = None
OWNER_KEY = "anime_sdf_gen_session"


def draft_root():
    # User data, never the extension installation directory or the original blend.
    path=bpy.utils.user_resource('CONFIG')
    if not path:
        raise OSError('The SDF recovery directory could not be created in Blender user data.')
    result=Path(path)/'anime_sdf_gen'/f'v{model.FORMAT_VERSION}'/'drafts'
    result.mkdir(parents=True,exist_ok=True)
    return result


class Registry:
    def __init__(self):
        self.id = uuid.uuid4().hex
        self.ids, self.draw_handlers = [], []

    def own(self, kind, block):
        block[OWNER_KEY] = self.id
        self.ids.append((kind, block))
        return block

    def dispose(self):
        for handler, stage in self.draw_handlers:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(handler, stage)
            except (ValueError, ReferenceError):
                pass
        self.draw_handlers.clear()
        ui, remaining = [], []
        for kind, block in self.ids:
            if kind in ('screens', 'workspaces'):
                try:
                    if block.get(OWNER_KEY) == self.id:
                        ui.append(block)
                except ReferenceError:
                    pass
            else:
                remaining.append((kind, block))
        self.ids = remaining
        if ui:
            # UI IDs have no collection.remove API. Their window has already
            # been closed/rebound; the original workspace is never in this set.
            bpy.data.batch_remove(ui)
        # First unlink owned objects/scenes, then their dependent data. No purge.
        order = {"objects": 0, "scenes": 1, "meshes": 2, "materials": 3,
                 "worlds": 4, "node_groups": 5, "images": 6, "collections": 7}
        for kind, block in sorted(self.ids, key=lambda x: order.get(x[0], 8)):
            try:
                if block.get(OWNER_KEY) != self.id:
                    continue
                collection = getattr(bpy.data, kind)
                if block.use_fake_user:
                    block.use_fake_user = False
                if kind in ("objects", "scenes", "collections"):
                    collection.remove(block, do_unlink=True)
                elif block.users == 0:
                    collection.remove(block)
                else:
                    # A user explicitly adopted a preview resource elsewhere.
                    # Preserve that reference instead of destroying unrelated work.
                    del block[OWNER_KEY]
            except (ReferenceError, RuntimeError):
                traceback.print_exc()
        self.ids.clear()


class WindowState:
    def __init__(self, context):
        self.window = context.window
        self.scene = context.window.scene if context.window else context.scene
        self.view_layer = context.view_layer
        self.workspace = context.workspace if context.window else None
        self.active = context.view_layer.objects.active
        self.selected = [o for o in context.view_layer.objects if o.select_get()]
        self.mode = self.active.mode if self.active else "OBJECT"
        self.area = context.area if context.area and context.area.type == 'VIEW_3D' else None
        self.viewport = None
        if self.area:
            space = self.area.spaces.active
            r = space.region_3d
            self.viewport = {"shading": space.shading.type, "overlays": space.overlay.show_overlays,
                             "location": r.view_location.copy(), "rotation": r.view_rotation.copy(),
                             "distance": r.view_distance, "perspective": r.view_perspective,
                             "toolbar": space.show_region_toolbar, "tool_header": space.show_region_tool_header,
                             "clip_start": space.clip_start, "clip_end": space.clip_end,
                             "use_clip_planes": r.use_clip_planes,
                             "local_collections": space.use_local_collections,
                             "mesh_visible": space.show_object_viewport_mesh}

    def restore(self):
        # Extraction restores its own temporary mode changes immediately. The
        # dedicated window never changes the original view/selection/workspace.
        # Reapplying an old snapshot here would erase changes made by the user.
        pass


class Session:
    def __init__(self, context, project, face, layout=None):
        self.project, self.face = project, face
        self.state = WindowState(context)
        self.registry = Registry()
        self.history = model.History()
        self.direction, self.key_index, self.contour, self.point = model.LTR, 0, 0, 0
        self.handle = "co"
        self.selected={(0,0)}
        self.curve_edit=None
        self.landmark = "nose"
        self.flat = False
        self.orbit_preview, self.playing, self.rotation = False, False, 0.
        self.closed, self.busy, self.dragging = False, False, False
        self.close_requested=None
        self.save_requested=False
        self.message, self.error, self.seam_warning = "", "", ""
        self.conflict = None
        self.field_cache = {}
        self.mask_cache = {}
        self.thresholds = None
        self.preview_job = None
        self.export_job = None
        self.debounce = 0.
        self.draft_due = 0.
        self.last_tick = time.perf_counter()
        self.last_render_ms = 0.
        self.render_times = []
        self.image = self.preview_object = self.scene = None
        self.output_paths = None
        self._timer = self.tick
        self._modal_running = False
        self._syncing = False
        self.editor = None
        self.layout_state = layout
        self.bvh = None
        self._material_copies = {}
        self.mask_revision=0
        self._mask_texture=None
        self._mask_texture_revision=-1
        self.refresh_projection()

    @property
    def stage(self):
        return self.project['authoring']['stage']

    def refresh_projection(self):
        from mathutils.bvhtree import BVHTree
        face = self.face
        self.bvh = BVHTree.FromPolygons(face.vertices.tolist(), face.triangles.tolist(), all_triangles=True)
        self.depth, self.facing = run(projection_steps(face.projected, self.size))
        self.domain = np.isfinite(self.depth)
        if not self.domain.any() and self.stage != 'ORIENT':
            raise ValueError("No front-facing face surface. Reset the face orientation.")

    def redraw(self):
        if self.editor:
            self.editor.redraw()

    def source_context(self):
        kwargs = {'scene': self.state.scene, 'view_layer': self.state.view_layer}
        if self.state.window and self.state.window in list(bpy.context.window_manager.windows):
            kwargs['window'] = self.state.window
        return bpy.context.temp_override(**kwargs)

    @property
    def size(self):
        return self.project["settings"]["preview_size"]

    @property
    def keyframe(self):
        self.key_index=max(0,min(self.key_index,len(model.sweep(self.project,self.direction))-1))
        return model.get_keyframe(self.project, self.direction, self.key_index)

    @property
    def curve(self):
        cs = self.keyframe["contours"]
        self.contour = min(self.contour, len(cs)-1)
        return cs[self.contour]

    def begin(self, attach_handlers=True):
        try:
            self._build_preview()
            if self.stage=='FIT':self.seed_landmarks()
            self.activate_stage()
            self.debounce = time.perf_counter()+.15
            self.safe_write_draft()
            if attach_handlers and self.state.window and not bpy.app.background:
                from .editor import Editor
                self.editor = Editor(self, self.layout_state)
                self.editor.open()
                bpy.app.timers.register(self._timer, first_interval=.03)
            self.sync_ui()
        except Exception:
            self.close(remove_draft=False)
            raise

    def _build_preview(self):
        own = self.registry.own
        self.scene = own("scenes", bpy.data.scenes.new("Anime SDF Gen Preview"))
        self.scene.render.engine = 'BLENDER_EEVEE'
        self.scene.view_settings.view_transform = 'Standard'
        self.scene.world = own("worlds", bpy.data.worlds.new("SDF Preview World"))
        self.scene.world.color = (.12, .12, .12)
        mesh = own("meshes", bpy.data.meshes.new("SDF Preview Face"))
        mesh.from_pydata(self.face.vertices.tolist(), [], self.face.triangles.tolist())
        mesh.update()
        for p in mesh.polygons:
            p.use_smooth = True
        self.preview_object = own("objects", bpy.data.objects.new("SDF Preview Face", mesh))
        self.scene.collection.objects.link(self.preview_object)
        self.scene.view_layers[0].objects.active=self.preview_object
        self.preview_object.select_set(True,view_layer=self.scene.view_layers[0])
        self.image = own("images", bpy.data.images.new("SDF Live Mask", width=self.size, height=self.size, alpha=True, float_buffer=True))
        self.image.colorspace_settings.name = 'Non-Color'
        self.image.alpha_mode = 'CHANNEL_PACKED'
        self.rgba = np.ones((self.size, self.size, 4), dtype=np.float32)
        self.preview_object.hide_select = False
        self.image.use_fake_user = True
        self.populate_reference()

    def populate_reference(self):
        if self.editor:
            self.editor.geometry_revision += 1
        mesh = self.preview_object.data
        mesh.clear_geometry()
        mesh.from_pydata(self.face.vertices.tolist(), [], self.face.triangles.tolist())
        mesh.update()
        for p in mesh.polygons:
            p.use_smooth = True
        for layer in list(mesh.uv_layers):
            mesh.uv_layers.remove(layer)
        for name, coords in (self.face.uv_layers or {self.face.reference['uv_map']: self.face.uvs}).items():
            layer = mesh.uv_layers.new(name=name)
            layer.data.foreach_set('uv', coords.astype(np.float32).ravel())
        if self.face.reference['uv_map'] in mesh.uv_layers:
            mesh.uv_layers.active = mesh.uv_layers[self.face.reference['uv_map']]
        mesh.materials.clear()
        for original in self.face.materials or []:
            key = original.as_pointer() if original else 0
            if key not in self._material_copies:
                mat = original.copy() if original else bpy.data.materials.new('Anime SDF Gen Neutral')
                self._material_copies[key] = self.registry.own('materials', mat)
            mesh.materials.append(self._material_copies[key])
        if self.face.material_indices is not None:
            mesh.polygons.foreach_set('material_index', self.face.material_indices)
        self._face_batch = None

    def frame_view(self):
        if self.editor:
            self.editor.frame()

    def set_front(self, rotation=None):
        if self.editor:self.editor.navigation.stop()
        if rotation is None:
            if not self.editor or not self.editor.ready:
                raise ValueError('Wait for the authoring view to open.')
            rotation = self.editor.views['AUTHOR'].view_rotation
        a = source.fit_frame(self.face.vertices, rotation @ Vector((0,0,1)), rotation @ Vector((0,1,0)))
        ref = deepcopy(self.project['source'])
        props = bpy.context.window_manager.anime_sdf_gen
        ref['uv_map'] = props.uv_map or ref['uv_map']
        ref['front_only'] = props.front_only
        with self.source_context():
            face = source.from_reference(ref, a, allow_relink=True)
        self.push_history()
        self.face = face
        self.project['source'], self.project['alignment'] = face.reference, a
        self.project['authoring'].update(stage='FIT', anchors={})
        self.project['landmarks']=deepcopy(model.DEFAULT_LANDMARKS)
        self.refresh_projection(); self.populate_reference()
        self.seed_landmarks()
        self.changed()
        self.frame_view()

    def seed_landmarks(self):
        """Attach missing default markers to the visible frontal surface."""
        a=self.project['alignment'];extent=max(a['width'],a['height'])
        start_depth=(float(np.max(self.face.projected[...,2]))+1)*extent
        direction=-Vector(a['forward'])
        covered=np.argwhere(self.domain)
        if not len(covered):raise ValueError('No visible face surface for fitting markers.')
        supported=(covered[:,::-1]+.5)*model.SPAN/self.size-model.PAD
        for name,default in model.DEFAULT_LANDMARKS.items():
            if name in self.project['authoring']['anchors']:continue
            target=np.asarray(self.project['landmarks'].get(name,default))
            # Try the intended point first, then the nearest covered pixel
            # centers when a facial opening leaves a hole under that point.
            nearest=np.argsort(np.sum((supported-target)**2,axis=1),kind='stable')[:32]
            for xy in [target,*supported[nearest]]:
                origin=source.world_point(a,xy,start_depth)
                hit,normal,index,distance=self.bvh.ray_cast(origin,direction)
                if hit is not None and self.place_landmark(hit,index,name):break
            else:raise ValueError(f'Cannot place the {name} marker on the selected face.')
        self.landmark='nose'
        self.error='';self.sync_ui();self.redraw()

    def pick_landmark(self, region, view, mouse, name=None):
        origin, direction = view.ray(mouse)
        hit, normal, index, distance = self.bvh.ray_cast(origin, direction)
        if hit is None:
            self.notify_error('Click on the visible face to place a marker. No surface was hit.')
            return False
        return self.place_landmark(hit, index, name or self.landmark)

    def place_landmark(self, hit, index, name):
        a = self.project['alignment']
        delta = np.asarray(hit)-a['center']
        coords = np.array([np.dot(delta,a['right'])/a['width']+.5,
                           np.dot(delta,a['up'])/a['height']+.5,
                           np.dot(delta,a['forward'])/max(a['width'],a['height'])])
        if not visible(self.depth, coords[None], 4*model.SPAN/self.size)[0]:
            self.error = 'That point is outside supported frontal coverage. Choose a visible facial surface.'
            self.redraw()
            return False
        tri = self.face.vertices[self.face.triangles[index]]
        weights = np.linalg.lstsq(np.vstack([tri.T, np.ones(3)]), np.append(hit,1), rcond=None)[0]
        weights = np.clip(weights,0,1); weights /= weights.sum()
        self.project['landmarks'][name] = coords[:2].tolist()
        self.project['authoring']['anchors'][name] = {'world':list(hit), 'barycentric':weights.tolist(),
                                                     'vertices':self.face.triangle_vertices[index].tolist()}
        self.error = ''
        self.draft_due = time.perf_counter()+.5
        self.sync_ui(); self.redraw()
        return True

    def fit(self, count=None):
        if any(name not in self.project['authoring']['anchors'] for name in ('nose','mouth','chin')):
            raise ValueError('Place Nose, Mouth Center, and Chin on the face before fitting.')
        nose, mouth, chin = (self.project['landmarks'][k][1] for k in ('nose','mouth','chin'))
        if not nose > mouth > chin:
            raise ValueError('Place Nose above Mouth Center, and Mouth Center above Chin.')
        self.push_history()
        model.refit(self.project, count)
        self.direction, self.key_index, self.contour, self.point = model.LTR,0,0,0
        self.changed()
        self.activate_stage()

    def activate_stage(self):
        """Initialize a step without refitting curves or invalidating cached fields."""
        self.playing=self.orbit_preview=False
        if self.stage in ('EDIT','CONFIRM'):
            self.direction,self.key_index,self.contour,self.point=model.LTR,0,0,0
            self.handle='co';self.keyframe_scroll=0;self.rotation=0.
            self.reset_selection()
        if self.stage=='CONFIRM':
            self.playing=self.orbit_preview=True
            self.flat=False
        self.last_tick=time.perf_counter()
        self.draft_due=self.last_tick+.1
        self.render_mask()
        if self.editor:self.editor.refresh_appearance()
        self.sync_ui();self.redraw()

    def confirm(self):
        if self.stage!='EDIT':raise ValueError('Adjust the curves before confirming.')
        self.project['authoring']['stage']='CONFIRM'
        self.activate_stage()

    def restore_project(self, project):
        previous_stage=self.stage
        self.cancel_preview()
        changed_geometry = project['alignment'] != self.project['alignment'] or project['source'] != self.project['source']
        self.project = project
        if changed_geometry:
            with self.source_context():
                self.face = source.from_reference(project['source'],project['alignment'],validate=self.stage!='ORIENT')
            self.refresh_projection(); self.populate_reference()
        self.changed()
        if self.stage!=previous_stage:self.activate_stage()

    def canonicalize_edit(self):
        model.synchronize_mirror(self.project, self.direction)

    def push_history(self):
        self.history.push(self.project)

    def normalize_selection(self):
        self.direction=self.direction if self.direction in model.SWEEP_LABELS else model.LTR
        self.key_index=max(0,min(self.key_index,len(model.sweep(self.project,self.direction))-1))
        frame=model.get_keyframe(self.project,self.direction,self.key_index)
        self.contour=max(0,min(self.contour,len(frame['contours'])-1))
        self.point=max(0,min(self.point,len(frame['contours'][self.contour]['points'])-1))
        self.selected.intersection_update(editing.available(frame))

    def reset_selection(self, whole_curve=False):
        self.handle='co'
        self.selected={(self.contour,i) for i in range(len(self.curve['points']))} if whole_curve else {(self.contour,self.point)}

    def cancel_curve_edit(self):
        if self.curve_edit:self.curve_edit.cancel()

    def checkpoint(self):
        return {'project':deepcopy(self.project),'face':self.face,
                'selection':(self.direction,self.key_index,self.contour,self.point,self.handle,self.landmark),
                'selected':self.selected.copy(),
                'undo':self.history.undo_stack[:],'redo':self.history.redo_stack[:]}

    def rollback(self,state):
        previous_stage=self.stage
        self.cancel_preview()
        geometry=self.face is not state['face']
        self.project,self.face=state['project'],state['face']
        self.direction,self.key_index,self.contour,self.point,self.handle,self.landmark=state['selection']
        self.selected=state['selected'].copy()
        self.history.undo_stack,self.history.redo_stack=state['undo'],state['redo']
        self.dragging=False
        if geometry:self.refresh_projection();self.populate_reference()
        self.changed()
        if self.stage!=previous_stage:self.activate_stage()

    def notify_error(self,exc):
        self.error=str(exc) or 'The edit could not be completed. You can continue editing.'
        self.redraw()

    def cancel_preview(self):
        if self.preview_job:self.preview_job.close()
        self.preview_job=None

    def changed(self, dragging=False):
        self.normalize_selection()
        self.playing=False
        self.canonicalize_edit()
        self.thresholds = None
        self.cancel_preview()
        self.conflict = None
        self.error = self.seam_warning = ""
        self.debounce = time.perf_counter()+(.20 if dragging else .08)
        self.draft_due = time.perf_counter()+.5
        self.orbit_preview = False
        self.rotation = model.keyframe_rotation(self.direction,self.keyframe["progress"])
        self.render_mask(validate=not dragging and self.stage=='EDIT')
        if self.editor and not dragging:
            self.editor.refresh_appearance()
        self.sync_ui()

    def select_keyframe(self, direction, index):
        if direction not in model.SWEEP_LABELS or not 0<=index<len(model.sweep(self.project,direction)):
            raise ValueError('Choose an existing keyframe in a sweep row.')
        self.playing = self.orbit_preview = False
        self.direction, self.key_index = direction, index
        self.contour, self.point, self.handle = 0, 0, 'co'
        self.reset_selection()
        self.rotation = model.keyframe_rotation(direction,self.keyframe['progress'])
        self.render_mask();self.sync_ui()

    def render_mask(self, validate=False):
        start = time.perf_counter()
        try:
            if self.orbit_preview and self.thresholds is not None:
                direction, progress = model.rotation_sample(self.rotation)
                channel = 0 if direction == model.LTR else 1
                mask = decode(self.thresholds[..., channel], progress)
            else:
                # Preview the current artwork immediately, including an invalid
                # contour being repaired. Validation still blocks generation.
                mask = curves.raster_keyframe(self.project, self.keyframe, self.direction, self.size, False,self.mask_cache)
            self.rgba[..., 0] = mask
            self.rgba[..., 1] = self.conflict if self.conflict is not None else 0
            self.rgba[..., 2] = self.domain
            self.image.pixels.foreach_set(self.rgba.ravel())
            self.image.update()
            self.mask_revision+=1
            self.redraw()
            if validate:curves.raster_keyframe(self.project,self.keyframe,self.direction,self.size,True,self.mask_cache)
        except ValueError as exc:
            self.error = str(exc)
        self.last_render_ms = (time.perf_counter()-start)*1000
        self.render_times.append(self.last_render_ms)
        self.render_times = self.render_times[-120:]

    def sync_ui(self):
        self.normalize_selection()
        wm = bpy.context.window_manager
        if not hasattr(wm, 'anime_sdf_gen'):
            return
        self._syncing = True
        try:
            props = wm.anime_sdf_gen
            self.point = min(self.point, len(self.curve['points'])-1)
            pt = self.curve['points'][self.point]
            props.point_xy = pt['co']
            props.handle_mode = pt['mode']
            props.handle_left = pt['left']
            props.handle_right = pt['right']
            props.rotation = self.rotation
            props.flat = self.flat
            props.layer_operation = self.curve['operation']
            props.reference = self.project['authoring']['reference']
            props.preset = self.project['preset']
            props.keyframes = self.project['authoring']['keyframe_count']
            props.mirror_sweeps = self.project['mirror_sweeps']
            props.output = self.project['settings']['output']
            props.resolution = str(self.project['settings']['resolution'])
            props.uv_map = self.project['authoring']['uv_map']
            props.front_only = self.project['authoring']['front_only']
        finally:
            self._syncing = False

    def write_draft(self):
        atomic_text(draft_root()/(self.project['id']+'.sdfproject.json'), model.dumps(self.project))

    def safe_write_draft(self):
        try:
            self.write_draft()
            return True
        except (OSError,ValueError) as exc:
            # Recovery IO must never prevent restoration or cause preview IDs
            # to be included in an ordinary .blend save.
            self.error='Recovery draft unavailable: '+str(exc)
            self.draft_due=0
            print('Anime SDF Gen:',self.error)
            return False

    def tick(self):
        if self.closed:
            return None
        if self.close_requested is not None:
            # Dispose after the operator/input event has returned to Blender.
            # Closing its native window from inside that event frees its RNA.
            end_session(remove_draft=self.close_requested)
            return None
        if self.save_requested:
            self.save_requested=False
            try:
                with bpy.context.temp_override(window=self.editor.window,area=self.editor.native_area):
                    bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')
            except Exception as exc:self.notify_error(exc)
            return None if self.closed else .025
        now = time.perf_counter()
        try:
            if self.editor:
                if not self.editor.alive():
                    end_session(remove_draft=True)
                    return None
                if not self.editor.ready:
                    self.editor.advance()
                    return .035
                self.editor.navigation.poll()
                self.editor.lock_author()
                self.editor.tick_tooltip(now)
            if self.draft_due and now >= self.draft_due:
                self.safe_write_draft()
                self.draft_due = 0
            if self.busy:
                self.advance_export(.012)
            elif not self.dragging and self.stage in ('EDIT','CONFIRM'):
                if self.thresholds is None and self.preview_job is None and now >= self.debounce:
                    self.preview_job = compile_steps(self.project, self.size, self.domain, self.field_cache,self.mask_cache)
                if self.preview_job:
                    stop = now+.009
                    while time.perf_counter() < stop:
                        try:
                            next(self.preview_job)
                        except StopIteration as done:
                            self.thresholds = done.value
                            seams=endpoint_seams(self.thresholds,self.domain)
                            affected=[f'{name}: {count} pixels' for name,count in seams.items() if count]
                            self.seam_warning=('360° orbit seam at '+', '.join(affected)+'. Align the two sweeps’ endpoint artwork for a continuous orbit. Export is available.') if affected else ''
                            self.preview_job = None
                            if self.orbit_preview: self.render_mask()
                            break
                        except (ValueError, KeyframeConflict) as exc:
                            self.error = str(exc)
                            self.conflict = exc.mask if isinstance(exc, KeyframeConflict) else None
                            self.preview_job = None
                            self.debounce = float('inf')
                            self.render_mask()
                            break
                if self.playing and self.thresholds is not None:
                    self.rotation = model.advance_rotation(self.rotation, (now-self.last_tick)*30.)
                    self.orbit_preview = True
                    self.render_mask()
                    self.sync_ui()
            self.last_tick = now
        except Exception as exc:
            self.error = str(exc)
            traceback.print_exc()
            if self.editor and not self.editor.ready:
                if hasattr(bpy.context.window_manager,'anime_sdf_gen'):
                    bpy.context.window_manager.anime_sdf_gen.status='Could not open editor: '+self.error
                end_session(remove_draft=False)
                return None
        return .025

    def _generate(self):
        # Re-read before export to catch a changed source, pose, or UV layout.
        with self.source_context():
            face = source.from_reference(self.project['source'], self.project['alignment'])
        size = self.project['settings']['resolution']
        depth, facing = yield from projection_steps(face.projected, size)
        threshold = yield from compile_steps(self.project, size, np.isfinite(depth))
        image = yield from bake_steps(threshold, face.uvs, face.projected, depth, facing, size)
        image = yield from pad_steps(image, max(1, round(self.project['settings']['padding']*size/2048)))
        yield "Verify and commit output files", .99
        output = bpy.path.abspath(self.project['settings']['output'])
        if not output:
            raise ValueError("Choose an output path before generation.")
        return (yield from export_steps(self.project, image, output))

    def start_export(self):
        if self.stage != 'CONFIRM':
            raise ValueError('Continue to Confirm to choose the save location before generating.')
        if not self.project['settings']['output'].strip():
            raise ValueError("Choose a save location in Confirm before generating.")
        model.validate_project(self.project)
        self.busy, self.playing = True, False
        self.cancel_preview()
        self.error, self.conflict = '', None
        self.export_job = self._generate()
        self.safe_write_draft()

    def advance_export(self, seconds=.012, finish=True):
        stop = time.perf_counter()+seconds
        while self.export_job and time.perf_counter() < stop:
            try:
                label, progress = next(self.export_job)
                self.message = f"{label} · {progress:.0%}"
            except StopIteration as done:
                self.output_paths = done.value
                self.export_job, self.busy = None, False
                self.message = "Saved: "+self.output_paths[0]
                if finish:
                    end_session(remove_draft=True)
                break
            except Exception as exc:
                self.export_job, self.busy = None, False
                self.cancel_preview()
                self.debounce=float('inf')
                self.error = str(exc)
                if isinstance(exc, KeyframeConflict):
                    self.direction, self.key_index = exc.direction, exc.after
                    coords = np.linspace(0, len(exc.mask)-1, self.size).astype(int)
                    self.conflict = exc.mask[np.ix_(coords, coords)]
                    self.orbit_preview = False
                    self.render_mask()
                    self.sync_ui()
                traceback.print_exc()
                break
        if not self.closed:
            self.redraw()

    def cancel_export(self):
        if self.export_job:
            self.export_job.close()
        self.export_job, self.busy = None, False
        self.message = "Generation cancelled; authoring data retained."

    def close(self, remove_draft=False):
        if self.closed:
            return
        self.cancel_curve_edit()
        self.closed, self.playing = True, False
        self.cancel_preview()
        for job in (self.export_job,):
            if job:
                job.close()
        self.export_job = None
        if bpy.app.timers.is_registered(self._timer):
            bpy.app.timers.unregister(self._timer)
        if getattr(self,'_event_timer',None):
            try:
                bpy.context.window_manager.event_timer_remove(self._event_timer)
            except ReferenceError:
                pass
            self._event_timer = None
        if self.editor:
            self.editor.close()
        self.state.restore()
        self.registry.dispose()
        self._face_shader = None
        self._face_batch = None
        self._mask_texture=None
        self.bvh = None
        self._material_copies.clear()
        from .drawing import flat_contour
        flat_contour.cache_clear()
        self.image = self.scene = self.preview_object = None
        self.thresholds = None
        self.field_cache.clear()
        self.mask_cache.clear()
        self.curve_edit=None
        if remove_draft:
            try:
                (draft_root()/(self.project['id']+'.sdfproject.json')).unlink(missing_ok=True)
            except OSError as exc:
                print('Anime SDF Gen: could not remove recovery draft:',exc)


def start(context, project, face, handlers=True, layout=None):
    global ACTIVE
    if ACTIVE:
        raise ValueError("Finish or close the current SDF authoring session first.")
    session = Session(context, project, face, layout)
    ACTIVE = session
    try:
        session.begin(handlers)
    except Exception:
        ACTIVE = None
        raise
    return session


def end_session(remove_draft=False):
    global ACTIVE
    current, ACTIVE = ACTIVE, None
    if current:
        current.close(remove_draft)


@bpy.app.handlers.persistent
def save_pre(_):
    global SUSPENDED
    if ACTIVE and not SUSPENDED:
        ACTIVE.cancel_curve_edit()
        ACTIVE.safe_write_draft()
        SUSPENDED = {"project": deepcopy(ACTIVE.project), "face": ACTIVE.face,
                     "history": ACTIVE.history, "direction": ACTIVE.direction, "key_index": ACTIVE.key_index,
                     "editor": {k:deepcopy(getattr(ACTIVE,k)) for k in ('contour','point','handle','landmark','selected','flat','rotation','orbit_preview','playing')},
                     "window": ACTIVE.state.window,
                     "layout": ACTIVE.editor.snapshot() if ACTIVE.editor else None}
        end_session(remove_draft=False)


def resume():
    global SUSPENDED
    if not SUSPENDED:
        return None
    data, SUSPENDED = SUSPENDED, None
    try:
        window = data['window']
        if window and window not in list(bpy.context.window_manager.windows):
            window = next(iter(bpy.context.window_manager.windows), None)
        kwargs = {'window': window} if window else {}
        with bpy.context.temp_override(**kwargs):
            s = start(bpy.context, data['project'], data['face'], layout=data.get('layout'))
            s.history = data['history']
            s.select_keyframe(data['direction'], data['key_index'])
            for k,value in data.get('editor',{}).items():setattr(s,k,value)
            s.render_mask();s.sync_ui()
    except Exception:
        traceback.print_exc()
    return None


@bpy.app.handlers.persistent
def save_post(_):
    if SUSPENDED and not bpy.app.timers.is_registered(resume):
        bpy.app.timers.register(resume, first_interval=.05)


@bpy.app.handlers.persistent
def load_pre(_):
    global SUSPENDED
    if ACTIVE:
        ACTIVE.cancel_curve_edit()
        ACTIVE.safe_write_draft()
        end_session(remove_draft=False)
    SUSPENDED = None
    if bpy.app.timers.is_registered(resume):
        bpy.app.timers.unregister(resume)


def register_handlers():
    for name, callback in (("save_pre", save_pre), ("save_post", save_post),
                           ("save_post_fail", save_post), ("load_pre", load_pre)):
        handlers = getattr(bpy.app.handlers, name)
        if callback not in handlers:
            handlers.append(callback)


def unregister_handlers():
    load_pre(None)
    for name, callback in (("save_pre", save_pre), ("save_post", save_post),
                           ("save_post_fail", save_post), ("load_pre", load_pre)):
        handlers = getattr(bpy.app.handlers, name)
        if callback in handlers:
            handlers.remove(callback)
