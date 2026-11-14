# Anime SDF Gen 0.20.0 — validation

## GitHub release and Chinese wording — November 13, 2026

The final 0.20.0 release uses `build/validation/release-0.20.0` for a complete run of the 32-check release matrix, including 79 numerical/tooling tests, the 448-template translation audit, real 2K/4K popup workflows, lifecycle checks, model exports, and package validation. The release verifier matches archive contents to the current source and checks the preserved model and authored-file hashes. Blender checks run only in disposable Blender 5.3.0 processes on Windows.

The Chinese wording revision changes 173 display strings while retaining all 448 English source templates and schema 4. Labels, tooltips, disabled reasons, errors, progress messages, and the Chinese guide use consistent artist-facing terminology. Its focused validation passed nine localization unit tests, native translation/Unicode/export checks, and both localization and shape-sidebar workflows at 2K and 4K. Switching languages preserves artwork, custom names, selection, history, playback, caches and generated texture data.

The final release assets include the installable extension ZIP, source ZIP and their SHA-256 files. Local models, recovery drafts, validation artifacts, the authored README draft, and the retired toon demo are excluded. The working tree and previous 0.20.0 archives are preserved in the release evidence's `baseline` directory.

## Curve and point sidebar — November 13, 2026

Evidence is under `build/validation/0.20.0`. The 32-check release matrix includes real 2K/4K sidebar workflows: list selection, independent list and property scrolling, clipped hit regions, attached shape and point actions, main-boundary protection, automatic row reveal, mirroring, undo/redo, focus/stage changes and English/Chinese layout. Existing artist, native-dialog, navigation, lifecycle and export checks remain in the matrix.

The sidebar extends from the global toolbar to the bottom of the popup. The timeline stays below the authoring/preview views and does not overlap the sidebar. Source models and the authored README draft are verified against `baseline/baseline.json`; no project schema changes are required. Validation runs only in disposable Blender processes. See [full run](build/validation/0.20.0/run-all.json) and [release verification](build/validation/0.20.0/release.json).

## Shape dock — November 13, 2026

Evidence is under `build/validation/0.19.0`. The release matrix requires 32 checks, including real shape-dock workflows at 2K and 4K. These exercise list selection, mouse-wheel and scrollbar dragging, attached actions, main-boundary protection, automatic row reveal from canvas/frame selection, mirrored edits, undo/redo, stage/focus changes, error placement and Chinese layout. Existing artist, native-dialog, curve, navigation, localization, lifecycle and export workflows remain in the matrix.

Validation runs only in disposable Blender processes; source model hashes and the authored README draft are recorded and verified against `baseline/baseline.json`. No project schema or authored data changes are required for this layout. See [full run](build/validation/0.19.0/run-all.json) and [release verification](build/validation/0.19.0/release.json).

## Artist workflow — November 13, 2026

Current evidence is under `build/validation/0.18.0`. Validation uses disposable Blender 5.3.0 processes with factory startup, isolated draft/temp folders, and no writes to the source models. The release verifier requires **30 checks**, including the two artist-workflow cases, **79 numerical/tooling tests**, and the **447-template** English/Chinese catalog.

The artist workflows at **2560 × 1600** and **3840 × 2043** (requested height 2160) exercise:

- First-frame guidance, neighboring-frame legends, light-angle tooltips, persistent mirrored-row labels, and separate editing/playback captions, including the unlocked right sweep's front endpoint.
- Real held presses and releases for shape renaming and explicit refitting. Rename edits pass through native text controls; confirmation dialogs survive release and idle, cancel normally, and accept native confirmation clicks.
- Mirrored names, rename undo/redo, invalid names and stale submissions, selected-point scope, and current-schema draft/reopen behavior.
- Returning from changed setup without rebuilding curves; returning through orientation; explicit refit cancellation, stale snapshot rejection, replacement, and undo/redo.
- Successful export retains the verified output paths after popup closure and project reopening. Cancelled generation leaves the completion record unchanged.

The broader matrix covers source/UV validation, all four `bugs.blend` faces at 512 pixels, mirror locking, native dialogs, navigation and curve editing, frozen preview samples, localization, save/resume and window cleanup, output precision, larger exports, and manifest/ZIP import checks. See [full run](build/validation/0.18.0/run-all.json) and [release verification](build/validation/0.18.0/release.json).

