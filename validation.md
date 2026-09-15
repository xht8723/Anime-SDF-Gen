# Anime SDF Gen 0.14.0 — validation

Validated with vanilla **Blender 5.2.2 LTS on Windows**, September 15, 2026. Tests use disposable processes and write under `build/validation/v014`. The supplied `test_sdf.blend` remains unchanged.

## Preview restoration

The shadow preview is restored from the checksum-verified **0.10.0 extension ZIP**. This includes the projected 512-pixel mask, original warm/cool palette, smooth surface lighting that follows the sweep, shaded/flat toggle, immediate updates during dragging, and cached distance-field interpolation after editing pauses. The newer toon/UV-texture preview and its unused numerical module have been removed.

The regression test loads only the preview functions from the verified archive into the disposable test process. It compares those released functions against the current implementation using identical geometry, masks, view matrices and light positions. Both the mask arrays and rendered GPU pixels must match exactly. The installed add-on does not load or depend on the old ZIP.

| Check | Result |
|---|---|
| Numerical/project suite | 45 tests passed |
| First, middle and last keyframes | Mask data and shaded/flat GPU pixels exactly match 0.10.0 |
| Full sweep samples | Exact GPU comparison passed at 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315° and 360° |
| Lit cutout | Original projected appearance and carried light preserved |
| Drag feedback | Current mask updates during real mouse movement, without waiting for distance-field compilation |
| Drag cancellation | Escape immediately restores artwork and mask |
| Invalid ordering | Original magenta conflict overlay appears; corrected artwork clears the error and recompiles |
| Native camera/Confirm | Camera orbit preserves projection; Confirm starts 360-degree playback with the restored toggle |
| Later curve controls | Box selection, G/R/S, numeric input, snapping, remapped keys, selection, undo/redo and cancellation passed |
| Saving during a transform | Unconfirmed edit is cancelled; artwork, selection and authoring session are restored |
| Lifecycle/export | Repeated sessions, export failure/cancellation, 512-pixel export/reload, save/resume, file loading and disable passed |
| Workspace preservation | Original geometry, UVs, materials, selection and datablock counts preserved |
| Full workflow | Both rows, mirrored/asymmetric edits, Confirm/save/resume, custom output packing, export and reopening passed |
| Saved-file inspection | Separate Blender process found no owned preview datablocks |
| Packaging | Manifest validation and actual extension-namespace import passed |
| Scope audit | 12 non-preview modules and 88 non-preview methods match 0.13.0; restored rendering/mask functions match 0.10.0 |

The remaining numerical/export engine, current project schema (3), curve editing engine, source capture, native navigation and floating-window layout are preserved. No migrations, compatibility aliases or alternate preview mode were added. Full-resolution export still calculates and transfers threshold fields independently of the displayed mask.

The five tests specific to the removed live UV-texture compiler were removed with that implementation. The 45 existing numerical/project tests remain, including distance-transform reference cases, phase fidelity, independent/mirrored sweeps, cutout carry, invalid contours, UV checks, all 34 valid channel packings, 16-bit encoding and atomic output rollback.

GUI checks ran at **2560 × 1600**. This restoration does not introduce new performance claims. Full 2048/4096 exports and a 4K GUI run were not repeated; numerical/export and layout code are unchanged. Earlier evidence remains in the versioned validation folders.

Fixture SHA256:

```text
f9670911e59ddf0de95a690c8c677348b267904bd295430d0b73f2a586e7da75
```

## Evidence

These links refer to local validation artifacts under `build/`, which are not included in the repository.

- [Numerical suite](build/validation/v014/numerical.log)
- [Comparison against 0.10.0](build/validation/v014/restore-2k/preview-restore.json)
- [Restored lit cutout](build/validation/v014/restore-2k/03-restored-lit-cutout.png)
- [Restored Confirm view](build/validation/v014/restore-2k/04-restored-confirm.png)
- [Curve input and save/resume](build/validation/v014/curve-controls-2k/curve-controls.json)
- [Full sweep workflow](build/validation/v014/full-sweeps-2k/full-sweeps.json)
- [Lifecycle/export](build/validation/v014/blender_integration.json)
- [Saved-file inspection](build/validation/v014/saved_file.json)
- [Actual ZIP import](build/validation/v014/archive_import.json)
- [Source scope and release verification](build/validation/v014/release.json)

## Reproduce

Use Python with NumPy and Blender on PATH. The comparison test additionally requires `dist/anime_sdf_gen-0.10.0.zip` and its `.sha256` file. Keep the fixture unchanged and use disposable Blender processes.

```powershell
python -m unittest discover -s tests -v
python tools/package.py
blender --background --factory-startup --command extension validate dist/anime_sdf_gen-0.14.0.zip
blender --background --factory-startup --disable-autoexec test_sdf.blend --python-exit-code 1 --python tests/blender_archive.py
blender --background --factory-startup --disable-autoexec test_sdf.blend --python-exit-code 1 --python tests/blender_integration.py
blender --background --factory-startup --disable-autoexec build/validation/v014/save_while_editing.blend --python-exit-code 1 --python tests/blender_saved_check.py
```

Launch GUI tests with `Start-Process -WindowStyle Hidden`, passing these arguments. Each test quits its disposable process after completing:

```text
--factory-startup --disable-autoexec --enable-event-simulate test_sdf.blend --window-geometry 60 60 2560 1600 --python tests/blender_preview_restore.py -- restore-2k
--factory-startup --disable-autoexec --enable-event-simulate test_sdf.blend --window-geometry 60 60 2560 1600 --python tests/blender_curve_controls.py -- curve-controls-2k
--factory-startup --disable-autoexec --enable-event-simulate test_sdf.blend --window-geometry 60 60 2560 1600 --python tests/blender_full_sweeps.py -- full-sweeps-2k
```
