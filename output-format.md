# Anime SDF Gen — texture and project format

Version 0.14.0 writes configurable RGB16/grayscale16 textures and project schema 3. Each threshold map represents a complete boundary sweep. Curve selection and pending transforms are transient editor state and are not serialized into the project. The restored 0.10.0 preview projects a lit/unlit mask; its colors and smooth shading are not written into the texture data.

## Image

All outputs are non-interlaced **PNG files with 16 bits per channel**. They carry no display gamma or view transform. Load them as **Non-Color** in Blender. The two directional maps are switching thresholds derived from signed distance fields; the finished textures are not normal maps or spatial signed-distance fields.

| Logical map | Default channel | Meaning |
|---|---|---|
| `character_left` | R | Left → Right boundary sweep; light on the character's left hemisphere |
| `character_right` | G | Right → Left boundary sweep; light on the character's right hemisphere |
| `face_coverage` | B | Coverage of the selected, projectable face in UV space |

In Confirm, each logical map can use **R**, **G**, **B**, or **Separate**. An RGB channel has one owner; selecting an occupied channel swaps assignments. Multiple maps can be Separate. Packing choices are independent of authoring symmetry.

- Maps routed to RGB share `<stem>.png`. Unassigned channels contain integer zero. The packed file is omitted if all maps are Separate.
- Separate maps use single-channel grayscale16 PNGs: `<stem>_left.png`, `<stem>_right.png`, and `<stem>_coverage.png`, as selected.
- `<stem>.sdfproject.json` records every texture's channels, filename, bit depth, dimensions, colorspace and SHA256. Grayscale uses the metadata channel key `Y`; Blender exposes this same value in R, G and B when loading it.

For example, Left → B, Right → Separate, Coverage → R writes a packed file with R = coverage, G = 0, B = left threshold, plus a right-threshold grayscale file and the JSON project.

Both directional maps are baked to the selected existing UV map. Do not flip U for the right map: mirroring has already been incorporated into the authored result.

Internally, face coordinates use `u=0` at viewer left, `u=1` at viewer right, and `v=0` at the bottom. The right vector of the projection is `up × forward`, which points toward the character's left. The sidecar stores the complete orthonormal frame, center, width, and height.

## Light progress and threshold decoding

Use a normalized direction from the face toward the light and project it into the head's horizontal plane. Select the map by the light's current side of the head. Its previous motion has no effect. Look up the selected map's file and channel in the sidecar.

```text
x = dot(face_to_light, head.right)     // projection right = character left
z = dot(face_to_light, head.forward)
yaw = atan2(x, z)                      // -pi ... pi
map = character_left if x >= 0 else character_right
progress = abs(yaw) / pi               // front 0; side 0.5; back 1
```

For a light exactly above or below the head, the horizontal direction is undefined; the consuming shader must choose a fallback. This version authors horizontal lighting only.

The preview completes one orbit in 12 seconds:

| Rotation | Light position | Map and progress |
|---|---|---|
| 0° | Front | Left, 0 |
| 90° | Character left | Left, 0.5 |
| 180° | Back | Left, 1 |
| 270° | Character right | Right, 0.5 |
| 360° / 0° | Front | Left, 0 |

Between 0° and 180°, `p = angle / 180`. Between 180° and 360°, `p = (360 - angle) / 180` on the right map. Thus the return half reads the opposite authoring row from last to first while the light keeps rotating in the same direction. The primary boundary sweeps left to right; the opposite boundary sweeps right to left when its own progress increases.

For a seamless orbit, the two decoded first masks must agree at Front and the two decoded last masks must agree at Back. The editor reports endpoint differences as nonblocking seam warnings. It preserves independent artwork and allows export. Default presets have fully lit Front and fully shadowed Back, so both endpoints match.

Threshold endpoints are explicit sentinels:

- integer **0** / normalized **0.0**: always shadowed;
- integer **65535** / normalized **1.0**: always lit;
- integers **1…65534**: ordinary switching thresholds.

For normalized `T` and progress `p`, hard-shadow decoding is:

```text
shadow = (T == 0) OR ((T < 1) AND (p >= T))
```

Do not use `p >= T` alone: that would shadow the always-lit sentinel at the back endpoint. A shader can add antialiasing around interior thresholds while respecting the sentinels. Apply face coverage and the intended geometry/material restriction separately.

UV padding extends the two threshold maps into nearby empty texels using the nearest covered seed. Face coverage keeps its original mask and does not acquire a padding halo. Dilation is eight texels at 2048, scaled with output size. No averaging between islands is performed during padding. Endpoint quantization and padding happen before channel packing, so assignments cannot alter numerical values or coverage.

PNG scanlines are written top-to-bottom; internal arrays and Blender UV coordinates use a bottom-left origin. The writer flips rows exactly once. Verification reloads the PNG and checks all encoded values. The Blender integration test independently reloads the image as Non-Color and compares channel values.

All selected texture files are staged and numerically verified before the sidecar is staged and round-trip checked. Generation can be cancelled between staging chunks. The complete set is committed without yielding; a failed replacement restores the previous files and removes partial new outputs. Only configured destinations participate. Files produced by an earlier, different packing choice are not automatically deleted.

## Numerical construction

Contours are adaptively flattened to at most one quarter of a working-canvas texel of geometric error. Even-odd scanline filling combines ordered Add/Remove masks on a canvas padded by 25% of the face extent on every side.