The initial working tree is archived under `baseline/working-tree.zip`. `bugs.blend` was saved externally after that initial snapshot and before any validation process; its newer bytes were retained. Both the initial and subsequent preservation hashes are recorded in `baseline`. `test_sdf.blend` and the authored README draft are checked unchanged.

## Release cleanup — November 13, 2026

Validation for the cleanup release uses disposable **Blender 5.3.0** processes on Windows. Current evidence is under `build/validation/0.17.0`; the pre-audit source and authored-file hashes are preserved in its `baseline` folder. See [cleanup-audit.md](cleanup-audit.md) for the removal decisions and retained behavior.

The full release run passed **28 checks**, including **79 numerical/tooling tests** and the **412-template** translation audit. Missing current-schema fields and non-boolean contour visibility are rejected without mutation or default filling. Source, guard and lifecycle checks pass; all four `bugs.blend` faces export successfully.

All **24 frozen preview samples** match exactly. Native-dialog, mirrored-sweep, output-control and English/Chinese workflows pass at **2560 × 1600** and **3840 × 2043** (requested height 2160). Curve editing, navigation, sliders, 360° playback, draft reopening and save/resume remain working. PNG8/16 and FLOAT EXR32 precision, 2048-pixel fixture export with independent Blender reload, and 4096-pixel filtering/codecs pass. The extension manifest and actual ZIP import under a Blender extension namespace pass without legacy install metadata.

Both model files and the authored README draft match their pre-audit hashes. The retired toon demo copies match the originals byte for byte. Release verification requires the new UV, native-dialog and mirror suites and checks archive members against the current source.

Evidence: [full run](build/validation/0.17.0/run-all.json), [audit and preservation](build/validation/0.17.0/audit-results.json), [release verification](build/validation/0.17.0/release.json).

## Mirrored sweep lock — November 13, 2026

Validated in disposable **Blender 5.3.0** processes on Windows. Evidence is under `build/validation/mirror-lock`; schema 4 is unchanged.

- **78 numerical/tooling tests** pass. Mirroring always copies Left → Right into Right → Left, including curves, handles, order, progress positions and frame counts. Locked mutations are atomic; refitting, endpoint protections and the 33-frame limit pass.
- Real popup workflows pass at **2560 × 1600** (scale 1.0) and **3840 × 2043** (scale 1.5, requested height 2160). Right-row clicks remain disabled. Direct selection/edit operators are rejected without changing artwork or selection. English/Chinese lock tooltips render in both sizes.
- Left insertion, deletion, copying and handle edits immediately update right-row data and buttons. Enabling from an independently edited right row with unequal frame counts preserves the left sweep, selects the nearest left frame (earlier on a tie), and selects its main boundary’s first point. Unlocking, undo/redo and stale-dialog rejection pass.
- Automatic drafts, explicit project reopening and actual Blender save/resume retain mirrored artwork and the lock. Both preview halves, right-row playback highlighting and 512-pixel exports pass. Existing curve editing, native navigation, sliders and full 360° orbit workflows also pass.
- The edit-guard suite, **410-template** translation audit and English/Chinese runtime/UI suites pass, including 2K/4K language switching, save/resume and reopening.
- Both `bugs.blend` and `test_sdf.blend` retain the SHA256 values recorded below. Existing working-tree changes and authored files are preserved.

Evidence: [run summary](build/validation/mirror-lock/summary.json), [numerical](build/validation/mirror-lock/run-core.json), [2K/4K mirror and curve workflows](build/validation/mirror-lock/run-mirror.json), [guards](build/validation/mirror-lock/run-guards.json), [localization](build/validation/mirror-lock/run-i18n.json).

## UV maps and native dialogs — November 13, 2026

Validated in disposable **Blender 5.3.0** processes on Windows. Evidence is under `build/validation/uv-dialog-update`. No source `.blend` was saved or modified.

