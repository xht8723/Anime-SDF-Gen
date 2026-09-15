# Anime SDF Gen — confirmation step

## Goals

Add a fourth Confirm step containing export settings and one large live preview. Remove the toolbar output/save control, start confirmation playback from the character's left toward the right, and select the leftmost keyframe whenever entering curve editing. Keep the floating popup, warning footer, native navigation and clean workspace lifecycle.

## Checklist

- [x] Add Confirm to the session and project stage model. Route Next from curve editing to Confirm and Back to curve editing without refitting artwork. Start editing at the left endpoint; start confirmation with an automatic left-to-right sweep.
- [x] Update all step counters to four, remove the toolbar save control, and expose destination, filename and resolution settings in the Confirm panel. Display one large preview with playback controls; retain bottom-panel warnings and tooltips.
- [x] Keep preview compilation, export/cancellation, save/resume and draft reopening functional in Confirm. Require confirmation before generation and preserve clean source/workspace ownership.
- [x] Verify real step navigation, endpoint selection, automatic playback, output controls, export failures and workspace restoration in disposable Blender processes. Inspect screenshots at 2K and 4K width.
- [x] Update usage and format documentation, package version 0.7.0, validate the extension ZIP and original fixture hash, and deliver extension and source archives.
