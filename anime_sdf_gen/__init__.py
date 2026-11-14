"""Anime SDF Gen. Blender imports are deferred for independent numerical tests."""

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
