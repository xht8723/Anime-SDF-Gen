# Anime SDF Gen

A Blender add-on for creating anime-style face-shadow textures. Define shadow shapes with editable curves, preview them on your model at different light angles, and export the maps for use in a character shader.

[Download v0.14.0](https://github.com/xht8723/sdf_gen/releases/download/v0.14.0/anime_sdf_gen-0.14.0.zip) · [Usage guide](https://github.com/xht8723/sdf_gen/blob/main/docs/usage.md)

## Features

- Editable Bézier curves for shadow boundaries.
- Live preview with shaded and black-and-white views.
- Mirrored or independent editing for the left and right sides.
- Lit cutouts and additional shadow patches.
- Full 360° light playback.
- A floating editor with Blender navigation and G / R / S controls.
- 16-bit PNG export with RGB channel packing or separate maps.
- Editable project files for saving and continuing your work.

## Installation

Requires **Blender 5.2 or newer**. Tested on **Windows**.

1. Download the extension ZIP from the [latest release](https://github.com/xht8723/sdf_gen/releases/latest).
2. In Blender Preferences, use **Install from Disk** and select the ZIP.

## Basic workflow

1. Select the face using an Edit Mode selection or a vertex group.
2. Create a session, orient the face, and place the landmarks.
3. Adjust the shadow curves across the light-angle keyframes.
4. Review the result with the live preview and 360° playback.
5. Choose the resolution and channel packing, then export.

The export includes PNG textures and an editable project file. Shader setup is manual; the texture format guide explains how to use the maps.

## Documentation

- [Usage and controls](https://github.com/xht8723/sdf_gen/blob/main/docs/usage.md)
- [Texture and project format](https://github.com/xht8723/sdf_gen/blob/main/docs/output-format.md)
- [Validation details](https://github.com/xht8723/sdf_gen/blob/main/docs/validation.md)
- [Report an issue](https://github.com/xht8723/sdf_gen/issues)

## License

[GPL-3.0-or-later](https://github.com/xht8723/sdf_gen/blob/main/anime_sdf_gen/LICENSE). Maintained by [xht8723](https://github.com/xht8723).
