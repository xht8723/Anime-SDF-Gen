"""Locale-independent messages. Numerical code never imports Blender."""

from dataclasses import dataclass
import re

CONTEXT = "Anime SDF Gen"


@dataclass(frozen=True)
class Message:
    template: str
    values: tuple = ()

    def render(self, translate=lambda value: value):
        template = translate(self.template)
        if not self.values:
            return template
        return template.format(
            **{
                name: value.render(translate) if isinstance(value, (Message, Joined)) else value
                for name, value in self.values
            }
        )

    def __str__(self):
        return self.render()

    def __bool__(self):
        return bool(self.template)


@dataclass(frozen=True)
class Joined:
    parts: tuple
    separator: str = ", "

    def render(self, translate=lambda value: value):
        return self.separator.join(
            part.render(translate) if isinstance(part, (Message, Joined)) else str(part)
            for part in self.parts
        )

    def __str__(self):
        return self.render()


class Literal(str):
    """User-owned text must not be looked up in a translation catalog."""


def raw(value):
    return Literal(str(value))


def msg(template, **values):
    return Message(template, tuple(values.items()))


def mark(value):
    """Mark a canonical label for extraction without translating project data."""
    return value


class MessageException:
    def __init__(self, template, **values):
        self.message = msg(template, **values)
        super().__init__(str(self.message))


class UserError(MessageException, ValueError):
    pass


class FileError(MessageException, OSError):
    pass


class AppError(MessageException, RuntimeError):
    pass


def diagnostic(error):
    if isinstance(error, Message):
        return error
    if isinstance(error, MessageException):
        return error.message
    if isinstance(error, BaseException):
        return msg("An unexpected error occurred: {details}", details=str(error))
    return (
        msg(str(error))
        if error
        else msg("The edit could not be completed. You can continue editing.")
    )


def contour_label(name):
    """Present reserved generated names; never rewrite the stored name."""
    match = re.fullmatch(r"(Main boundary|Triangle)( [2-9][0-9]*| 1[0-9]+)?((?: copy)*)", name)
    if not match or (match[1] == "Main boundary" and match[2]):
        return raw(name)
    value = msg(mark("Main boundary") if match[1] == "Main boundary" else mark("Triangle"))
    if match[2]:
        value = msg("{name} {number}", name=value, number=match[2].strip())
    for _ in range(match[3].count(" copy")):
        value = msg("{name} copy", name=value)
    return value
