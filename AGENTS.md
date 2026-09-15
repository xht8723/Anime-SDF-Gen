# Anime SDF Gen project instructions

- Reworks start from a clean application state. Do not add or maintain project migrations, legacy loaders, compatibility aliases, obsolete settings, or old-version upgrade support unless the user explicitly requests it.
- Preserve the user's source models and authored files. A clean revision does not authorize deleting user data; old project schemas may be rejected with a clear message.
- The authoring UI is a floating Blender popup containing only Anime SDF Gen controls and views. Hide Blender workspace tabs, main menus, editor headers, and unrelated sidebar tabs. Do not substitute a visible Blender workspace layout.
- Keep `test_sdf.blend` unchanged; run destructive or UI lifecycle tests only in disposable Blender processes and put validation artifacts under `build/validation`.