Each row contains 2–33 ordered keyframes including progress 0 and 1. Each keyframe first combines its local layers in order. ADD unions shadow and refills any earlier light in that layer's footprint. A closed REMOVE subtracts shadow and marks an explicit lit cutout. Only lit regions remaining after all local layers carry to earlier keyframes in that same row.

For a directional keyframe `i`, let `M_i` be its local shadow mask and `L_j` the surviving explicit light on later keyframe `j`. The effective shadow mask is:

```text
S_i = M_i AND NOT (UNION of L_j for every j > i)
```

The two first keyframes are independent; neither receives cutouts from the opposite row. **Mirror Full Sweep** reflects every corresponding keyframe into the other row in head space, including its closed shapes. It never copies between different positions in the same row. Later cutouts take precedence over earlier shadow artwork. Curve data stays on the originating keyframe: propagation is derived, so editing or removing a curve cannot leave duplicate shapes behind. Immediate preview, the full orbit and export all use these effective masks.

Signed Euclidean distances are positive inside shadow. Empty/full canvases use finite signed diagonal distances. Consecutive effective masks must be nested over the projected face domain; remaining reversals from main boundaries or ADD shapes are rejected. For a pixel changing from negative distance `d0` to positive distance `d1`, between positions `p0` and `p1`:

```text
alpha = -d0 / (d1 - d0)
threshold = p0 + alpha * (p1 - p0)
```

Distances are computed in the common face plane before coverage clipping or UV transfer. UV triangles use barycentric interpolation into that plane. Front-facing depth coverage rejects hidden samples within the raster tolerance. Preview and export share this implementation at different resolutions.

The authoring preview rasterizes its current projected mask at 512 pixels. Cached threshold fields provide interpolated playback after editing pauses. This restores the preview implementation from 0.10.0 and does not change the output contract. The internal mask stores shadow, conflict and coverage in R/G/B; those diagnostic channels are never exported as threshold data. Export recalculates fields and UV transfer at its selected resolution, with the chosen output packing. Preview colors and smooth surface lighting are never baked into output files.

## Editable JSON

`.sdfproject.json` files have `format: "anime_sdf_gen"` and `format_version: 3`, with these principal sections:

- `source`: blend/object/mesh names, captured polygon IDs, region (`SELECTED` or `VERTEX_GROUP`), optional vertex-group name, frontal-subset setting, UV name, and a SHA256 of evaluated coordinates, triangles, and UVs.
- `alignment`: orthonormal head frame, center, width, and height.
- `landmarks`: normalized nose, mouth, and chin positions.
- `authoring`: `stage` (`ORIENT`, `FIT`, `EDIT`, or `CONFIRM`), `reference` (`NEUTRAL` or `MATERIAL`), initial/refit `keyframe_count` per sweep, pending orientation choices `uv_map` and `front_only`, and named surface `anchors`. Each anchor stores a world position, original triangle vertex indices, and three barycentric weights. No Blender pointer is serialized. Generated sidecars reopen in Confirm; use Back to edit their curves.
- `sweeps`: `left_to_right` and `right_to_left` arrays of complete keyframes, each with strictly increasing `progress` from 0 to 1. Independent rows can have different counts and intermediate positions.
- `mirror_sweeps`: links corresponding artwork and keyframe positions across the two rows. Re-enabling it reflects the current row into the opposite row. There is no shared frontal keyframe or pair-count setting.
- `contours`: main boundary followed by ordered closed shapes, with enabled state and ADD/REMOVE operation (Shadow area / Lit area in the UI). Only locally authored curves are stored; carried light is derived with the rule above.
- `points`: normalized positions, AUTO/CORNER/FREE mode, and relative incoming/outgoing handle vectors.
- `settings`: preview/output resolution, padding, output stem, and `packing`, a map from the three logical map names to `R`, `G`, `B`, or `SEPARATE`. Rotation and playback are transient UI state and have no effect on map meanings.
- `encoding`: numerical PNG format, Non-Color, unused-channel fill and endpoint conventions; independent of the chosen channels.
- `textures`: a list present after generation. Each entry has `file`, `sha256`, `width`, `height`, `bits`, `colorspace`, `color_type` (`RGB` or `GRAYSCALE`), and `channels`. Channel entries map `R`/`G`/`B` or grayscale `Y` to logical map names. This describes the files produced by that export; `settings.packing` controls the next generation.

The project contains no executable code, Blender ID pointers, or baked mesh. The source model is required to reopen it. References are checked before reopening and again before generation; explicit relinking recomputes the source reference and fitting frame.

Authoring data is authoritative: the texture can be regenerated even if its PNG is missing. Unknown project versions, malformed contours, invalid keyframe positions, or non-finite coordinates are rejected.

## Source validation and session state

Only the exact format identifier and version above are accepted. Other schemas are rejected with a request to create a new project. There is no conversion path. Opening or rejecting a file never modifies it.

Explicit relinking captures the current active selection or vertex group and returns to `ORIENT`. Ordinary reopening and generation reject source fingerprint or group-membership changes. Changes to the user's live face selection alone do not alter the captured polygon set.

Window IDs, internal workspace/screen IDs, GPU resources, and live Blender objects are session-only. During an ordinary `.blend` save, the popup's divider, focus, cameras, rotation, selection and history are held in memory while its window and data are removed, then rebuilt afterward. Recovery and explicit drafts use the same external JSON format. Current automatic recovery uses the separate `anime_sdf_gen/v3/drafts/` directory.
