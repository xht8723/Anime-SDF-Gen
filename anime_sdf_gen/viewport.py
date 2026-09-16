"""Shared viewport geometry and camera math without editor ownership."""

from dataclasses import dataclass
import bpy
from mathutils import Matrix, Quaternion, Vector


def scale():
    return max(1.0, bpy.context.preferences.system.ui_scale)


def window_region(area):
    return next((r for r in area.regions if r.type == "WINDOW"), None)


@dataclass
class Rect:
    x: int = 0
    y: int = 0
    width: int = 1
    height: int = 1

    @property
    def box(self):
        return self.x, self.y, self.width, self.height

    def contains(self, xy):
        return self.x <= xy[0] < self.x + self.width and self.y <= xy[1] < self.y + self.height


class View:
    """One popup camera, projected and navigated by Blender's RegionView3D."""

    def __init__(self, editor):
        self.editor = editor
        self.region = Rect()
        self.view_location = Vector((0, 0, 0))
        self.view_rotation = Quaternion()
        self.view_distance = 1.0
        self.view_perspective = "ORTHO"
        self.view_matrix = Matrix.Identity(4)
        self.perspective_matrix = Matrix.Identity(4)
        self.projection_matrix = Matrix.Identity(4)
        self.frame_pending = False

    def update(self):
        if not self.editor.navigation.drawing:
            return
        self.editor.navigation.matrices(self)
        if self.frame_pending:
            a = self.editor.session.project["alignment"]
            self.view_distance *= (
                max(
                    a["height"] * self.projection_matrix[1][1],
                    a["width"] * self.projection_matrix[0][0],
                )
                / 1.66
            )
            self.frame_pending = False
            self.editor.navigation.matrices(self)

    def project(self, world):
        clip = self.perspective_matrix @ Vector((*world, 1))
        if clip.w <= 0:
            return None
        return Vector(
            (
                (clip.x / clip.w + 1) * self.region.width / 2,
                (clip.y / clip.w + 1) * self.region.height / 2,
            )
        )

    def ray(self, mouse):
        inv = self.perspective_matrix.inverted()
        p = inv @ Vector(
            (2 * mouse[0] / self.region.width - 1, 2 * mouse[1] / self.region.height - 1, -1, 1)
        )
        q = inv @ Vector(
            (2 * mouse[0] / self.region.width - 1, 2 * mouse[1] / self.region.height - 1, 1, 1)
        )
        origin = Vector(p[:3]) / p.w
        return origin, (Vector(q[:3]) / q.w - origin).normalized()
