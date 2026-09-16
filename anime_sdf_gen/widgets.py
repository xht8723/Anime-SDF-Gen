"""Session-owned, batched rounded surfaces for the popup's pixel-space UI."""

import math
from .canvas import label
from functools import lru_cache
import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader


@lru_cache(maxsize=128)
def linear_color(color):
    # Popup palette values are display sRGB. The target framebuffer performs
    # its own linear-to-sRGB encoding for custom shaders.
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in color[:3]) + (
        color[3],
    )


class Painter:
    def __init__(self):
        self.shader = None
        self.rectangles = []
        self.labels = []
        self.viewport = (1, 1)

    def begin(self, width, height):
        self.rectangles.clear()
        self.labels.clear()
        self.viewport = (width, height)

    def rectangle(self, x, y, w, h, fill, radius=0, border=None, stroke=0):
        if w > 0 and h > 0:
            self.rectangles.append(
                (x, y, w, h, fill, min(radius, w / 2, h / 2), border or fill, stroke)
            )

    def line(self, a, b, color, width=1.5):
        # Filled quads give consistent icon strokes on every graphics backend.
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return
        self.rectangles.append(("line", a, b, color, width))

    def label(self, value, x, y, size, color):
        self.labels.append((value, x, y, size, color))

    def _shader(self):
        if self.shader is None:
            info = gpu.types.GPUShaderCreateInfo()
            for index, kind, name in [
                (0, "VEC2", "position"),
                (1, "VEC2", "coordinate"),
                (2, "VEC2", "extent"),
                (3, "VEC2", "style"),
                (4, "VEC4", "fillColor"),
                (5, "VEC4", "borderColor"),
            ]:
                info.vertex_in(index, kind, name)
            stage = gpu.types.GPUStageInterfaceInfo("anime_sdf_gen_widgets")
            for kind, name in [
                ("VEC2", "local"),
                ("VEC2", "halfSize"),
                ("VEC2", "shapeStyle"),
                ("VEC4", "fill"),
                ("VEC4", "edge"),
            ]:
                stage.smooth(kind, name)
            info.vertex_out(stage)
            info.push_constant("VEC2", "viewportSize")
            info.fragment_out(0, "VEC4", "fragColor")
            info.vertex_source("""void main(){
                local=coordinate;halfSize=extent;shapeStyle=style;fill=fillColor;edge=borderColor;
                gl_Position=vec4(position/viewportSize*2.0-1.0,0.0,1.0);
            }""")
            info.fragment_source("""void main(){
                vec2 q=abs(local)-halfSize+shapeStyle.x;
                float d=length(max(q,vec2(0.0)))+min(max(q.x,q.y),0.0)-shapeStyle.x;
                float aa=max(fwidth(d),0.7);
                float coverage=1.0-smoothstep(-aa*0.5,aa*0.5,d);
                float outline=shapeStyle.y>0.0 ? smoothstep(-shapeStyle.y-aa*0.5,-shapeStyle.y+aa*0.5,d) : 0.0;
                vec4 color=mix(fill,edge,outline);
                fragColor=vec4(color.rgb,color.a*coverage);
            }""")
            self.shader = gpu.shader.create_from_info(info)
        return self.shader

    def flush(self):
        gpu.state.blend_set("ALPHA")
        if self.rectangles:
            attrs = {
                name: []
                for name in (
                    "position",
                    "coordinate",
                    "extent",
                    "style",
                    "fillColor",
                    "borderColor",
                )
            }
            order = (0, 1, 2, 0, 2, 3)
            for item in self.rectangles:
                if item[0] == "line":
                    _, a, b, fill, stroke = item
                    center = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                    dx, dy = b[0] - a[0], b[1] - a[1]
                    length = math.hypot(dx, dy)
                    ux, uy = dx / length, dy / length
                    w, h = length + stroke, stroke
                    basis = ((ux, uy), (-uy, ux))
                    radius = stroke / 2
                    edge = fill
                    border_width = 0
                else:
                    x, y, w, h, fill, radius, edge, border_width = item
                    center = (x + w / 2, y + h / 2)
                    basis = ((1, 0), (0, 1))
                half = (w / 2, h / 2)
                pad = 1.0
                corners = (
                    (-half[0] - pad, -half[1] - pad),
                    (half[0] + pad, -half[1] - pad),
                    (half[0] + pad, half[1] + pad),
                    (-half[0] - pad, half[1] + pad),
                )
                for i in order:
                    x, y = corners[i]
                    attrs["position"].append(
                        (
                            center[0] + basis[0][0] * x + basis[1][0] * y,
                            center[1] + basis[0][1] * x + basis[1][1] * y,
                        )
                    )
                    attrs["coordinate"].append((x, y))
                    attrs["extent"].append(half)
                    attrs["style"].append((radius, border_width))
                    attrs["fillColor"].append(linear_color(tuple(fill)))
                    attrs["borderColor"].append(linear_color(tuple(edge)))
            shader = self._shader()
            shader.bind()
            shader.uniform_float("viewportSize", self.viewport)
            # GPU buffers must use float32, including coordinates.
            batch_for_shader(
                shader, "TRIS", {k: np.asarray(v, dtype=np.float32) for k, v in attrs.items()}
            ).draw(shader)
            self.rectangles.clear()
        for values in self.labels:
            label(*values)
        self.labels.clear()

    def close(self):
        self.rectangles.clear()
        self.labels.clear()
        self.shader = None
