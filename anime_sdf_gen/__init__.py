"""Anime SDF Gen. Blender imports are deferred for independent numerical tests."""

bl_info = {
    "name": "Anime SDF Gen",
    "author": "xht8723",
    "version": (0, 16, 0),
    "blender": (5, 2, 0),
    "doc_url": "https://github.com/xht8723",
    "location": "3D View > Sidebar > Anime SDF Gen",
    "category": "Material",
}


def register():
    from . import i18n, ui

    i18n.register()
    try:
        ui.register()
    except Exception:
        i18n.unregister()
        raise


def unregister():
    from . import i18n, ui

    try:
        ui.unregister()
    finally:
        i18n.unregister()
