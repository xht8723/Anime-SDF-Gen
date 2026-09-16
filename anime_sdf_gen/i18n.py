"""Blender presentation adapter for the shared, locale-independent messages."""

import bpy
from .catalog import ENTRIES
from .core.messages import CONTEXT, Message, Joined, Literal

CATALOG = {"zh_HANS": {(CONTEXT, source): target for source, target in ENTRIES}}
_registered = False
launcher_notice = ""


def _present(value, translator):
    if isinstance(value, Literal):
        return str(value)
    if isinstance(value, (Message, Joined)):
        return value.render(lambda text: translator(text, CONTEXT))
    return translator(str(value), CONTEXT)


def iface(value):
    return _present(value, bpy.app.translations.pgettext_iface)


def tip(value):
    return _present(value, bpy.app.translations.pgettext_tip)


def report(value):
    return _present(value, bpy.app.translations.pgettext_rpt)


def signature():
    view = bpy.context.preferences.view
    return (
        bpy.app.translations.locale,
        view.use_translate_interface,
        view.use_translate_tooltips,
        view.use_translate_reports,
    )


def register():
    global _registered
    bpy.app.translations.register(__package__, CATALOG)
    _registered = True


def unregister():
    global _registered, launcher_notice
    if _registered:
        bpy.app.translations.unregister(__package__)
        _registered = False
    launcher_notice = ""
