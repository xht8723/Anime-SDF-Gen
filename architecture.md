# Anime SDF Gen — developer architecture

The add-on runs in vanilla Blender with its bundled NumPy. It has no additional runtime dependencies.

## Boundaries

- **core** contains JSON project validation, curves and affine editing, distance transforms, threshold compilation, smoothing, projection/UV baking, numerical image codecs, and verified bundle export. It imports no Blender modules.
- **Session** coordinates the canonical project, selection, fitting, history, stage changes and save/load recovery. Launcher properties retain creation defaults; live authoring state is read directly from the project.
- **commands** owns edit transactions and shared authoring operations. A transaction captures project, selection, source reference, playback state and history. It commits one undo entry for a changed artwork, or rolls back on failure. A drag holds one transaction from press to release/cancel.
- **Preview** owns distance/mask caches, raw and filtered thresholds, cooperative jobs, the NumPy mask and revision-controlled GPU resources. The mask has no duplicate Blender image datablock.
- **ExportJob** owns progress, cancellation and results. Starting generation snapshots the project. The numerical pipeline stages and verifies the complete bundle before replacement.
- **Registry / OriginContext** track owned Blender IDs/draw handlers and the original window, scene, view layer and workspace. They never purge unrelated orphan data.
- **Editor / NativeNavigation** own the floating popup, virtual cameras, offscreen views and native navigation bridge. Shared viewport geometry is independent of the editor.
- **input / CurveInput** route events and preserve modal edit cancellation. **drawing / canvas / widgets** render views and overlays. **interface / panels / typography / theme** construct the existing layout.
- **ui / ui_guard** adapt Blender operators and dialogs to commands. Delayed submissions are bound to a session and stage; shape/point dialogs also bind their target, and export confirmations bind the project they reviewed.

## Localization

Core messages retain English templates and named arguments until presentation. Their exception categories and English diagnostics remain available to headless tools. The Blender i18n adapter resolves labels, tooltips and reports through the extension catalog, respecting independent preference flags. No localized values enter schema 4 or numerical output.

The existing session timer detects language changes and requests text redraws without invalidating preview or export computation. CJK wrapping is tested outside Blender; native property contexts and actual popup typography are checked in Blender. See [translation maintenance](i18n-development.md).

## Data flow

Source extraction → alignment/landmarks → authored curves → binary keyframe masks → signed distance interpolation → optional threshold smoothing → UV transfer → island padding → final precision/packing → verified files.

Immediate curve dragging displays authored masks. Interpolated playback uses cached thresholds through the existing preview shader. Numerical calculations remain floating point until encoding.

## Cleanup and failure handling

Session close cancels edits and cooperative jobs, removes timers, closes or restores the popup, disposes owned IDs/handlers, and clears CPU/GPU caches. Saving suspends the preview before serialization and rebuilds afterward. Failed exports retain the session and existing output files.

Transactions permit temporarily invalid contour artwork so artists can repair it; numerical validation blocks generation. Errors remain in the popup footer. No schema migrations or compatibility forwarding APIs are provided.

## Development and validation

Use Python with NumPy for numerical tests. Blender checks run only in disposable processes against a supplied fixture. The validation runner derives the version from the manifest and accepts explicit executable, fixture, output and suite options:

```powershell
python tools/validate.py --blender "C:/path/to/blender.exe" --fixture "E:/path/to/test_sdf.blend" --suite all
python tools/verify_release.py
```

Suites are core, guards, lifecycle, ui, i18n, export and package. Helpers perform filesystem/preference setup only when explicitly invoked. The GPU reference is frozen test data; tests do not execute an archived add-on or require Git history.

The extension and source archives are deterministic and contain an explicit set of code, tests and documentation. Development tools and validation artifacts are excluded. Python formatting uses Black 26.5.1 with a 100-character line length; Black is a development tool only.
