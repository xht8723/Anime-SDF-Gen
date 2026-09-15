# Character toon shader

Open `character_toon_sdf.blend`. The character uses a simple two-tone **EEVEE** material, with the original color textures. Material Preview uses scene lighting. Rotate **Sun** to change the lighting.

## Add your face SDF maps

On the `body` object, open the **head | Toon** material in the Shader Editor.

1. Load the character-left threshold image in **LEFT SDF - Non-Color**.
2. Load the character-right threshold image in **RIGHT SDF - Non-Color**.
3. Set both images' Color Space to **Non-Color**. They use `UVMap`; do not mirror the right map's UVs.
4. In **Face SDF Controls**, set **Enable SDF** to **1**.
5. Optionally connect your face coverage mask to **Coverage**. This limits the effect to the authored facial area. The default value 1 applies SDF to the front-facing part of the head material.

SDF starts disabled so the character renders normally before maps are assigned. Left/right refer to the **character's** sides. Positive local X on **Anime Face Direction** is character left, local Y is head up, and local Z points forward. This reference follows `body`. If you rig the character, parent it to the head bone while keeping its alignment.

### Packed exports

For the default Anime SDF Gen packed image, connect an Image Texture set to Non-Color to a **Separate Color** node in RGB mode:

| Image channel | Face SDF Controls input |
|---|---|
| R | Left Threshold |
| G | Right Threshold |
| B | Coverage |

Other channel arrangements use the assignments recorded in your `.sdfproject.json`. Separate grayscale maps can use their Color outputs directly.

An optional helper in `tools/setup_character_toon.py` provides `connect_export(path_to_sidecar)`. It verifies the current export schema, file hashes and source mesh/UV fingerprint, connects the recorded channels, aligns the head reference, packs the images, and enables SDF. Run it from this project with its directory on Python's module search path.

## Controls

- **Simple Toon Controls / Shadow Tint** sets the darker tone as a multiplier of the original base color.
- **Light Threshold** moves the regular toon boundary; **Edge Softness** softens that boundary.
- **Face SDF Controls / Edge Softness** controls only the authored face shadow edge.
- **Enable SDF** blends from normal toon shading (0) to the face SDF result (1).

The shared groups are **Anime Simple Toon**, **Anime Face SDF**, and **Anime Sun and Face Direction**. The Sun and head reference use built-in transform drivers, including world-space parent and constraint effects. No timer, custom driver namespace, or script auto-run is needed after reopening the file.

## Map convention

Compatible maps encode Anime SDF Gen front-to-side switching thresholds. Progress is absolute horizontal light yaw / 90 degrees, clamped to 0–1. The Sun's local +Z points toward the light. Its position has no effect on a directional light.

The selected threshold is decoded with 0 always shadowed and 1 always lit within the authored front-to-side range. Rear illumination shades the face fully; an exactly vertical Sun falls back to regular toon shading. SDF overrides physical cast shadows inside its coverage; ordinary toon lighting and cast shadows remain outside it.

The shader uses Shader to RGB and requires **EEVEE**. Arbitrary distance textures with another encoding need a matching decoder.

## Preservation

The original material datablocks are retained. The setup preserves source geometry, UVs and packed base textures, and saves its changes only to `character_toon_sdf.blend`. No SDF image is assigned in the delivered file; the empty slots are ready for your own maps.
