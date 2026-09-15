"""Anime SDF Gen. Blender imports are deferred for independent numerical tests."""
bl_info = {"name": "Anime SDF Gen", "author": "xht8723",
           "version": (0, 14, 0), "blender": (5, 2, 0),
           "doc_url": "https://github.com/xht8723",
           "location": "3D View > Sidebar > Anime SDF Gen", "category": "Material"}


def register():
    from . import ui
    ui.register()


def unregister():
    from . import ui
    ui.unregister()
