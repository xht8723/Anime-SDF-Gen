# Anime SDF Gen — full boundary sweeps and 360-degree lighting

## Goals

Replace the shared-Front/two-half model with two complete independently authored boundary sweeps. Mirror entire sweeps in fitted head space. Keep per-map PNG packing and the isolated floating editor. No migration or old-schema support.

## Conventions

- Rows: Left → Right and Right → Left, in the fitted front view. N means keyframes per sweep (2–33; odd and even counts).
- Each row runs from progress 0 to 1, with expanding shadow. Default boundaries cross the entire face, from outside one edge to outside the other.
- Light rotation: 0° Front, 90° character left, 180° Back, 270° character right, 360° Front. The first half samples Left → Right at angle/180; the second samples Right → Left at (360-angle)/180.
- Mirror Full Sweep links corresponding frames in the two rows, never different frames within one row. Independent rows may have different counts after editing.
- Lit cutouts protect earlier frames only within their own row. Mirroring carries the corresponding artwork to the opposite row. Front/Back endpoint differences are reported as visible orbit seams, without silently merging artwork.
- Output maps remain character-left threshold, character-right threshold and coverage. Document the new 180-degree progress mapping and head-relative direction selection. All PNG packing options remain.

## Checklist

- [x] Audit model, rasterization, compilation, selection, caches, controls, overlays, playback, history, serialization, recovery and export for assumptions about halves or paired frames.
- [x] Replace the schema/model and obsolete helpers with complete sweep arrays, independent insertion/removal, full-sweep mirroring and one 360-degree rotation mapping.
- [x] Update fitted presets, local light carry, compilation/conflicts and endpoint-seam diagnostics.
- [x] Replace the keyframe strip with two direction-labelled rows; update counts, controls, tooltips, overlays and the full-rotation slider.
- [x] Update selection/history/error recovery and save/load lifecycle; remove obsolete runtime state and UI properties.
- [x] Replace obsolete tests with current-schema regressions for full sweeps, independent rows, mirroring, cutout carry, orbital decoding, packing and rollback.
- [x] Exercise real Blender input, a full orbit, endpoint diagnostics, export, undo/redo, invalid input, save/reopen and cleanup in disposable processes.
- [x] Update documentation, build the extension/source ZIPs and verify the package and unchanged fixture.
