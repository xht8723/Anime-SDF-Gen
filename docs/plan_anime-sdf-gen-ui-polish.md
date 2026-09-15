# Anime SDF Gen — concise workflow and default markers

## Goals

Simplify the floating editor according to the seven requested refinements. Preserve the native viewport controls and clean session lifecycle. Use shadow keyframes throughout visible controls, messages and current documentation.

## Checklist

- [x] Put a smaller back-arrow control beside Next Step / Generate in every step; disable it at step one. Remove the duplicate panel back controls.
- [x] Give active and primary buttons a distinct hover color. Replace Undo/Redo text with compact icons while retaining their functionality.
- [x] Use only the requested short step guides, with the step counter immediately beside them. Remove navigation hints, preview explanations and count explanations; reclaim their viewport space.
- [x] Automatically seed three surface-attached default markers when entering fitting, with a nearest-supported-surface fallback for holes. Keep existing marker adjustments when returning from curve editing.
- [x] Rename visible phases to shadow keyframes, including dialogs, progress/errors and usage text.
- [x] Verify real back/next clicks, selected-button hover pixels, automatic surface markers and dragging, undo, and viewport layout in disposable Blender tests. Preserve test_sdf.blend.
- [x] Update documentation and package version 0.5.0 extension and source ZIPs.

This is a clean revision. It adds no migrations or compatibility aliases. Numerical channel encoding remains unchanged.

Delivered with real-input, surface-marker, integration, export and package checks. The current redraw timing did not meet the 30 FPS target; measurements and a same-session control comparison are recorded in [validation.md](validation.md).
