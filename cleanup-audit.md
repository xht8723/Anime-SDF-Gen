# Anime SDF Gen 0.17.0 — cleanup audit

Audited the runtime package, numerical core, release tooling and test entry points on November 13, 2026. The audit combined AST/reference scans with caller review, Blender registration/lifecycle review and behavioral validation. Dynamically registered callbacks were checked against their registrations rather than classified as dead solely from textual references.

## Removed or consolidated

- Removed legacy `bl_info` install metadata. `blender_manifest.toml` is the single source for extension identity, supported Blender version and release version. Archive validation reads that manifest.
- Removed defaults that silently accepted missing contour visibility, source-region settings, landmarks, anchors or partial save/resume state. Schema 4 requires its current fields; incomplete records fail clearly instead of being upgraded or filled in. No migrations, alternate project loaders or compatibility aliases were added.
- Made evaluated `FaceSource` data required. Removed fallback UV/material data paths that extraction never produced. UV coordinates are extracted once per map and the selected bake map reuses that array.
- Removed unused source-capture overrides and the unused object override on saved-source loading.
- Removed unused render-history buffers, draw-duration state, intermediate transform state, sidebar locals, a padding local and unused test imports.
- Initialized transient state explicitly instead of repeatedly inventing defaults through attribute lookups. Kept lifecycle checks for Blender objects that can actually disappear during close, disable or failed initialization.
- Shared clipped control hit testing between ordinary controls and deferred native-dialog launches. Removed duplicate slider geometry, tooltip hit testing and a repeated camera update.
- Removed redundant session-existence branches after successful operator guards and the unused error-report context argument.
- Expanded release verification to require UV-selection, four-face export, native-dialog and mirrored-sweep checks.

## Retired standalone demo

At the user's request, `tools/setup_character_toon.py` and `tests/blender_character_toon.py` were retired from the active codebase. They depended on schema 2, 90-degree sweeps, a specific character scene and historical output paths. Exact, hash-verified copies are under `build/retired/character-toon`; the audit's initial working-tree ZIP also preserves them. The obsolete packaging exclusion was removed. No character `.blend` was edited or deleted.

## Retained intentionally

- The floating four-step popup, native navigation, curve controls, face-space preview, lit cutout carry, full orbit, locked mirrored sweep, bake UV selection, permitted UV overlap, precision/packing and smoothing.
- Blender callbacks, registration-failure cleanup, transaction rollback, cancellation, source fingerprint checks and native-window recovery. These handle current application behavior.
- English fallback for unsupported locales and independent translation preferences.
- Synchronous numerical helpers and image readers used by numerical tests, batch validation and independent output verification. They are current callers of the cooperative implementation, not legacy implementations.
- Schema 4 and existing texture conventions. Complete current-schema projects remain usable; earlier schemas and incomplete records are rejected without conversion.

## Evidence and preservation

The pre-audit source snapshot and preservation hashes are under `build/validation/0.17.0/baseline`. Validation uses disposable Blender processes; artifacts stay under `build/validation/0.17.0`. Existing authored files, working-tree changes and historical release artifacts are preserved. See [validation.md](validation.md) for results and [architecture.md](architecture.md) for current ownership boundaries.
