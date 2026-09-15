# Character toon shader with automatic face SDF shadows

## Goals

- Apply a simple two-tone shader to the open character through Blender MCP, preserving existing color textures and geometry.
- Select the character-left or character-right SDF threshold from the Sun's world direction relative to the face.
- Decode Anime SDF Gen exports with their recorded UV map, channels, face coverage, angle convention, and endpoint sentinels.
- Save a separate `character_toon_sdf.blend`; keep `test_sdf.blend` and authored exports unchanged.

## Checklist

- [x] Inspect the live scene, source materials, Sun, and output format.
- [x] User chose to assign their own maps later; leave left/right image slots empty and Enable SDF at 0.
- [x] Build reusable, clearly labeled shader groups and automatic transform drivers.
- [x] Connect new toon materials while retaining the source materials and images.
- [x] Validate left/front/right lighting, map endpoints, head rotation, and saved-file reload in a disposable Blender process.
- [x] Inspect rendered results and save the completed Blender file, usage notes, and validation evidence.

## Scope

This is a character material setup in the open Blender scene. The authoring popup and extension release are outside this change. Validation files belong in `build/validation/toon-sdf`.

## Result

- `character_toon_sdf.blend` contains nine toon materials, two empty face map image slots, the optional coverage input, and three shader groups.
- `tools/setup_character_toon.py` records the Blender MCP implementation and supplies an optional current-export connector.
- `docs/character-toon-shader.md` and the Blender text `Character Toon - Read Me` explain setup and controls.
- `build/validation/toon-sdf/report.json` reports PASS. EEVEE render probes check map selection and sentinels. A disposable copy also renders a verified sample export under left, front and right lighting.
- Validation opens the saved file with script autorun disabled. Transform drivers remain valid, including parented light and rotated head tests.
