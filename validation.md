# Anime SDF Gen 0.16.0 — validation

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

Use Python with NumPy. The runner derives the release from the manifest and accepts `core`, `guards`, `lifecycle`, `ui`, `i18n`, `export`, `package` and `all`.

```powershell
python tools/check_i18n.py
python tools/validate.py --blender "C:/path/to/blender.exe" --fixture "E:/path/to/test_sdf.blend" --suite all
python tools/verify_release.py --fixture "E:/path/to/test_sdf.blend"
```

Use `--output-dir` for alternate validation evidence, and `--evidence-dir` for release verification. Each check records the runtime digest and rejects changes during the check. Final verification requires current successful evidence, verifies every archive member against the workspace and installed test copy, and checks the preserved baseline hashes. No exact test-count assertion or archived-code execution is required.
