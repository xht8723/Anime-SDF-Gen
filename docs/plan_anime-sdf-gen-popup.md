# Anime SDF Gen — clean popup revision

The user rejected the workspace-style editor. A floating Blender window is acceptable only when Blender's own workspace tabs, menus, editor headers, and unrelated sidebar UI are hidden. The popup must contain the add-on's controls and views. Migration and backward compatibility are no longer requirements; reworks start with a clean application state.

## Implementation

- [x] Prove a floating window with hidden Blender chrome in a disposable process, including independent preview data and an unchanged original window.
- [x] Replace the workspace-style presentation with an add-on-only popup: branded header/actions, reference/curve view, orbitable inspection view, dedicated controls, phase shelf.
- [x] Preserve precise surface fitting, full-size curves, live masks, numeric editing, shape/layer/phase actions, and local history using the current engine.
- [x] Adopt `anime_sdf_gen` as the package/operator/extension namespace. Remove legacy source properties, aliases, migration code, and compatibility tests. Use only the current project schema and a fresh recovery namespace; do not convert or delete old user-authored files.
- [x] Verify popup input, resize, clean finish/discard, save/load/disable recovery, and original scene/data preservation. Verify visible UI by screenshot, not just window creation assertions.
- [x] Update installation/usage/format documentation and produce a fresh extension/source package with measured validation results.

The supplied test scene remains unchanged. Keep the existing RGB16 encoding because it remains the current output design, not as a backward-compatibility requirement. Native Blender dialogs for the add-on's own numeric fields and file pickers are acceptable; generic Blender workspace/editor chrome is not part of the popup.
