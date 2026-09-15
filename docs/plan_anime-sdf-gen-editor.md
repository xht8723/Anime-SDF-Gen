# Anime SDF Gen v0.2 — accepted implementation plan

## Goals and confirmed defaults

Replace the small canvas/sidebar workflow with a dedicated resizable Blender window. Rename the product Anime SDF Gen, maintained by xht8723 (https://github.com/xht8723). Preserve the original test_sdf.blend, the numerical pipeline and RGB16 output contract.

Flow: select facial geometry → Create → orient face → place landmarks → fit preset → edit curves → preview sweep → Generate & Finish.

- Selected faces on the active Edit Mode mesh by default; optional vertex group. All vertices must have positive group weight to include a polygon.
- Neutral reference shading by default; original materials optional.
- Orbit the reference, then Set Face Front; click nose, mouth center, chin on the surface.
- Closing with X discards the active session and automatic recovery draft. Explicitly saved drafts and committed outputs remain.
- Nine default phases; mirrored authoring; preview 512; output 2048. One bouncing sweep slider, no reverse toggle.

## Implementation checklist

- [x] Source capture: no material-name dependence in launcher; snapshot selected polygons, support vertex groups, active UV default, preserve selection and mode, detect source/group changes.
- [x] Format 2: explicit migration from format 1 preserving artwork and face IDs; store surface landmark anchors and fitting stage; ignore old playback direction.
- [x] Branding: Anime SDF Gen v0.2.0, maintainer xht8723, GitHub homepage; keep extension ID and operator namespace compatible.
- [x] Window lifecycle: owned native main window/workspace/screens; two viewport roles and phase shelf; original window remains intact; support resize/maximize; one session at a time.
- [x] Fitting: neutral reference mesh with preserved UV/material data, orientation from view, BVH surface picking, labeled draggable nose/mouth/chin anchors, explicit undoable refit preserving patches.
- [x] Authoring: full-size front-view handles, numeric edits, shapes, layers, symmetry, neighbors, local undo/redo; orbitable live shadow inspection; DPI-aware picking and labels.
- [x] Playback: full-width phase strip, Character Left → Front → Character Right slider with continuous endpoint reversal; choosing a phase pauses playback.
- [x] Cleanup/recovery: finish commits verified files before cleanup; export errors retain session; explicit discard/X cancels and deletes only automatic draft; save snapshots and removes editor before serialization and resumes afterward; load/disable preserve recovery and clean up; never globally purge.
- [x] Validation: numerical and migration regression, source modes/groups, landmark hit/miss, resize/maximize/orbit/drag, 2K/4K and UI-scale measurements, window/file-save/failure lifecycle, repeat leak tests, clean saved-file inspection, package import.
- [x] Delivery: anime_sdf_gen-0.2.0.zip, source/tests, revised usage and output format, validation report documenting unavailable display checks.

## Interface and compatibility decisions

The launcher contains source method/group, Create, Open, Recover. Other settings move into the editor. Default layout uses an approximately 60/40 authoring/inspection split, bottom phase shelf, collapsible inspector. Reference geometry remains recognizable while inspection shows the shadow. Curve coordinates stay in the fixed head projection; landmarks additionally store surface anchors. Native window lifecycle feasibility was checked in a disposable Blender 5.2.1 process, including a clean save initiated from the editor.

Use one session, explicit area roles and scoped input/drawing. Track all owned UI/data resources. Restore temporary extraction changes immediately and avoid overwriting later user changes in the original window. If the original window disappears, restore the last surviving editor to the source workspace on finish instead of quitting Blender.

Source mismatches and changed vertex-group membership require explicit relinking. Old projects open directly in curve editing. RGB16 R/G/B meanings, endpoint sentinels, UV padding and sidecar filenames are unchanged. No shader integration or additional projection directions are included.

Completed September 14, 2026. See [validation](validation.md) for evidence and measured limits: 17 numerical tests, 16 Blender integration checks, native-window lifecycle and interaction suites, verified 2048 output, and validated ZIP import. The desktop constrained the 4K-width client to 3840 × 2043; full 2160-pixel client height and mixed-monitor OS DPI transitions remain unverified. Dragging measured about 32–34 viewport draws/s median, with some frames slower than the 30 FPS target.
