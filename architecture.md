# Anime SDF Gen — developer architecture

The add-on runs in vanilla Blender with its bundled NumPy. It has no additional runtime dependencies.

## Boundaries

- **core** contains JSON project validation, curves and affine editing, distance transforms, threshold compilation, smoothing, projection/UV baking, numerical image codecs, and verified bundle export. It imports no Blender modules.
- **Session** coordinates the canonical project, selection, fitting, history, stage changes and save/load recovery. Launcher properties retain creation defaults; live authoring state is read directly from the project.
- Setup revisits use `REORIENT` / `REFIT` in the existing `authoring.stage` field. The four displayed steps stay the same, but returning to editing preserves curves. Explicit refitting uses a deferred native confirmation bound to the reviewed project snapshot. There is no additional setting or migration.
- **commands** owns edit transactions and shared authoring operations. A transaction captures project, selection, source reference, playback state and history. It commits one undo entry for a changed artwork, or rolls back on failure. A drag holds one transaction from press to release/cancel.
- **Preview** owns distance/mask caches, raw and filtered thresholds, cooperative jobs, the NumPy mask and revision-controlled GPU resources. The mask has no duplicate Blender image datablock.
- **ExportJob** owns progress, cancellation and results. Starting generation snapshots the project. The numerical pipeline stages and verifies the complete bundle before replacement.
- Successful export retains only the committed path tuple for the launcher's completion card before session teardown. Cancellation and failure do not replace the last successful result; no preview resources or Blender IDs are retained by the card.
- **Registry / OriginContext** track owned Blender IDs/draw handlers and the original window, scene, view layer and workspace. They never purge unrelated orphan data.
- **Editor / NativeNavigation** own the floating popup, virtual cameras, offscreen views and native navigation bridge. Shared viewport geometry is independent of the editor.
- **input / CurveInput** route events and preserve modal edit cancellation. **drawing / canvas / widgets** render views and overlays. **interface / panels / shelf / typography / theme** construct the layout. The full-height sidebar groups reference controls, a flat shape list, selected-shape actions and point properties. **shape_list** owns list rows and the independent scrollbar; **shelf** owns keyframe controls and playback below the views. Shape scrolling is transient editor state, independent of sidebar and keyframe scrolling. List hit regions are clipped to the sidebar body, including when errors reserve footer space.
- **ui / ui_guard** adapt Blender operators and dialogs to commands. Delayed submissions are bound to a session and stage; shape/point dialogs also bind their target, and export confirmations bind the project they reviewed.
- **NativeUI** arms native-dialog controls on press, consumes the release, and invokes one queued action on the next session timer tick in the popup context. Cancelled or stale gestures are discarded before invocation; Blender owns interaction inside the native dialog.

## Localization

Core messages retain English templates and named arguments until presentation. Their exception categories and English diagnostics remain available to headless tools. The Blender i18n adapter resolves labels, tooltips and reports through the extension catalog, respecting independent preference flags. No localized values enter schema 4 or numerical output.

The existing session timer detects language changes and requests text redraws without invalidating preview or export computation. CJK wrapping is tested outside Blender; native property contexts and actual popup typography are checked in Blender. See [translation maintenance](i18n-development.md).

## Data flow

Source extraction → alignment/landmarks → authored curves → binary keyframe masks → signed distance interpolation → optional threshold smoothing → UV transfer → island padding → final precision/packing → verified files.

Immediate curve dragging displays authored masks. Interpolated playback uses cached thresholds through the existing preview shader. Numerical calculations remain floating point until encoding.

With `mirror_sweeps` enabled, Left → Right owns editable artwork; Right → Left is derived and its keyframe buttons are disabled. `synchronize_mirror(project)` copies only left to right, including frame additions/removals. Core mutation helpers, session edits and operator guards enforce the lock. Enabling or restoring mirroring from a right-side selection chooses the closest left progress position, with earlier-frame tie-breaking; playback still samples both directions.

UV validation permits overlaps. UV transfer keeps the last valid triangle sample at each shared texel. Confirm can re-extract a different existing bake map after checking geometry, triangle identities, pose and region against the session. Only the face UV data, source fingerprint and existing `source.uv_map` / `authoring.uv_map` fields change; face-space caches and artwork remain intact. Reference meshes retain the source's active/render UV defaults independently of the bake map.

## Cleanup and failure handling

Session close cancels edits and cooperative jobs, removes timers, closes or restores the popup, disposes owned IDs/handlers, and clears CPU/GPU caches. Saving suspends the preview before serialization and rebuilds afterward. Failed exports retain the session and existing output files.

Transactions permit temporarily invalid contour artwork so artists can repair it; numerical validation blocks generation. Errors remain in the popup footer. Current project fields and evaluated source data are explicit requirements. No schema migrations, missing-field upgrades or compatibility forwarding APIs are provided.

## Development and validation

Use Python with NumPy for numerical tests. Blender checks run only in disposable processes against a supplied fixture. The validation runner derives the version from the manifest and accepts explicit executable, fixture, output and suite options:

```powershell
python tools/validate.py --blender "C:/path/to/blender.exe" --fixture "E:/path/to/test_sdf.blend" --suite all
python tools/verify_release.py
```

Suites are core, guards, lifecycle, uv, mirror, dialogs, ux, shapes, ui, i18n, export and package. The uv suite also exports all four faces in `bugs.blend`; mirror covers the locked row at 2K/4K plus curve/full-sweep workflows. For interrupted validation, `--resume` reuses recorded successful checks only for the same runtime and commands; failed or missing checks run again, and package checks always rebuild the archives. Helpers perform filesystem/preference setup only when explicitly invoked. The GPU reference is frozen test data; tests do not execute an archived add-on or require Git history.

The extension manifest is the single source for release and installation metadata; legacy `bl_info` metadata is not shipped. The extension and source archives are deterministic and contain an explicit set of code, tests and documentation. Retired demos and validation artifacts are excluded. Python formatting uses Black 26.5.1 with a 100-character line length; Black is a development tool only.
