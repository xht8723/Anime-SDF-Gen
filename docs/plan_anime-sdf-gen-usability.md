# Anime SDF Gen — navigation, workflow and error recovery

## Goals

Fix the reported frozen input after invalid clicks, use Blender's native viewport navigation, simplify orientation and fitting, and make shape creation and phase settings immediately understandable. Keep the floating window and hidden Blender workspace UI. This is a clean release without migration or compatibility code.

## Implementation checklist

- [x] Contain input/operator errors, roll back failed edits, keep recovery/close available, and disable actions that cannot apply to the current selection. Add real-click and injected-error regression checks.
- [x] Drive navigation through Blender's actual viewport operators and active navigation keymap. Retain independent view cameras, native turntable/trackball preferences, axis snapping, numpad controls and perspective/orthographic switching. Keep curve authoring projection fixed.
- [x] Show one large viewport during orientation and landmark placement. Introduce the split view only for curve editing.
- [x] Add a prominent Next Step action, readable contextual instructions, clear back controls, and visible phase-count controls in setup/fitting and phase totals while editing.
- [x] Create Nose and Chin as closed three-point corner triangles. Refresh the visible GPU shadow immediately on creation and edits, without a second user action. Check actual rendered pixels as well as numerical masks.
- [x] Validate navigation, failure recovery, phase settings, triangle creation and live updates, popup lifecycle, and clean export using disposable Blender processes. Preserve test_sdf.blend.
- [x] Update usage/format/validation documentation and deliver a fresh extension and source ZIP.

Native camera state is hosted in the owned Blender viewport; the popup passes navigation to Blender while displaying the camera in its authoring or inspection rectangle. Workspace menus, tabs and unrelated editing commands remain hidden. During setup, explanations and phase count are visible directly rather than hidden in a settings dialog.

Delivered as version 0.4.0. The regression suite also caught and resolved callback-time window disposal and a native GPU-context failure after closing the source window first. See [validation.md](validation.md) for evidence and performance measurements.
