# Anime SDF Gen — controls and visual refresh

## Goals

Implement the seven requested UI changes without rearranging the popup's main views, panel or keyframe strip. Preserve native navigation, automatic markers, live shadow updates, and clean workspace restoration. Deliver a clean v0.6.0 extension and source package; no migrations or compatibility aliases.

## Checklist

- [x] Add a compact GPU-drawn visual system: charcoal surfaces, rounded controls, subtle borders, consistent text hierarchy, and clear hover/selection states. Keep its GPU resources session-owned.
- [x] Anchor warnings at the bottom of the right panel, independently of control scrolling. Keep long messages readable and scrollable without blocking controls.
- [x] Replace the two anatomical triangle actions with one Add triangle action. Create an enabled, closed three-point curve with smooth handles and immediate shadow updates.
- [x] Put the shaded/flat toggle beside Focus in the live preview header; use a compact icon when the header is narrow. Place the Output save icon directly beside Generate/Next, preserving the adjacent back arrow.
- [x] Give keyframe minus/plus compact square buttons and the numeric selector the remaining width, with a centered, fully visible number.
- [x] Add delayed tooltips to every custom button, including selected and disabled controls, with useful disabled-state explanations. Hide tooltips on clicks, drags, navigation, window deactivation and close.
- [x] Test actual input, smooth-triangle masks/history, warning anchoring/scrolling, tooltip timing/clipping, output dialogs, moved preview controls, native navigation and resource cleanup. Visually inspect 2K and 4K/DPI-scaled screenshots.
- [x] Update usage/validation documentation, build and verify the v0.6.0 ZIPs, and confirm the original fixture hash is unchanged.
