# Anime SDF Gen — usage

Version **0.14.0**, maintained by [xht8723](https://github.com/xht8723). Blender **5.2 LTS** on Windows.

## Install and create

In **Edit → Preferences → Get Extensions**, open the menu and choose **Install from Disk**. Select `anime_sdf_gen-0.14.0.zip` and enable **Anime SDF Gen**. In the original 3D View, press **N** and open **Anime SDF Gen**.

Close any authoring session before replacing the installed extension. Restart Blender after installing the new build so its Python modules load fresh.

Use one source method:

- **Selected Faces:** make a mesh active, enter Edit Mode, and select the facial surface. Fully selected visible polygons count in face, edge, or vertex selection mode. Multi-object Edit Mode captures only the active mesh.
- **Vertex Group:** make a mesh active and choose a group. A polygon is included when all its vertices have positive weight in that group. Both Object Mode and Edit Mode work.

Choose **Shadow keyframes** (default nine per complete sweep), then click **Create**. The selected polygon IDs and active UV map are captured. Later selection changes do not silently change the authoring region. Keyframe count can also be changed inside the popup before fitting.

For the supplied fixture, select polygons assigned to `head` on `body` using Blender's material selection controls. These names are a fixture convenience; the add-on has no material-name requirement.

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

1. **Orient the face to front view.** Orbit until the face looks straight at you and the head is upright. **Source / UV…** selects the output UV map and **Frontal surface only**. Leave frontal filtering enabled for the fixture, whose rear-head UVs overlap. Click **Next Step**.
2. **Place markers.** Nose, Mouth Center and Chin already appear at approximate default positions on the face. Drag each handle onto the matching feature. You can orbit to inspect it. Nose must be above mouth, and mouth above chin. Choose a preset, **Keyframes per sweep** and **Mirror Full Sweep**, then click **Next Step**.
3. **Adjust curves.** The curve editor and live shadow view appear together, starting on keyframe 1 of Left → Right. Select keyframes and adjust their curve points, then click **Next Step**.
4. **Confirm.** A single large preview automatically rotates the light through **Front → character left → Back → character right → Front** and repeats. Choose the save location, file name, texture resolution and output packing, then click **Generate & Finish**.

The default marker positions fit the face bounds and snap to the frontal surface. If a default falls over an opening, it moves to nearby supported geometry. These are starting positions, not detected anatomy. Empty-space clicks leave markers unchanged. The keyframe count has small minus/plus buttons around a wide, centered numeric selector. Click the number for direct entry; any count from **2 to 33** works, including even counts. Both endpoints are included in that count.

**Neutral** reference shading makes facial features visible. **Materials** displays copied source materials under preview lighting. Presets fit the selected bounds and landmarks; they do not detect anatomy automatically.

**Clean Face** starts every main boundary as a straight vertical line, including after refitting or moving the markers sideways. Its seven points remain editable, with the lower points placed at marker heights. **Nose Accent** starts with a shaped profile fitted to the markers.

## Curves and keyframes

The two rows are labelled by boundary movement in the fitted front view:

- **Left → Right:** shadow expands from the left edge across the entire face as keyframe progress increases.
- **Right → Left:** shadow expands from the right edge across the entire face as its own keyframe progress increases.

Each row contains keyframes **1 … N**. Default first keyframes leave the face fully lit; default last keyframes leave it fully shadowed. There is no shared middle keyframe. The controls show the selected row's count.

- Click a keyframe, then select points over the reference. Selected points are orange; the larger point is active. **Shift-click** adds or removes a point. Drag a selected point to move the group, or drag a handle to adjust only that handle. The projected mask updates immediately during the drag.
- Press **B**, then drag a box around points. **Shift** with the box gesture, or the middle mouse button, subtracts points. Dragging empty space also selects a box; Shift adds and Ctrl subtracts in this case. **A** selects all enabled curves' points, **Alt+A** deselects and **Ctrl+I** inverts selection. Clicking a layer selects its whole curve; adding a triangle selects all three points.
- Use **G / R / S** to move, rotate or scale selected points. **X / Y** constrains the face-plane axes; press the same axis again to clear it. Type a displacement, degrees or scale factor. For example, **G X .05 Enter** moves the selection by 5% of face width; **R 15 Enter** rotates it by 15 degrees around the selected points' center. Movement coordinates use normalized face width/height. Rotation and uniform scale preserve physical proportions despite differing face width and height. Z movement is locked to preserve the projection.
- Hold **Shift** for fine mouse movement and **Ctrl** for incremental snapping: movement .01 face units, rotation 5 degrees, scale .1. Combining Shift and Ctrl uses .001 units, 1 degree and .01. Explicit numeric input takes precedence over snapping. Click, Enter or Space confirms a keyboard transform; **Esc** or right-click restores the artwork, mirrored sweep and history from before it. Mouse dragging confirms on release and also supports Esc cancellation.
- These selection, transform and modal shortcuts are read from Blender's active Curve, 3D View and modal keymaps, including remapped keys. The examples use Blender's standard keymap. The transforms operate on session data in the fixed face plane; they do not move the source mesh. Changes to the preferred selection mouse button also apply.
- Click the active point's **X / Y…** control for absolute coordinates and handle offsets. Double-clicking a point also opens this dialog. **Smooth**, **Corner**, and **Free** apply to all selected points; free handles can be dragged independently.
- **Insert** splits the following segment; **Remove** deletes a point. The main boundary endpoints are retained above/below the working face. Zoom out or pan to reach them.
- The two curved-arrow icons at the top undo and redo; **Ctrl+Z** and **Ctrl+Shift+Z** also use session-local history.
- **Copy previous keyframe** copies the preceding keyframe within the selected row. **Add keyframe** inserts a copy halfway toward the next one (or before the last endpoint when selected). **Remove** preserves the first and last keyframes. Wheel over crowded rows to scroll.
- **Mirror Full Sweep** links corresponding frames across the two rows in head space, including on asymmetric UV layouts. Editing either row updates its opposite; keyframe 3 mirrors to keyframe 3 in the other row. It never mirrors into another position in the same row. Unlinked rows can have different artwork, counts and intermediate positions. Re-enabling the link replaces the opposite row with a reflection of the current row and can be undone.

**Add triangle** creates one enabled, closed curve with three **Smooth** points near the middle of the lower face. Select **Lit area** to carve a bright patch inside the main shadow, or **Shadow area** to darken the region. The preview updates automatically and editing pauses playback. Move and reshape it for any feature, including the nose or chin. Change points to **Corner** for sharp vertices or **Free** for individual Bézier handles. Areas apply in the displayed layer order. Closed curves support duplicate, delete, hide, reorder, point edits, and **Move / Rotate / Scale…**.

A **Lit area** also carries into earlier keyframes in its own sweep. For example, a triangle on Left → Right keyframe 7 keeps its region lit on keyframes 1–6 wherever those frames would shadow it. It does not alter the opposite row unless **Mirror Full Sweep** is enabled; linking reflects the artwork and its carry into that other row. The handles remain on keyframe 7. Moving, reshaping, hiding or deleting the original updates all inherited light, and Undo/Redo covers the change. No duplicate curves are inserted into earlier keyframes.

Later Lit cutouts take precedence over earlier shadow artwork. Multiple cutouts contribute their combined lit footprints to earlier keyframes. Within a cutout's own keyframe, a Shadow layer placed after it can refill part of it; only the surviving light carries backward. This behavior keeps one lit-to-shadow transition per pixel and one threshold map per light direction.

The back arrow in **Confirm** returns to keyframe 1 of Left → Right, preserving all curves and output settings. Returning to Confirm restarts the orbit at Front. From curve editing, the back arrow returns to markers in a single view, preserving their positions. **Next Step** from markers regenerates main curves and both rows with the chosen count, retaining closed patches from the nearest previous keyframes. Refit is undoable. Going back again to orientation and confirming a new front resets the three markers to defaults in the new head frame.

Unavailable actions are dimmed, such as removing a row's first/last keyframe or deleting a triangle's last three points. Active and selected buttons brighten on hover. Warnings appear in **Needs attention**, pinned to the bottom of the right panel. They do not shift the controls above. Scroll over a long warning to read it independently of the controls, or use its × button to dismiss it. Failed actions roll back partial artwork and history changes. Invalid curves remain editable; export stays blocked until corrected.

## Preview lighting

Drag the rotation slider or click **Play 360°**. One orbit takes 12 seconds, passing **Front (0°) → character left (90°) → Back (180°) → character right (270°) → Front (360°)** before wrapping to zero. The first half advances the Left → Right row from first to last; the return half samples Right → Left from last to first. The light continues rotating in the same direction. The row and nearest keyframe highlight follow this sampling.

Choosing a keyframe or editing artwork pauses playback. **Shaded preview / Flat mask**, beside **Focus** in the live preview header, changes its appearance. In a narrow header it becomes a circular shading icon with the same tooltip and behavior.

The shadow preview uses the original **0.10.0** appearance: warm lit regions, cool shadow regions, and smooth surface lighting that follows the light sweep. **Flat mask** displays the lit/shadow boundary in black and white. The projection remains attached to the head when you orbit the preview. Preview shading is never baked into exported textures or assigned to source materials; copied source materials remain available in the reference view.

The current keyframe's projected **512-pixel mask**, including carried lit cutouts, updates immediately while dragging. After editing pauses, cached distance fields calculate the interpolated sweep. Playback decodes those thresholds into the displayed mask; it does not rebuild distance fields every frame. A new edit or cancellation discards unfinished interpolation work. There is one preview implementation, with no live UV-texture/toon mode retained.

Each direction encodes one lit-to-shadow transition per pixel. Lit cutouts carry backward automatically to satisfy this rule. Remaining reversals caused by main boundaries or Shadow areas appear magenta, with the offending keyframes in the warning footer; generation is blocked until corrected. Self-intersections and incompatible UV overlaps also block export. Generation computes and validates at the chosen output resolution.

The two first masks meet at Front; the two last masks meet at Back. If their artwork differs, switching maps can cause a visible jump. An **orbit seam** warning identifies the endpoint and pixel count. You can align the endpoint artwork for seamless rotation, or keep it and export. This warning does not silently merge the rows. Default preset endpoints match.

## Export, close, and recover

In **Confirm**, click the **Save location** field to choose a folder and file name in Blender's file browser. The **File name** and **Texture resolution** fields can also be edited separately.

Under **Output packing · PNG 16-bit**, each map has **R / G / B / Separate** buttons:

- **Left shadow** is the threshold for lighting from the character's left. It defaults to R.
- **Right shadow** is the threshold for lighting from the character's right. It defaults to G.
- **Face coverage** marks the supported face in UV space. It defaults to B.

Choose any RGB channel for each map. Selecting an occupied channel swaps its two map assignments. **Separate** writes that map as a single-channel 16-bit grayscale PNG. Mix packed and separate maps, or store all three separately. Empty packed channels are zero. These choices update the file list and its channel labels immediately while playback continues.

Packed maps share `<stem>.png`. Individual maps use `<stem>_left.png`, `<stem>_right.png`, and `<stem>_coverage.png`. The editable project is `<stem>.sdfproject.json`; it records the actual file/channel mapping. Load every texture as **Non-Color**.

**Generate & Finish** stages and verifies all listed files, commits the set, then closes the popup. Existing files in the chosen output set receive an overwrite confirmation. Export errors appear in the warning footer and retain Confirm; **Cancel Generation** stops work and keeps the session. Use the back arrow to adjust curves again.

All owned preview meshes, materials, images, scenes, internal UI data, handlers, timers, and GPU resources are released. No global orphan purge runs and no shader is assigned. If the original window was closed during authoring, the remaining window returns to the source workspace instead of quitting Blender.

- **Save Draft & Close** preserves an editable project without generating a texture.
- **Discard & Close** or the window's **X** removes the active automatic draft. Explicitly saved projects and generated files remain.
- **Edit Existing SDF** opens projects in this release's schema. On source mismatch, choose the active selection/group, reopen, and enable **Relink to Active Source** in the file browser. Review orientation and fit before generating.

Automatic drafts live outside the `.blend`, under `anime_sdf_gen/v3/drafts/` in Blender's user configuration directory. Saving a `.blend` cancels any unconfirmed curve transform, removes the popup and preview before serialization, then rebuilds them after success or failure. The current step, confirmed artwork, point selection, output packing, local history, cameras and rotation/playback state are retained; interrupted generation can be started again. Loading another file or disabling the add-on preserves a recovery draft. **Recover Latest Draft** opens the newest current-schema draft. Reopening a Confirm project starts its orbit at Front; reopening curve editing selects keyframe 1 of Left → Right.

Only the documented current schema is accepted. No project migrations or compatibility loaders are included. Existing authored files are preserved.

## Supported models

Use compatible UVs in one 0–1 tile and topology-preserving evaluation. Current armature and shape-key deformation is captured. Prepare a source copy when topology-changing modifiers are required. Symmetric art cannot resolve overlapping UVs.

One frontal projection cannot independently author the rear head, hidden cavities, or underside shadows. The Face coverage map marks supported regions; restrict the eventual shader to the intended face geometry when other surfaces share those UVs. See the [format guide](output-format.md) for decoding and [validation](validation.md) for measured performance.
