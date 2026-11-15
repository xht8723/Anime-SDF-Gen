"""Artist input acceptance, full UV coverage, and recoverable draft data."""

from copy import deepcopy
import unittest
import numpy as np
from anime_sdf_gen.core import compile, curves, files, geometry, model
from anime_sdf_gen.core.jobs import run
from anime_sdf_gen.core.thresholds import decode
from tests.samples import project, ellipse


def uv_footprint(uvs, size):
    mask = np.zeros((size, size), bool)
    for uv in uvs:
        for y, x, _ in geometry.triangle_pixels(uv, size):
            mask[y, x] = True
    return mask


class PermissiveBakeTests(unittest.TestCase):
    def test_full_selection_covers_backfaces_occluded_and_collapsed_geometry(self):
        front = np.array([[0, 0, 0.2], [1, 0, 0.2], [0, 1, 0.2]])
        projected = np.stack([front, front - [0, 0, 0.3], front[::-1],
                              [[0.8, 0.5, 0.1]] * 3,
                              [[0.4, 0, 0], [0.4, 1, 0], [0.4, 0.5, 0.3]]])
        base = np.array([[0.01, 0.1], [0.18, 0.1], [0.01, 0.8]])
        uvs = np.stack([base + [i * 0.2, 0] for i in range(5)])
        expected = uv_footprint(uvs, 128)
        for front_only in (False, True):
            depth, facing = run(geometry.projection_steps(projected, 128, front_only=front_only))
            for threshold in (0.0, 0.35, 1.0):
                fields = np.full((128, 128, 2), threshold, np.float32)
                image = run(geometry.bake_steps(fields, uvs, projected, depth, facing, 128,
                                               front_only=front_only))
                mask = image[..., 2] > 0
                if front_only:
                    self.assertFalse(mask[:, 26:].any())
                    self.assertTrue(mask.any())
                else:
                    np.testing.assert_array_equal(mask, expected)
                np.testing.assert_allclose(image[mask, :2], threshold)

    def test_uv_tile_clipping_and_collapsed_uvs(self):
        uv = np.array([[[0.1, 0.1], [0.8, 0.1], [0.1, 0.8]],
                       [[0.5, 0.5]] * 3,
                       [[2, 2], [3, 2], [2, 3]],
                       [[-0.3, 0.4], [0.4, 0.4], [0.4, 1.3]]])
        geometry.validate_uv(uv)
        projected = np.tile([[[0, 0, 0], [1, 0, 0], [0, 1, 0]]], (4, 1, 1))
        depth, facing = run(geometry.projection_steps(projected, 64))
        image = run(geometry.bake_steps(np.full((64, 64, 2), 0.3), uv, projected, depth, facing, 64))
        np.testing.assert_array_equal(image[..., 2] > 0, uv_footprint(uv, 64))
        self.assertEqual(list(geometry.triangle_pixels(uv[1], 64)), [])
        self.assertEqual(list(geometry.triangle_pixels(uv[2], 64)), [])

    def test_empty_output_and_padding(self):
        for uv in (np.zeros((1, 3, 2)), np.full((1, 3, 2), 2), np.empty((0, 3, 2))):
            projected = np.zeros((len(uv), 3, 3))
            depth, facing = run(geometry.projection_steps(projected, 64))
            for front_only in (False, True):
                image = run(geometry.bake_steps(np.zeros((64, 64, 2)), uv, projected,
                                               depth, facing, 64, front_only=front_only))
                run(geometry.pad_steps(image, 2))
                np.testing.assert_array_equal(image, np.broadcast_to([1, 1, 0], image.shape))

    def test_projection_domain_includes_edge_and_point_samples(self):
        for tri in ([[[0.5, 0.5, 0]] * 3], [[[0.5, 0.1, 0], [0.5, 0.9, 0], [0.5, 0.4, -1]]]):
            projected = np.array(tri, dtype=float)
            depth, _ = run(geometry.projection_steps(projected, 64))
            self.assertTrue(np.isfinite(depth).any())
            restricted, _ = run(geometry.projection_steps(projected, 64, front_only=True))
            self.assertFalse(np.isfinite(restricted).any())

    def test_selected_surface_endpoints_and_authored_cutout(self):
        p = project(5)
        p["sweeps"][model.LTR][-1]["contours"].append(ellipse("Cutout", 0.5, 0.5, 0.15, 0.15, "REMOVE"))
        model.synchronize_mirror(p)
        fields = compile.compile_project(p, 128)
        # Reversed winding maps the same projection to a separate UV island.
        uv = np.array([[[0, 0], [0.5, 0], [0, 1]], [[0.5, 0], [1, 0], [0.5, 1]]])
        front = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        projected = np.stack([front, front[::-1]])
        depth, facing = run(geometry.projection_steps(projected, 128))
        image = run(geometry.bake_steps(fields, uv, projected, depth, facing, 128))
        covered = image[..., 2] > 0
        self.assertFalse(decode(image[..., 0], 0)[covered].any())
        self.assertTrue(decode(image[..., 0], 1)[covered].any())
        self.assertTrue((~decode(image[..., 0], 1)[covered]).any())
        np.testing.assert_array_equal(covered, uv_footprint(uv, 128))


class PermissiveArtworkTests(unittest.TestCase):
    def test_crossings_duplicate_points_and_empty_shapes_compile(self):
        for points in ([(0.2, 0.2), (0.8, 0.8), (0.2, 0.8), (0.8, 0.2)],
                       [(0.2, 0.2), (0.8, 0.2), (0.8, 0.2), (0.2, 0.8)],
                       [(0.5, 0.5)] * 3):
            p = project(2)
            c = model.triangle()
            c.update(operation="REMOVE", points=[model.point(*xy, mode="CORNER") for xy in points])
            p["sweeps"][model.LTR][-1]["contours"].append(c)
            model.synchronize_mirror(p)
            cache = {}
            expected = curves.raster_keyframe(p, p["sweeps"][model.LTR][-1], model.LTR, 128, cache)
            fields = run(compile.compile_steps(p, 128, mask_cache=cache))
            np.testing.assert_array_equal(decode(fields[..., 0], 1), expected)

    def test_large_artwork_draft_roundtrip(self):
        p = project(2)
        p["source"]["uv_map"] = p["authoring"]["uv_map"] = ""
        frames = p["sweeps"][model.LTR]
        c = model.triangle()
        c["points"] = [model.point(i / 300, 0.3, mode="CORNER") for i in range(300)]
        frames[0]["contours"].extend(deepcopy(c) for _ in range(130))
        model.synchronize_mirror(p)
        text = model.dumps(p)
        self.assertGreater(len(text), 16_000_000)
        self.assertEqual(model.loads(text), p)

    def test_export_conflict_does_not_prevent_draft(self):
        p = project(5)
        p["sweeps"][model.LTR][0]["contours"].append(ellipse("Early shadow", 0.8, 0.7, 0.1, 0.1))
        model.synchronize_mirror(p)
        with self.assertRaises(compile.KeyframeConflict):
            compile.compile_project(p, 64)
        self.assertEqual(model.loads(model.dumps(p)), p)

    def test_nonfinite_data_still_rejected(self):
        for value in (np.nan, np.inf):
            with self.assertRaises(ValueError):
                geometry.validate_uv(np.full((1, 3, 2), value))
            p = project()
            p["landmarks"]["chin"][0] = value
            with self.assertRaises(ValueError):
                model.dumps(p)
