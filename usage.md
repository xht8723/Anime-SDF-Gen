# Anime SDF Gen — usage

Version **0.21.0**, maintained by [xht8723](https://github.com/xht8723). Blender **5.2 LTS** on Windows.

## Install and create

In **Edit → Preferences → Get Extensions**, open the menu and choose **Install from Disk**. Select `anime_sdf_gen-0.21.0.zip` and enable **Anime SDF Gen**. In the original 3D View, press **N** and open **Anime SDF Gen**.

Close any authoring session before replacing the installed extension. Restart Blender after installing the new build so its Python modules load fresh.

Use one source method:

- **Selected Faces:** make a mesh active, enter Edit Mode, and select the facial surface. Fully selected visible polygons count in face, edge, or vertex selection mode. Multi-object Edit Mode captures only the active mesh.
- **Vertex Group:** make a mesh active and choose a group. A polygon is included when all its vertices have positive weight in that group. Both Object Mode and Edit Mode work.

Choose **Shadow keyframes** (default nine per complete sweep), then click **Create**. The selected polygon IDs and active UV map are captured. Later selection changes do not silently change the authoring region. Keyframe count can also be changed inside the popup before fitting.

For the supplied fixture, select polygons assigned to `head` on `body` using Blender's material selection controls. These names are a fixture convenience; the add-on has no material-name requirement.

## Language

The same extension contains English and Simplified Chinese. In **Edit → Preferences → Interface → Language**, choose **Chinese (Simplified)** or Blender’s **Automatic** setting. Anime SDF Gen follows Blender’s effective language; unsupported add-on languages fall back to English.

Blender’s **Interface**, **Tooltips** and **Reports** translation options apply independently. Changing language updates the open editor and retained warnings without restarting it or changing artwork, selection, history, playback or a running export. Native dialogs follow Blender’s own redraw behavior. Object names, UVs, vertex groups, filenames and project metadata remain literal. Language changes do not alter texture values.

See the [Simplified Chinese guide](usage.zh-Hans.md). Updating the extension requires a fresh module load as described above; switching language does not.

## The floating popup

The editor opens in a separate, resizable Blender window with Blender's workspace tabs, menus, editor headers, and sidebars hidden. It contains:

- **Setup:** one large shaded view, a short guide beside the step counter, and a large **Next Step** button with a smaller back arrow beside it. The arrow is disabled in step one and remains beside **Generate & Finish** in step four.
- **Curve editor:** the shaded reference and editable curves, alongside an independent **Live shadow preview**.
- **Confirm:** one large live preview with automatic playback, save-location settings and **Generate & Finish**.
- **Controls:** an add-on column on the right, scrollable when needed.
- **Keyframe rows:** Left → Right and Right → Left boundary sweeps, with a 360° light-rotation slider beneath them.

During curve editing, drag the divider to change view widths. **Focus** or **Ctrl+Space** over a view enlarges it; **Split views** restores both. Very narrow windows display one view; enlarge the window for side-by-side editing. The original Blender window remains available and unchanged.

Hover over any button for a short tooltip. Disabled buttons explain why an action is unavailable. Tooltips appear after a brief pause, stay inside the window, and disappear when clicking, dragging, scrolling or navigating.

Navigation uses Blender's actual viewport operators and active navigation keymap. With the standard keymap, **middle mouse** orbits, **Shift + middle mouse** pans, and the **wheel** zooms. **Numpad 1 / 3 / 7** selects exact front/right/top views, **4 / 6** rotates by steps, and **5** switches perspective/orthographic. Blender's turntable/trackball and navigation preferences apply. Setup also has **Front / Right / Top** buttons. **Frame face** returns to the fitted head frame.

Both setup steps allow orbiting. During curve editing the authoring view is fixed to an orthographic face projection; use Shift + middle mouse to pan and the wheel to zoom. Orbit in the live shadow view to inspect the result.

## Orient and fit

1. **Orient the face to front view.** Orbit until the face looks straight at you and the head is upright. **Source / UV…** contains **Bake UV map** and **Frontal surface only**. The bake map defaults to the active map captured when creating the session. Frontal filtering is **off by default**, so all selected geometry receives the projection. Turn it on only to exclude surfaces facing away or hidden from the front; this can also exclude cheeks and the underside of the chin. Click **Next Step**.
2. **Place markers.** Nose, Mouth Center and Chin appear at approximate default positions. Drag them wherever they help fit your curves; no anatomical ordering is required. You can orbit to inspect them. Choose a preset, **Keyframes per sweep** and **Mirror Full Sweep**, then click **Next Step**.
3. **Adjust curves.** The curve editor and live shadow view appear together, starting on keyframe 1 of Left → Right. Select keyframes and adjust their curve points, then click **Next Step**.
4. **Confirm.** A single large preview automatically rotates the light through **Front → character left → Back → character right → Front** and repeats. Choose the save location, file name, bake UV map, texture resolution and output packing, then click **Generate & Finish**.

Returning from editing to markers shows **Return to editing**, which keeps all current curves, frame positions and counts. Changes to markers, the starting preset or the fitting count apply only through **Refit boundaries…**. That separate action asks before replacing every main boundary; extra shapes are copied from nearby existing frames, so reducing the frame count can omit shapes. Refitting is undoable. The safe return route survives drafts, reopening, Blender save/resume, and revisiting orientation.

The default marker positions fit the face bounds and snap to the mesh where possible. If a default falls over an opening, it tries nearby geometry. Markers without a surface stay on the drawing plane; dragging into empty space also places them on that plane. These are fitting guides, not detected anatomy. The keyframe count has small minus/plus buttons around a wide, centered numeric selector. Click the number for direct entry; any count from **2 to 33** works, including even counts. Both endpoints are included in that count.

**Neutral** reference shading makes facial features visible. **Materials** displays copied source materials under preview lighting. Presets fit the selected bounds and landmarks; they do not detect anatomy automatically.

**Clean Face** starts every main boundary as a straight vertical line, including after refitting or moving the markers sideways. Its seven points remain editable, with the lower points placed at marker heights. **Nose Accent** starts with a shaped profile fitted to the markers.

## Curves and keyframes

The two rows are labelled by boundary movement in the fitted front view:

- **Left → Right:** shadow expands from the left edge across the entire face as keyframe progress increases.
- **Right → Left:** shadow expands from the right edge across the entire face as its own keyframe progress increases.

Each row contains keyframes **1 … N**. Default first keyframes leave the face fully lit; default last keyframes leave it fully shadowed. There is no shared middle keyframe. The controls show the selected row's count.

For a first edit, choose a middle keyframe and drag a visible point. The first frame deliberately has its boundary outside the face. The editor includes default shortcut reminders and labels the blue previous-frame and purple next-frame guides. Keyframe tooltips show the exact light angle and sweep progress, including uneven spacing after insertion. The filled button identifies the frame being edited; an underline follows preview playback independently. The preview header identifies both states, and the locked row always displays **Mirrored from Left → Right**.

- Click a keyframe, then select points over the reference. Selected points are orange; the larger point is active. **Shift-click** adds or removes a point. Drag a selected point to move the group, or drag a handle to adjust only that handle. The projected mask updates immediately during the drag.
- Press **B**, then drag a box around points. **Shift** with the box gesture, or the middle mouse button, subtracts points. Dragging empty space also selects a box; Shift adds and Ctrl subtracts in this case. **A** selects all enabled curves' points, **Alt+A** deselects and **Ctrl+I** inverts selection. Clicking a layer selects its whole curve; adding a shape selects all three points.
- Use **G / R / S** to move, rotate or scale selected points. **X / Y** constrains the face-plane axes; press the same axis again to clear it. Type a displacement, degrees or scale factor. For example, **G X .05 Enter** moves the selection by 5% of face width; **R 15 Enter** rotates it by 15 degrees around the selected points' center. Movement coordinates use normalized face width/height. Rotation and uniform scale preserve physical proportions despite differing face width and height. Z movement is locked to preserve the projection.
- Hold **Shift** for fine mouse movement and **Ctrl** for incremental snapping: movement .01 face units, rotation 5 degrees, scale .1. Combining Shift and Ctrl uses .001 units, 1 degree and .01. Explicit numeric input takes precedence over snapping. Click, Enter or Space confirms a keyboard transform; **Esc** or right-click restores the artwork, mirrored sweep and history from before it. Mouse dragging confirms on release and also supports Esc cancellation.
- These selection, transform and modal shortcuts are read from Blender's active Curve, 3D View and modal keymaps, including remapped keys. The examples use Blender's standard keymap. The transforms operate on session data in the fixed face plane; they do not move the source mesh. Changes to the preferred selection mouse button also apply.
- Click the active point's **X / Y…** control for absolute coordinates and handle offsets. Double-clicking a point also opens this dialog. **Smooth**, **Corner**, and **Free** apply to all selected points; free handles can be dragged independently.
- **Insert** splits the following segment; **Remove** deletes a point. The main boundary endpoints are retained above/below the working face. Zoom out or pan to reach them.
- The two curved-arrow icons at the top undo and redo; **Ctrl+Z** and **Ctrl+Shift+Z** also use session-local history.
- **Copy previous keyframe** copies the preceding keyframe within the selected row. **Add keyframe** inserts a copy halfway toward the next one (or before the last endpoint when selected). **Remove** preserves the first and last keyframes. Wheel over crowded rows to scroll.
- **Mirror Full Sweep** makes **Left → Right** the editable source. **Right → Left** stays visible but disabled and mirrors every left frame in head space, including on asymmetric UV layouts. Adding, deleting, copying or editing left frames updates the right row immediately, preserving frame order and progress positions. Enabling the option always replaces Right → Left with a reflection of Left → Right; if the right row was selected, selection moves to the nearest left frame (earlier frame on a tie), selecting its main boundary’s first point. The toggle can be undone. Turning it off unlocks the right row with its current mirrored artwork; both rows can then have independent artwork, counts and intermediate positions. Full 360° playback continues to use both sweeps.

**Shapes and their point controls share the full-height sidebar.** Click a flat list row to select the whole shape. Its effect, rename, transform, duplicate, delete, visibility and order controls appear below the list, followed by its point coordinates, handle modes and point insertion/removal. Scroll within a long shape list or drag its scrollbar; scroll elsewhere in the sidebar to reach overflowing properties. Canvas selection and frame changes reveal the active shape automatically. The main boundary is always retained. Keyframe actions, Mirror Full Sweep and playback stay together below the views.

**Add shape** creates one enabled, closed curve with three **Smooth** points near the middle of the lower face. Select **Lit cutout** to carve a bright patch inside the main shadow, or **Shadow patch** to darken the region. Use **Rename shape…** for names such as “Cheek highlight”; names are saved and mirrored with the artwork. The shape list labels its effect or hidden state. The preview updates automatically and editing pauses playback. Move and reshape it for any feature, including the nose or chin. Change points to **Corner** for sharp vertices or **Free** for individual Bézier handles. Areas apply in the displayed layer order. Closed curves support duplicate, delete, hide, reorder, point edits, and **Move / Rotate / Scale…**.

When several points are selected, the panel shows their count and the active point. **Smooth / Corner / Free** affect every selected point; **X / Y…**, **Insert** and **Remove** affect only the active point. Mixed handle modes leave all three mode buttons unselected.

A **Lit cutout** also carries into earlier keyframes in its own sweep. For example, a triangle on Left → Right keyframe 7 keeps its region lit on keyframes 1–6 wherever those frames would shadow it. It does not alter the opposite row unless **Mirror Full Sweep** is enabled; linking reflects the artwork and its carry into that other row. The handles remain on keyframe 7. Moving, reshaping, hiding or deleting the original updates all inherited light, and Undo/Redo covers the change. No duplicate curves are inserted into earlier keyframes.

Later lit cutouts take precedence over earlier shadow artwork. Multiple cutouts contribute their combined lit footprints to earlier keyframes. Within a cutout's own keyframe, a Shadow layer placed after it can refill part of it; only the surviving light carries backward. This behavior keeps one lit-to-shadow transition per pixel and one threshold map per light direction.

The back arrow in **Confirm** returns to keyframe 1 of Left → Right, preserving all curves and output settings. Returning to Confirm restarts the orbit at Front. From curve editing, the back arrow returns to markers in a single view, preserving their positions. **Next Step** from markers regenerates main curves and both rows with the chosen count, retaining closed patches from the nearest previous keyframes. Refit is undoable. Going back again to orientation and confirming a new front resets the three markers to defaults in the new head frame.

Unavailable actions are dimmed, such as removing a row's first/last keyframe or deleting a triangle's last three points. Active and selected buttons brighten on hover. Warnings appear in **Needs attention**, pinned to the bottom of the right panel. They do not shift the controls above. Scroll over a long warning to read it independently of the controls, or use its × button to dismiss it. Failed actions roll back partial artwork and history changes. Invalid curves remain editable; export stays blocked until corrected.

## Preview lighting

Drag the rotation slider or click **Play 360°**. One orbit takes 12 seconds, passing **Front (0°) → character left (90°) → Back (180°) → character right (270°) → Front (360°)** before wrapping to zero. The first half advances the Left → Right row from first to last; the return half samples Right → Left from last to first. The light continues rotating in the same direction. The row and nearest keyframe highlight follow this sampling.

Choosing a keyframe or editing artwork pauses playback. **Shaded preview / Flat mask**, beside **Focus** in the live preview header, changes its appearance. In a narrow header it becomes a circular shading icon with the same tooltip and behavior.

The shadow preview uses warm lit regions, cool shadow regions, and smooth surface lighting that follows the light sweep. **Flat mask** displays the lit/shadow boundary in black and white. The projection remains attached to the head when you orbit the preview. Preview shading is never baked into exported textures or assigned to source materials; copied source materials remain available in the reference view.

The current keyframe's projected **512-pixel mask**, including carried lit cutouts, updates immediately while dragging. After editing pauses, cached distance fields calculate the interpolated sweep. Playback decodes those thresholds into the displayed mask; it does not rebuild distance fields every frame. A new edit or cancellation discards unfinished interpolation work. There is one preview implementation, with no live UV-texture/toon mode retained.

Each direction encodes one lit-to-shadow transition per pixel. Lit cutouts carry backward automatically to satisfy this rule. Remaining reversals caused by main boundaries or Shadow patches appear magenta, with the offending keyframes in the warning footer; generation is blocked until corrected, but drafts can still be saved. Generation computes and validates at the chosen output resolution.

Crossing curves, coincident points and collapsed shapes are accepted. Crossings use even–odd filling: each boundary crossing switches between inside and outside, so intersecting loops can leave holes. Shape and point counts have no fixed cap; complex artwork takes more time and memory to process.

The two first masks meet at Front; the two last masks meet at Back. If their artwork differs, switching maps can cause a visible jump. An **orbit seam** warning identifies the endpoint and pixel count. You can align the endpoint artwork for seamless rotation, or keep it and export. This warning does not silently merge the rows. Default preset endpoints match.

## Export, close, and recover

In **Confirm**, click the **Save location** field to choose a folder and file name in Blender's file browser. The **File name** and **Texture resolution** fields can also be edited separately.

**Bake UV map**, above Texture resolution, opens a searchable list of the source mesh's UV maps. You can also choose it through **Source / UV…** in Orientation. Changing it in Confirm keeps the current fit, artwork, landmarks, history and projected preview. It does not change the source's active/render UV maps or the **Materials** reference shading. The choice is retained through stage changes, drafts, saving, reopening and export. If source geometry, pose or region membership has changed, relink the source before switching maps.

Overlapping and mirrored UVs are allowed without overlap checks. At shared texels, later valid triangle samples overwrite earlier values. Different face locations may therefore receive the same baked shadow even when their projected preview differs. Inspect the export and adjust the chosen UV map if needed. Collapsed UV triangles write no samples; out-of-tile areas are skipped. Coordinates must still be finite.

You can draw, preview, and save drafts without a UV map. Choose an existing map before exporting. A saved project whose map is missing can reopen for editing; geometry and pose checks still apply. Draft files have no fixed 16 MB limit. If no texels are baked, export still succeeds with always-lit background thresholds and zero face coverage; the completion card reports this result.

**Output precision** applies to every generated texture: **8-bit PNG**, **16-bit PNG** (default), or **32-bit Float EXR**. Depth is per channel. The live preview uses floating-point thresholds; bit-depth quantization is applied during export. 8-bit saves space but can produce coarser sweep transitions; 32-bit stores the calculated floating-point precision in larger, uncompressed EXR files. The destination extension and file list follow this choice.

**Smoothing** defaults to **Off / 0**. Drag its slider from 0 to 8, or click the number for precise entry. Escape cancels a slider drag; cancelling the numeric dialog restores its starting value. Confirm playback updates after a short pause in adjustment. Smoothing can change small lit cutouts and shadow timing; it does not make a hard-cutoff shader produce soft edges. Always-lit/shadowed pixels and face coverage are preserved. The amount scales with resolution, so the low-resolution preview approximates the same effect as export. Set 0 to restore the unsmoothed result.

Under **Output packing**, each map has **R / G / B / Separate** buttons:

- **Left shadow** is the threshold for lighting from the character's left. It defaults to R.
- **Right shadow** is the threshold for lighting from the character's right. It defaults to G.
- **Face coverage** marks the supported face in UV space. It defaults to B.

Choose any RGB channel for each map. Selecting an occupied channel swaps its two map assignments. **Separate** writes that map as a single-channel image at the selected precision. Mix packed and separate maps, or store all three separately. Empty packed channels are zero. These choices update the file list and its channel labels immediately while playback continues.

Packed maps share `<stem>.png` or `<stem>.exr`. Individual maps use the suffixes `_left`, `_right`, and `_coverage` with the selected extension. The editable project is `<stem>.sdfproject.json`; it records the actual file/channel mapping. Load every texture as **Non-Color**.

Projects use schema 4. Projects from older releases are rejected without modifying their files; create a new project with this release.

**Generate & Finish** stages and verifies all listed files, commits the set, then closes the popup. Existing files in the chosen output set receive an overwrite confirmation. Export errors appear in the warning footer and retain Confirm; **Cancel Generation** stops work and keeps the session. Use the back arrow to adjust curves again.

After success, the original **Anime SDF Gen** launcher retains an **Export complete** card with the saved folder, file count, **Open output folder**, **Reopen project**, and a **Shader setup guide** link. It reminds you to load the textures as **Non-Color**. The card describes the last successful export in this Blender session; a cancelled or failed export does not replace it. Reopening uses the saved editable project directly.

All owned preview meshes, materials, images, scenes, internal UI data, handlers, timers, and GPU resources are released. No global orphan purge runs and no shader is assigned. If the original window was closed during authoring, the remaining window returns to the source workspace instead of quitting Blender.

- **Save Draft & Close** preserves an editable project without generating a texture.
- **Discard & Close** or the window's **X** removes the active automatic draft. Explicitly saved projects and generated files remain.
- **Edit Existing SDF** opens projects in this release's schema. On source mismatch, choose the active selection/group, reopen, and enable **Relink to Active Source** in the file browser. Review orientation and fit before generating.

Automatic drafts live outside the `.blend`, under `anime_sdf_gen/v4/drafts/` in Blender's user configuration directory. Saving a `.blend` cancels any unconfirmed curve transform, removes the popup and preview before serialization, then rebuilds them after success or failure. The current step, confirmed artwork, point selection, output packing, local history, cameras and rotation/playback state are retained; interrupted generation can be started again. Loading another file or disabling the add-on preserves a recovery draft. **Recover Latest Draft** opens the newest current-schema draft. Reopening a Confirm project starts its orbit at Front; reopening curve editing selects keyframe 1 of Left → Right.

Only complete records using the documented current schema are accepted. Missing required fields are reported; no project migrations, default-filling upgrades or compatibility loaders are included. Existing authored files are preserved.

## Supported models

The output covers the 0–1 UV tile: triangles crossing its boundary are clipped, triangles outside it are skipped, and UV triangles collapsed to a line or point write no texels. This is not UDIM export. Coordinates must be finite. Current armature and shape-key deformation is captured; evaluation must preserve topology. Prepare a source copy when topology-changing modifiers are required. Shared UV texels store only one value per output channel.

All selected surfaces receive the same frontal projection by default, including back-facing, hidden and edge-on surfaces. Surfaces at the same projected location share artwork; they cannot be authored independently in this projection. Choose the source region and final material coverage to control where the effect applies. The optional frontal filter restricts coverage to front-visible surfaces. See the [format guide](output-format.md) for decoding and [validation](validation.md) for measured performance.
