# Anime SDF Gen — lit cutouts

## Goals

Allow closed triangles to create lit islands inside the main shadow, matching the user's reference. Keep preview and exported lighting consistent, retain editable curves and the four-step popup, and preserve the source scene. The current magenta region is caused by a shadow-to-lit reversal between keyframes, which one directional threshold cannot encode.

## Checklist

- [x] Reproduce the reported lit triangle and distinguish mask composition from cross-keyframe encoding validation. A 512-pixel case produces a fully lit 2,286-pixel triangle, with 1,380 pixels rejected because the preceding keyframe shadows them. Evidence: `build/validation/lit-cutouts/reproduction.json`.
- [x] Resolve the output behavior with the user. Chosen: keep the RGB threshold contract and carry lit cutouts toward Front. The shared front receives both sides' cutouts.
- [x] Implement the chosen mask/encoding behavior in both immediate preview and generation. Make light versus shadow shape behavior clear in controls and tooltips.
- [x] Verify enclosed lit holes, boundary-straddling triangles, moving/disappearing patches, mirrored and independent sides, undo/redo, sweep playback and exported reconstruction. All 27 numerical tests and the real-input Blender cutout workflow passed; a 2048 × 2048 RGB16 export also passed.
- [x] Validate the floating popup and workspace cleanup in disposable Blender processes, document the output contract, and deliver verified extension/source packages. Version 0.8.0 keeps the existing RGB texture channels and decoding; the original fixture hash is unchanged.

## Implementation decisions

- Keep a cutout's editable curve in its originating keyframe. Compute its effect on earlier keyframes so moving, hiding or deleting it cannot leave stale duplicate curves.
- Apply each keyframe's layer order first. Only the surviving Lit regions carry backward; a later Shadow layer can refill a local cutout. Later-keyframe Lit regions take precedence over earlier artwork where required by the chosen threshold format.
- Use these same effective masks for direct preview, interpolated sweep, validation and export. Keep rejecting remaining nonmonotonic main boundaries or Shadow shapes, as well as invalid curves.
- Cache raw layer masks and key signed-distance caches by the effective mask, so editing a later cutout refreshes affected earlier fields.
- Label the shape modes Lit area and Shadow area and explain backward propagation in tooltips. Preserve smooth triangle geometry and existing layer-order controls.