- **77 numerical/tooling tests** pass, including overlap acceptance, last-valid-sample overwrite at shared texels, occluded-sample preservation, and retained invalid-input checks.
- Two distinct bake layouts produce different 512-pixel placements and saved UV metadata. Switching preserves artwork, fit, selection, history, playback, preview caches and the source/reference active and render UV defaults (also tested with different active and render maps).
- Invalid/missing maps, changed geometry/pose/triangle identities/region, stale stages/sessions, cancellation and busy submissions are rejected without partial UV changes. Draft and project reopening retain the chosen map.
- Native-dialog workflows pass at **2560 × 1600** and **3840 × 2160** requested window sizes, with UI preferences 1.0 and 1.5: long/rapid presses, release outside, Escape/right-click/focus loss, nested UV search and resolution dropdown, numeric/text acceptance, file-browser cancellation, overwrite cancellation and real export. Curve dragging, undo, sliders and viewport navigation work afterward.
- Blender's `event_simulate` accepts press/release events but does not generate `DOUBLE_CLICK`. That one event tag is supplied at the curve-input boundary; its opening press and subsequent release still pass through the popup input path. Dialog tests do not substitute direct operator execution for clicks.
- All **24 frozen preview samples** still match. Source, edit-guard, lifecycle, curve, full-sweep and preview-interaction suites pass. Bake-map save/resume passes at 2K and 4K. The **409-template** translation audit and English/Chinese runtime/UI checks pass at both sizes.

All four `bugs.blend` faces export at **512 × 512** with their active maps and frontal filtering:

| Face | Bake UV | Covered texels |
|---|---|---:|
| hana_face | UVMap | 136,438 |
| amiya_face | UVMap | 20,395 |
| genshin_face | UVMap | 92,210 |
| avywen_face | UV0 | 120,635 |

Evidence: [UV selection](build/validation/uv-dialog-update/uv-selection/uv-selection.json), [four-face exports](build/validation/uv-dialog-update/bugs-export/bugs-export.json), [2K dialogs](build/validation/uv-dialog-update/native-dialogs-2k/native-dialogs.json), [4K dialogs](build/validation/uv-dialog-update/native-dialogs-4k/native-dialogs.json).

Preserved SHA256 values:

```text
bugs.blend      7c9bf4500068957ab74eb46a5263bc1cfea62d3e776b2e7d91040b6ccbce876b
test_sdf.blend  f9670911e59ddf0de95a690c8c677348b267904bd295430d0b73f2a586e7da75
```

## Previous release baseline

Validated with vanilla **Blender 5.2.2 LTS on Windows**, September 15, 2026. All Blender checks use disposable processes. Evidence is under `build/validation/0.16.0`; the original `test_sdf.blend` is unchanged.

## Results

The complete release run passed **22 checks**, including **76 numerical/tooling tests**. The captured 0.15.1 baseline passed 67 tests.

| Check | Result |
|---|---|
| Translation catalog | **408 templates**; marked source coverage, duplicates, unused entries and named-placeholder agreement passed |
| Native controls | Add-on context verified on operators/panels and **24 named RNA properties**; create/save notifications respect report preferences |
| Language behavior | English, Simplified Chinese, Automatic and unsupported-language fallback passed; all eight interface/tooltip/report flag combinations passed |
| Live switching | Idle, playback, retained warnings, a pending dialog and active generation passed; artwork, selection, history, playback and jobs remain intact |
| Cache isolation | Locale refresh preserves field/threshold identities, mask revisions, GPU texture identity and upload revision |
| Chinese typography | Launcher, all four steps, markers, dialogs, long tooltips, disabled reasons, warnings and mixed-language paths inspected at 2K/4K |
| Language-independent data | Chinese object/group/UV names and paths passed; PNG8, PNG16, EXR32 and sidecars are byte-identical across English and Chinese |
| Translation lifecycle | Repeated enable/disable, partial-registration failure, Chinese save/resume, project reopening and active-session disabling passed |
| Edit guards | Rejected opens, busy transforms, repeated generation, stale submissions, export snapshots, affine equivalence and rollback passed |
| Preview appearance | All **24 frozen GPU samples**, masks and threshold arrays match exactly |
| Interaction/workflow | Native navigation, G/R/S, box selection, dragging, undo/redo, both sweeps, mirrored artwork, carried cutouts, 360° playback and four steps passed |
| Precision/packing | PNG8, PNG16 and FLOAT EXR32; all 34 RGB/Separate routings per depth, sentinels, orientation and binary coverage passed |
| Export/recovery | Independent Blender Non-Color reload, smoothing/debounce, stale cancellation, verification/replacement failures and prior-file preservation passed |
| Workspace lifecycle | Finish/cancel, save failure/resume, reload, disabling, native popup close and last-window cleanup passed; independent saved-file reload contains no preview assets |
| Packaging | Manifest validation, extension-namespace ZIP import, deterministic archives and current-source verification passed |

The project schema remains **4**, and the texture contract and existing preview shader are unchanged. Language is presentation state; it is not serialized into projects.

