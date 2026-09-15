# Blender SDF Face Author — accepted implementation plan

## Goals

Build an installable extension for vanilla Blender 5.2 LTS on Windows. Author binary face-shadow phases using fitted Bézier contours, nose/chin patches, and a fixed head-space projection with live preview. Generate a 16-bit RGB threshold texture and an editable JSON sidecar, then restore the original Blender workspace and remove all owned temporary resources.

Preserve `test_sdf.blend` (SHA256 `26275b63c848416f1340ee79c53f318b9a86e9c382724dd3c0bd4eaeedda1914`) as the validation fixture. Its face is the `head` material region on the `body` mesh.

## Agreed scope and interfaces

- Select mesh, material/selected-face region, existing UV, head alignment, destination, resolution, odd initial phase count (default 9), sweep direction, and shadow symmetry.
- Clean Face and Nose Accent presets fitted to face bounds, with nose/mouth/chin landmarks. Main open contour closes beyond the face; closed Nose and Chin patches support ordered Add/Remove Shadow operations.
- Point/handle editing, smooth/corner modes, insertion/removal, numeric coordinates, patch transforms/duplication, neighboring outlines, mirrored editing, local undo/redo, paired phase insertion/removal, and copying.
- Separate front-to-left and front-to-right monotonic sequences sharing the frontal phase. Reject phase conflicts and self-intersections rather than changing artwork.
- Rasterize padded projection-space masks, compute signed Euclidean distances, interpolate crossing thresholds, transfer through UV triangles, and pad islands. Default preview 512; output 2048.
- RGB16 PNG: R = light from character left; G = light from character right; B = valid face coverage. Threshold 0 means always shadow; 1 means always lit; interior values are front-to-side progress. Non-Color data.
- Versioned `.sdfproject.json` contains source/region/UV fingerprints, alignment, landmarks, phases, handles, operations, settings, and output convention. Reopening validates or explicitly relinks the source.
- Independent preview scene/mesh/materials, UUID ownership registry, and invoking-window state snapshot. Finish verifies and commits exports before cleanup; errors retain editing. Cancel restores; Save Draft & Close preserves editable data.
- Recoverable drafts outside the blend; suspend preview around save; recreate after success/failure; dispose on load/disable. No global orphan purge or original shader assignment.
- Existing compatible UVs only. Geometry-derived presets, automatic UV creation, extra projection directions, and integration into the other shader task are deferred.

## Build checklist

- [x] Foundation: extension package, project model/serialization, source validation, session ownership and restoration.
- [x] Authoring: alignment, fitted presets, Bézier controls, nose/chin patches, phase editing, undo/redo.
- [x] Preview: projected mask and shaded views, mirrored controls, sweep playback, conflict/coverage diagnostics.
- [x] Generation: exact distance transform, threshold encoding, incremental UV transfer/padding, RGB16 PNG and staged export.
- [x] Delivery: reopen/relink/recovery, installable ZIP, numerical and Blender integration tests, GUI/performance verification, usage and format documentation.

## Acceptance criteria

- Reference-checked distance transforms; empty/full masks, holes, patches; authored-phase fidelity outside a one-texel boundary tolerance; continuous intermediate motion.
- Asymmetric halves, head-space mirror on asymmetric UVs, shared front, reversal, invalid curves/UVs/geometry/phase order, projection coverage.
- Live updates during drag, numeric edits, undo/redo, projection stable under orbit; target 30 FPS at preview 512 on the test workstation.
- True 16-bit numeric export without color conversion; padding; exact project round trips; export failures and cancelled generation preserve editing.
- Original data and UI restored on finish/cancel, no leaks over repeated sessions, save/load/disable/failure lifecycle coverage.
- Deliver ZIP, source, tests, guides, and validation results without changing the fixture.

## Implementation decisions confirmed during validation

- The supplied full head has real UV overlaps in its rear region. The explicit, default-enabled Frontal subset option restricts authoring to its compatible front-facing triangles without changing the model or UVs. Full-region overlap remains an error.
- The live 3D face is drawn using Blender's GPU API from an independent mesh copy. This avoids material compilation on mouse movement and uses the same mask image as the 2D canvas.
- Mirrored generation validates the union of the face domain and its reflection, then reflects the compiled field. This avoids duplicate distance transforms while still checking both sides of an asymmetric face.
- Recovery file failures do not prevent cleanup or allow preview datablocks into a normal blend save. An in-memory snapshot still supports save suspension/resume.

Completed validation and measured performance are recorded in [validation.md](validation.md).
