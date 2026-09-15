# Anime SDF Gen — curve selection, transforms and mask-only preview

## Goals

Make projected curves fast to edit with box selection and Blender's active selection/transform key bindings. Remove normal-based lighting from the live shadow preview so it displays only authored shadow regions. Preserve the floating popup and source workspace; no migration work.

## Implementation

- [x] Add session-local multi-point selection, Shift-click, box selection, select-all/deselect, and visible selection feedback across current-keyframe contours.
- [x] Read Blender's active curve/3D View and transform modal keymaps for Move/Rotate/Scale and constraints. Implement these actions on the fixed face plane, with numeric entry, Shift precision, Ctrl snapping, confirmation and cancellation. Keep transforms in session data without mutable source geometry or helper datablocks.
- [x] Integrate selection and transforms with direct dragging, mirrored sweeps, lit-cutout carry, history, keyframe/layer changes, and save/close lifecycle.
- [x] Remove the normal-light multiplier and light-direction uniform from the preview shader. Keep coverage/conflict diagnostics, a colored mask and a black/white mask. Rename the preview toggle to describe those appearances accurately.
- [x] Add meaningful numerical and real Blender input regressions: multi-selection, constrained/numeric transforms, snapping, undo/cancel, remapped shortcuts, mask-only GPU pixels and cleanup.
- [x] Update usage/tooltips, build the extension and source archives, validate the actual package, and verify that the fixture remains unchanged.
