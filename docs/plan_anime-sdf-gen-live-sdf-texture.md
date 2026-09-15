# Anime SDF Gen — live low-resolution SDF textures

## Goals

Generate real directional SDF threshold textures during authoring and sample them directly in the preview toon shader. Measure compilation latency separately from interactive frame rate. Preserve readable geometry, the exact mask view, source assets and the floating popup.

## Implementation

- [x] Build a reusable UV transfer lookup so edits do not rasterize the mesh again. Generate a low-resolution threshold field with the existing numerical engine and transfer it to an owned Non-Color preview texture.
- [x] Queue immutable artwork snapshots, reuse unchanged distance fields, coalesce edits and spend bounded work per UI tick. Keep the last complete preview while the next texture is generated; discard pending work when the session/source changes.
- [x] Have the toon shader sample the actual UV-mapped threshold texture, select the directional channel and apply the sentinel-aware cutoff. Light playback changes uniforms without CPU mask decoding or image uploads. Remove the obsolete full-size CPU mask/image update; numerical masks remain internal to compilation and validation.
- [x] Retain facial form shading and an exact black/white inspection mode in the material. Preserve coverage/conflict feedback and export validation without assigning preview assets to the source model.
- [x] Test UV transfer against export, GPU threshold decoding, asymmetric sweeps, sentinels, editing/cancellation, save/close cleanup and zero uploads during playback. Measure cached rebuild time, drag frame intervals and publication latency on the fixture.
- [x] Update documentation, build 0.13.0, validate the actual extension archive, and preserve test_sdf.blend unchanged.
