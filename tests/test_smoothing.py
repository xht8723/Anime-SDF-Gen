"""Independent 2-D reference checks for the separable threshold filter."""

from anime_sdf_gen.core.thresholds import decode
import unittest
import numpy as np
from anime_sdf_gen.core import smoothing, geometry
from anime_sdf_gen.core.jobs import run


def reference(field, strength):
    sigma = strength * len(field) / 2048
    radius = int(np.ceil(3 * sigma))
    yy, xx = np.mgrid[-radius : radius + 1, -radius : radius + 1]
    kernel = np.exp(-(xx * xx + yy * yy) / (2 * sigma * sigma))
    kernel /= kernel.sum()
    interior = (field > 0) & (field < 1)
    padded = np.pad(np.where(interior, field, 0).astype(float), radius)
    weights = np.pad(interior.astype(float), radius)
    numer = np.zeros(field.shape)
    denom = numer.copy()
    for y in range(len(kernel)):
        for x in range(len(kernel)):
            numer += kernel[y, x] * padded[y : y + len(field), x : x + field.shape[1]]
            denom += kernel[y, x] * weights[y : y + len(field), x : x + field.shape[1]]
    result = field.copy()
    result[interior] = numer[interior] / denom[interior]
    return result


class SmoothingTests(unittest.TestCase):
    def test_matches_independent_2d_convolution_with_holes_and_endpoints(self):
        fields = np.random.default_rng(4).random((256, 256, 2)).astype(np.float32)
        fields[15:70, 20:45] = 0
        fields[90:130, 130:200] = 1
        original = fields.copy()
        filtered = run(smoothing.smooth_steps(fields, 8))
        for c in (0, 1):
            np.testing.assert_allclose(
                filtered[..., c], reference(fields[..., c], 8), rtol=0, atol=6e-8
            )
        np.testing.assert_array_equal(fields, original)
        for endpoint in (0, 1):
            np.testing.assert_array_equal(filtered == endpoint, fields == endpoint)
        for progress in (0, 0.25, 0.5, 0.75, 1):
            if progress:
                self.assertFalse(
                    np.any(decode(filtered, progress - 0.01) & ~decode(filtered, progress))
                )

    def test_off_constants_sentinels_and_isolated_patch(self):
        a = np.full((64, 64, 2), 0.25, np.float32)
        self.assertIs(run(smoothing.smooth_steps(a, 0)), a)
        np.testing.assert_array_equal(run(smoothing.smooth_steps(a, 8)), a)
        a[:32] = 0
        a[32:] = 1
        np.testing.assert_array_equal(run(smoothing.smooth_steps(a, 8)), a)
        a[15, 20, 0] = 0.375
        np.testing.assert_array_equal(run(smoothing.smooth_steps(a, 8)), a)

    def test_lit_cutout_is_preserved_while_nearby_transitions_smooth(self):
        a = np.full((256, 256, 2), 0.2, np.float32)
        a[:, 128:] = 0.8
        a[110:120, 120:130] = 1
        out = run(smoothing.smooth_steps(a, 8))
        np.testing.assert_array_equal(out[a == 1], a[a == 1])
        self.assertGreater(out[100, 127, 0], a[100, 127, 0])
        self.assertLess(out[100, 128, 0], a[100, 128, 0])

    def test_exact_linked_mirroring_and_independent_unlinked_fields(self):
        a = np.random.default_rng(7).random((256, 256, 2)).astype(np.float32)
        a[..., 1] = a[:, ::-1, 0]
        out = run(smoothing.smooth_steps(a, 8, True))
        np.testing.assert_array_equal(out[..., 1], out[:, ::-1, 0])
        a[..., 1] = 0.15
        out = run(smoothing.smooth_steps(a, 8, False))
        np.testing.assert_array_equal(out[..., 1], a[..., 1])
        self.assertFalse(np.array_equal(out[..., 1], out[:, ::-1, 0]))

    def test_strength_scales_with_canvas_resolution(self):
        def field(n):
            x = (np.arange(n) + 0.5) / n
            return (
                np.broadcast_to((0.5 + 0.25 * np.sin(x * 24 * np.pi))[None, :, None], (n, n, 2))
                .astype(np.float32)
                .copy()
            )

        low = run(smoothing.smooth_steps(field(256), 8))
        high = run(smoothing.smooth_steps(field(512), 8))
        reduced = high.reshape(256, 2, 256, 2, 2).mean(axis=(1, 3))
        np.testing.assert_allclose(
            low[16:-16, 16:-16], reduced[16:-16, 16:-16], atol=0.0007, rtol=0
        )

    def test_cancel_does_not_modify_raw_cache(self):
        a = np.random.default_rng(11).random((512, 512, 2)).astype(np.float32)
        before = a.copy()
        job = smoothing.smooth_steps(a, 8)
        for _ in range(12):
            next(job)
        job.close()
        np.testing.assert_array_equal(a, before)

    def test_uv_islands_sample_head_space_without_cross_island_blur(self):
        a = np.full((256, 256, 2), 0.2, np.float32)
        a[:, 128:] = 0.8
        uv = []
        projected = []
        for ux, px in ((0.1, 0.75), (0.52, 0.05)):
            u = np.array([[ux, 0.1], [ux + 0.38, 0.1], [ux + 0.38, 0.9], [ux, 0.9]])
            p = np.array([[px, 0.2, 0], [px + 0.2, 0.2, 0], [px + 0.2, 0.8, 0], [px, 0.8, 0]])
            for indices in ((0, 1, 2), (0, 2, 3)):
                uv.append(u[list(indices)])
                projected.append(p[list(indices)])
        uv = np.array(uv)
        projected = np.array(projected)
        depth, facing = run(geometry.projection_steps(projected, 256))
        raw = run(geometry.bake_steps(a, uv, projected, depth, facing, 256))
        filtered = run(
            geometry.bake_steps(
                run(smoothing.smooth_steps(a, 8)), uv, projected, depth, facing, 256
            )
        )
        np.testing.assert_array_equal(raw[..., 2], filtered[..., 2])
        np.testing.assert_allclose(filtered[128, 64, :2], 0.8)
        np.testing.assert_allclose(filtered[128, 180, :2], 0.2)

    def test_strength_validation(self):
        for strength in (-1, 8.1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                run(smoothing.smooth_steps(np.ones((8, 8, 2)), strength))


if __name__ == "__main__":
    unittest.main()
