"""DPI-aware measurement, truncation and Chinese/Latin wrapping."""

import blf
from .viewport import scale
from .core.text import cjk, wrap_text


def measure(value, size):
    blf.size(0, size * scale())
    return blf.dimensions(0, value)[0]


def button_height(value, size):
    blf.size(0, size * scale())
    return blf.dimensions(0, value if cjk(value) else "Ag")[1]


def shorten(value, width, size):
    if measure(value, size) <= width:
        return value
    while value and measure(value + "…", size) > width:
        value = value[:-1]
    return value + "…" if value else ""


def wrap(value, width, size=12.5):
    return wrap_text(value, width, lambda part: measure(part, size))
