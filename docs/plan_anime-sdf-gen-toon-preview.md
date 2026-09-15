# Anime SDF Gen — SDF toon preview

## Goals

Make facial geometry readable in the live preview while retaining SDF control of the main lit/shadow boundary. Use the same working masks and decoded threshold maps as authoring/export. Preserve the floating popup, source assets and current project schema.

## Implementation

- [x] Replace the flat colored preview with a simple toon shader. SDF chooses the lit/shadow palette; a stationary head-space fill adds restrained tonal bands inside each region. Keep the lit and shadow brightness ranges separate, including at the nose, mouth and eye sockets.
- [x] Keep the black/white mask as the exact diagnostic view. Preserve coverage and conflict overlays, live editing, both directional maps and full 360-degree playback.
- [x] Rename the existing preview toggle to Toon preview and update its tooltip and documentation. Add no extra authoring steps or shader assignments to source materials.
- [x] Verify facial feature visibility on the fixture, classification fidelity between toon and mask views, stable fill during light rotation, opposite sweeps, cutouts, orbiting, Confirm and GPU cleanup in disposable Blender processes.
- [x] Run relevant numerical/input regressions, build version 0.12.0, validate the actual extension ZIP and source bundle, and confirm that test_sdf.blend remains unchanged.
