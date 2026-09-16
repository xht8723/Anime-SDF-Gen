"""Regressions for the shared physical-space transform implementation."""

from copy import deepcopy
import unittest
import numpy as np
from anime_sdf_gen.core import editing, model


class NumericTransformTests(unittest.TestCase):
    def test_numeric_and_shortcut_rotation_agree_for_asymmetric_canvases(self):
        for aspect in (0.5, 1.0, 2.0):
            for angle in (-45, 90, 180):
                contour = model.triangle()
                expected = editing.Transform(
                    {"contours": [contour]},
                    {(0, i) for i in range(3)},
                    "ROTATE",
                    (0.5, 0.3),
                    aspect,
                )
                expected.number = str(angle)
                result = deepcopy(contour)
                editing.transform_contour(result, angle=angle, aspect=aspect)
                for actual, reference in zip(
                    result["points"], expected.evaluate()["contours"][0]["points"]
                ):
                    for field in ("co", "left", "right"):
                        np.testing.assert_allclose(
                            actual[field], reference[field], rtol=0, atol=1e-15
                        )

    def test_combined_numeric_transform_preserves_physical_shape(self):
        contour = model.triangle()
        original = np.asarray([p["co"] for p in contour["points"]])
        metric = np.array([1.0, 2.0])
        editing.transform_contour(contour, 0.05, -0.02, 90, 1.5, 2)
        result = np.asarray([p["co"] for p in contour["points"]])
        np.testing.assert_allclose(
            result.mean(axis=0), original.mean(axis=0) + [0.05, -0.02], atol=1e-15
        )
        for i in range(3):
            self.assertAlmostEqual(
                np.linalg.norm((result[(i + 1) % 3] - result[i]) * metric),
                1.5 * np.linalg.norm((original[(i + 1) % 3] - original[i]) * metric),
            )

    def test_invalid_numeric_transform_leaves_original_untouched(self):
        contour = model.triangle()
        original = deepcopy(contour)
        with self.assertRaises(ValueError):
            editing.transform_contour(contour, dx=float("inf"))
        self.assertEqual(contour, original)
