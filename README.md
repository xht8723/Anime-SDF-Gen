# Anime SDF Gen

Create anime face-shadow threshold textures in a floating Blender window, using editable Bézier curves and landmarks placed on the model. Setup uses one large view; curve editing adds a live shadow view. Blender's workspace tabs, menus, editor headers, and sidebars are hidden inside the popup.

Version **0.14.0** · Maintainer: [xht8723](https://github.com/xht8723) · Blender **5.2 LTS**, Windows.

**Select face → Create → orient → place markers → adjust curves → Confirm → Generate & Finish.**

- [Installable extension](https://github.com/xht8723/sdf_gen/releases/download/v0.14.0/anime_sdf_gen-0.14.0.zip)
- [Source and tests](https://github.com/xht8723/sdf_gen/releases/download/v0.14.0/anime_sdf_gen-0.14.0-source.zip)
- [Release notes and checksums](https://github.com/xht8723/sdf_gen/releases/tag/v0.14.0)
- [Usage](docs/usage.md)
- [Texture and project format](docs/output-format.md)
- [Validation](docs/validation.md)
- [Full sweeps and 360° implementation plan](docs/plan_anime-sdf-gen-full-sweeps.md)
- [Curve controls implementation plan](docs/plan_anime-sdf-gen-curve-controls.md)
- [Preview restoration plan](docs/plan_anime-sdf-gen-restore-preview.md)

Choose the current Edit Mode selection or a vertex group. Each step has a short guide beside its counter. Nose, mouth-center and chin markers start on the face, ready to drag. The popup uses rounded controls, clear selection states and delayed tooltips, including explanations for disabled buttons. The keyframe count has a wide centered number and compact minus/plus buttons.

Navigation uses Blender's native keymap and preferences. In curve editing, the reference view shows facial features and the live shadow view orbits independently. Adjust the divider, use Focus to enlarge a view, and select keyframes in the two labelled **Left → Right** and **Right → Left** boundary-sweep rows. Each row starts with 2–33 keyframes, default nine; odd and even counts work. **Mirror Full Sweep** links corresponding artwork across the rows. Unlink it to edit each sweep independently, including its keyframe count.

Select points with **B** box selection or **Shift-click**, then use **G / R / S** to move, rotate or scale the selection. **X / Y** constraints, numeric entry, **Shift** precision and **Ctrl** snapping work on the fixed face plane. Selection and transform shortcuts follow Blender's active curve and modal key bindings. **Esc** cancels the entire edit, including its mirrored result.

The shadow preview restores **0.10.0's appearance and behavior**. Its projected 512-pixel mask updates immediately during curve editing. **Shaded preview** uses the original warm/cool colors and smooth lighting that follows the sweep; **Flat mask** shows black and white. Distance-field interpolation is cached after editing for continuous playback. Export still recomputes at the selected output resolution. The later box selection, G/R/S shortcuts, workflow and output controls remain available.

**Clean Face** starts with straight boundaries crossing the full face. **Nose Accent** fits a shaped profile to the markers. **Add triangle** creates a smooth three-point closed curve with an immediate shadow update. Select **Lit area** to carve a bright patch inside the shadow, or **Shadow area** to darken it. Lit cutouts carry to earlier keyframes only within their own sweep, retaining one threshold per light direction. Mirroring reflects the entire sweep into its counterpart. Warnings stay in a scrollable footer at the bottom of the right panel.

Curve editing opens at keyframe 1 of Left → Right. **Play 360°** and the progress bar rotate the light **Front → character left → Back → character right → Front**, looping continuously. The return half samples the opposite sweep from last to first. **Next Step** opens **4 / 4 — Confirm**, with one large preview and automatic rotation. Choose the save location, file name, resolution and output packing in its right panel. Each map can use any **R / G / B** channel or **Separate**. **Generate & Finish** and the adjacent back arrow complete the flow.

Generate writes the selected 16-bit RGB and/or individual grayscale PNGs, plus an editable JSON project that records their channel meanings. Default packing is Left → R, Right → G, Coverage → B. The complete file set is verified and committed together, then temporary preview assets are removed and the popup closes. The original window remains available throughout authoring. No shader is assigned automatically.

The extension, Python package, and operator namespace are `anime_sdf_gen`. Only the documented current project schema is accepted; there is no migration code. Existing authored files are preserved.

## Development

Blender supplies Python and NumPy; the add-on requires no additional installation. For development commands, use Python with NumPy:

```powershell
python -m unittest discover -s tests -v
python tools/package.py
```

- `anime_sdf_gen/core/`: independent distance fields, masks, threshold compilation, UV transfer, serialization, and verified export.
- `source.py`: generic selection/group capture, evaluation, and source fingerprints.
- `session.py`: preview ownership, jobs, surface fitting, history, recovery, and cleanup.
- `editor.py`: floating window lifecycle, hidden native UI, and resizable views.
- `navigation.py`: Blender navigation keymap/operators and native camera projection.
- `curve_input.py` / `core/editing.py`: active key bindings, box selection and affine edits of session-owned curve points.
- `drawing.py`: GPU rendering, projected controls, picking, and guarded popup input.
- `interface.py`: step guides, adjacent back/next actions, two keyframe rows, rotation slider and controls.
- `widgets.py` / `tooltips.py`: batched rounded UI drawing and contextual hover explanations.
- `ui.py`: launcher, authoring actions, and add-on settings/file dialogs.

Tests use disposable Blender processes and write under `build/validation/v014`. The supplied `test_sdf.blend` stays unchanged and is excluded from release ZIPs. Automatic UV generation, other projection directions, geometry-derived presets, and character-shader integration remain outside this release. The [format guide](docs/output-format.md) documents map selection by head-relative light direction and the front-to-back progress mapping.
