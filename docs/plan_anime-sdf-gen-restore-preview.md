# Anime SDF Gen — restore the 0.10.0 shadow preview

## Goals

Restore the shadow preview's appearance and update behavior from the verified 0.10.0 release archive. Keep subsequent curve selection/transform controls, workflow, export settings, validation, recovery and source preservation. Ship a new 0.14.0 release without project migrations or duplicate preview modes.

## Checklist

- [x] Compare the 0.10.0 archive with current source and isolate preview-only differences.
- [x] Restore the original projected 512-pixel mask, shaded/flat views, immediate editing feedback and cached sweep interpolation. Remove the newer toon/UV-texture preview implementation and its obsolete tests.
- [x] Preserve box selection, G/R/S and remapped shortcuts, undo/cancel, both sweep rows, 360-degree playback, Confirm and output packing.
- [x] Compare GPU output directly with the archived 0.10.0 shader and mask generation. Run interaction and lifecycle regressions in disposable Blender processes; preserve test_sdf.blend.
- [x] Update documentation, package 0.14.0, validate the actual ZIP, and verify that unrelated code remains unchanged.