## Performance and preservation

| Measurement | 0.15.1 | 0.16.0 |
|---|---:|---:|
| 512-pixel CPU mask update, median | 1.217 ms | 1.182 ms |
| Actual two-view curve dragging, median frame | 23.275 ms | 24.076 ms |
| 2048 EXR32 fixture export, smoothing 8 | 59.01 s | 59.30 s |

The drag check remains above the 30 FPS target on this workstation. CPU mask-update timings are not complete frame timings. The numerical routines are unchanged apart from deferred messages; exact arrays and rendered samples remain the correctness reference.

In the same running editor, median complete redraws measured **16.58 ms English / 16.60 ms Chinese at 2K**, and **16.59 ms / 16.63 ms at 4K**. Live locale changes cause no distance-field rebuild or texture upload. These measurements show no material interaction regression; operating-system scheduling and GPU load affect individual timings.

The full-resolution fixture export includes a carried lit cutout and independent Blender reload. Its EXR SHA256 is identical to 0.15.1:

```text
ddb5e617c0b70e1480b212acf506b79cc12dcab7104de675d76e93f369ab6521
```

The 4096 synthetic filter/codec check records cooperative step timings in `large-output/large-output.json`. Source validation and some allocations remain synchronous, so full-resolution generation does not promise a fixed UI frame rate. Uncompressed 4096 RGB EXR is about 192 MiB.

UI checks use **2560 × 1600 at scale 1.0** and **3840 × 2043 at scale 1.5**. Blender clamps the requested 2160-pixel window height on this display. Frozen GPU pixels are exact on this Blender/GPU configuration; another graphics backend may require a reviewed reference capture.

The initial working tree is preserved in `baseline/working-tree.zip` with `baseline/baseline.json`. The original model, authored README draft, separate character-shader tools and all **31 historical release archives** match their recorded hashes.

Fixture SHA256:

```text
f9670911e59ddf0de95a690c8c677348b267904bd295430d0b73f2a586e7da75
```

## Evidence

Build evidence is excluded from the source ZIP.

- [Complete run](build/validation/0.16.0/run-all.json)
- [Numerical tests](build/validation/0.16.0/numerical.log)
- [Native i18n and Unicode export](build/validation/0.16.0/i18n-runtime/i18n-runtime.json)
- [2K i18n](build/validation/0.16.0/i18n-2k/i18n-ui.json)
- [4K i18n](build/validation/0.16.0/i18n-4k/i18n-ui.json)
- [Chinese curve editor](build/validation/0.16.0/i18n-4k/03-curves-zh.png)
- [Chinese Confirm and tooltip](build/validation/0.16.0/i18n-4k/08-smoothing-tooltip-zh.png)
- [Edit guards](build/validation/0.16.0/guards/guards.json)
- [Frozen preview](build/validation/0.16.0/preview-reference/preview-reference.json)
- [Full-sweep interaction](build/validation/0.16.0/full-sweeps-2k/full-sweeps.json)
- [Workspace lifecycle](build/validation/0.16.0/integration/blender_integration.json)
- [Native/last-window cleanup](build/validation/0.16.0/window-lifecycle/window-lifecycle.json)
- [Precision and recovery](build/validation/0.16.0/precision/precision.json)
- [2048 fixture export](build/validation/0.16.0/full-export/export_2048_32_8.json)
- [4096 filtering/codecs](build/validation/0.16.0/large-output/large-output.json)
- [Preservation comparison](build/validation/0.16.0/preservation.json)
- [ZIP import](build/validation/0.16.0/archive/archive_import.json)
- [Release audit/checksums](build/validation/0.16.0/release.json)

## Reproduce

Use Python with NumPy. The runner derives the release from the manifest and accepts `core`, `guards`, `lifecycle`, `uv`, `mirror`, `dialogs`, `ui`, `i18n`, `export`, `package` and `all`.

```powershell
python tools/check_i18n.py
python tools/validate.py --blender "C:/path/to/blender.exe" --fixture "E:/path/to/test_sdf.blend" --suite all
python tools/verify_release.py --fixture "E:/path/to/test_sdf.blend"
```

Use `--output-dir` for alternate validation evidence, and `--evidence-dir` for release verification. Each check records the runtime digest and rejects changes during the check. Final verification requires current successful evidence, verifies every archive member against the workspace and installed test copy, and checks the preserved baseline hashes. No exact test-count assertion or archived-code execution is required.
