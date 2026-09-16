"""Session binding for delayed Blender dialogs and operator submissions."""

from copy import deepcopy
from . import session


def bind(operator, current, target=False, snapshot=False):
    operator.owner = current.registry.id
    operator.bound_stage = current.stage
    if target:
        operator.bound_target = (
            current.direction,
            current.key_index,
            current.contour,
            current.point,
        )
        operator.bound_artwork = deepcopy(current.project["sweeps"])
    if snapshot:
        operator.bound_project = deepcopy(current.project)


def current(operator, stages=None, allow_busy=False):
    s = session.ACTIVE
    if s is None or s.closed or (s.busy and not allow_busy):
        return None
    if hasattr(operator, "owner") and operator.owner != s.registry.id:
        return None
    if hasattr(operator, "bound_stage") and operator.bound_stage != s.stage:
        return None
    if stages is not None and s.stage not in stages:
        return None
    if hasattr(operator, "bound_target"):
        target = (s.direction, s.key_index, s.contour, s.point)
        if target != operator.bound_target or operator.bound_artwork != s.project["sweeps"]:
            return None
    if hasattr(operator, "bound_project") and operator.bound_project != s.project:
        return None
    return s
