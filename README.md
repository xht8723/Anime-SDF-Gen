# Anime SDF Gen

A Blender add-on for creating anime-style face-shadow textures. Define shadow shapes with editable curves, preview them on your model at different light angles, and export the maps for use in a character shader.

[Download the latest published release](https://github.com/xht8723/Anime-SDF-Gen/releases/latest) · [Usage guide](usage.md) · [简体中文指南](usage.zh-Hans.md)

Shapes use a flat list in the full-height sidebar, with shape actions and point properties grouped beneath it. Keyframes and playback stay below the views.

## Demo

Face shadows under a moving light, followed by boundary and cutout editing with the live preview.

https://github.com/user-attachments/assets/7cbefedc-edcd-4a6f-b7d6-56ef065f0153

## Features

- Editable Bézier curves for shadow boundaries.
- Live preview with shaded and black-and-white views.
- Mirrored or independent editing for the left and right sides.
- Mirror Full Sweep keeps Left → Right editable and synchronizes the locked Right → Left row, including keyframe additions and deletions.
- Lit cutouts and additional shadow patches.
- Full 360° light playback.
- A floating editor with Blender navigation and G / R / S controls.
- Safe return from setup, explicit refitting, named shapes, and separate editing/playback frame cues.
- 8/16-bit PNG and 32-bit float EXR export, with RGB packing or separate maps.
- Choose the bake UV map in Orientation or Confirm. Mirrored and overlapping UVs are allowed; shared texels use the last valid triangle sample.
- Optional threshold smoothing with a live Confirm preview; off by default.
- Editable project files for saving and continuing your work.
- English and Simplified Chinese UI, following Blender’s language settings with live switching and artist-focused Chinese labels and explanations.

## Installation

Requires **Blender 5.2 or newer**. Tested on **Windows**.

1. Download the extension ZIP from the [latest release](https://github.com/xht8723/Anime-SDF-Gen/releases/latest).
2. In Blender Preferences, use **Install from Disk** and select the ZIP.

## Basic workflow

1. Select the face using an Edit Mode selection or a vertex group.
2. Create a session, orient the face, and place the landmarks.
3. Adjust the shadow curves across the light-angle keyframes.
4. Review the result with the live preview and 360° playback.
5. Choose resolution, output precision and channel packing, optionally adjust smoothing, then export.

Version 0.20.0 exports PNG or EXR textures and an editable project file. Output defaults to 16-bit PNG with smoothing off. Shader setup is manual; the texture format guide explains how to use the maps.

## Documentation

- [Usage and controls](usage.md)
- [Texture and project format](output-format.md)
- [Validation details](validation.md)
- [Developer architecture](architecture.md)
- [Translation maintenance](i18n-development.md)
- [Cleanup audit](cleanup-audit.md)
- [Report an issue](https://github.com/xht8723/Anime-SDF-Gen/issues)

## License

[GPL-3.0-or-later](https://github.com/xht8723/Anime-SDF-Gen/blob/main/anime_sdf_gen/LICENSE). Maintained by [xht8723](https://github.com/xht8723).
