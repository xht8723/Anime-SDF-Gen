# Anime SDF Gen 0.15.1 — cleanup audit

## Preserved contract

The floating four-step popup, native navigation, curve controls, preview appearance, two sweeps, lit cutout carry, schema 4, channel packing, precision options and optional smoothing remain supported. Source models, authored files, existing release artifacts and the separate character-shader tools are preserved.

## Removed or consolidated

- Unused original selection/mode/viewport snapshots and the no-op restoration method.
- Duplicate Blender live-mask image and per-frame CPU image upload.
- Repeated preview-mesh initialization, redundant UV-pair tracking, unused helpers, imports and conversion parameters.
- Authoring RNA mirrors and property callbacks; native dialogs read canonical project state.
- Separate numeric and shortcut affine implementations.
- Mixed responsibilities in Session, rendering/input and the sidebar builder.
- Incidental codec re-exports, duplicate generator draining, wildcard test imports and fixtures imported from test cases.
- Hardcoded old-release paths, exact test-count gates, old ZIP code execution and Git HEAD source-identity checks.
- Packaging side effects at import and its dependency on a specific local plan document.

## Fixed behavior

- Opening another project is rejected before it can change the active session.
- Busy sessions reject artwork mutations and repeated generation requests.
- Numeric rotations preserve physical proportions on asymmetric face canvases.
- Stale dialogs cannot modify a replacement session or a different target.
- Invalid edits restore project, selection and history; successful artwork commands create one undo entry.
- Export uses a snapshot of its starting inputs.

## Verification

See [validation.md](validation.md) for completed evidence, timings and package checks. The suite now contains 67 numerical/tooling tests, plus disposable Blender integration and UI checks. All 24 frozen preview samples match exactly. Expected failures are injected in cancellation, rollback and recovery tests. These do not modify the supplied fixture.
