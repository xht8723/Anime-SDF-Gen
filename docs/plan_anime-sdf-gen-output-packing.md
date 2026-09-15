# Anime SDF Gen — straight presets and output packing

## Goals

- Make every Clean Face main boundary straight, including refitting after landmark edits. Keep its points editable and preserve Nose Accent shaping.
- Let users route Left shadow, Right shadow, and Face coverage to any RGB channel or to individual grayscale textures in Confirm.
- Keep 16-bit numerical PNG output, live preview, lit-cutout propagation, and workspace restoration intact.
- Use the new project schema directly, without migration or compatibility code.

## Implementation checklist

- [x] Generate collinear Clean Face points in every keyframe and direction.
- [x] Add validated per-map packing settings; swap occupied channels when reassigned.
- [x] Write and verify RGB16 and grayscale16 PNGs from canonical quantized map data.
- [x] Export all configured textures and the project sidecar in one rollback-safe transaction, recording exact map/channel/file conventions.
- [x] Add packing controls, tooltips, and a dynamic file list to Confirm; include every destination in overwrite checks.
- [x] Cover straight presets, all packing permutations, mixed/separate outputs, quantization, round trips, invalid settings, and multi-file rollback in numerical tests.
- [x] Exercise packing controls, live playback, export, reloading, and cleanup in a disposable Blender process using the unchanged test fixture.
- [x] Update usage and format documentation; build and validate the v0.9.0 extension and source ZIPs.
