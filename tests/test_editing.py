import copy
import math
import unittest
import numpy as np
from anime_sdf_gen.core import editing, model, curves
from tests.samples import project


def artwork():
    frame = model.get_keyframe(project(), model.LTR, 2)
    frame["contours"].append(model.triangle())
    return frame


class SelectionTests(unittest.TestCase):
    def test_box_directions_boundary_and_hidden_points(self):
        points = {(0, 0): [10, 10], (0, 1): [20, 15], (1, 0): [30, 40], (2, 0): None}
        expected = {(0, 0), (0, 1)}
        self.assertEqual(editing.box_selection(points, [20, 20], [10, 10]), expected)
        self.assertEqual(editing.box_selection(points, [10, 10], [20, 20]), expected)
        self.assertEqual(editing.combine_selection({(1, 0)}, expected, "SET"), expected)
        self.assertEqual(editing.combine_selection({(1, 0)}, expected, "ADD"), expected | {(1, 0)})
        self.assertEqual(editing.combine_selection(expected, {(0, 1)}, "SUB"), {(0, 0)})
        frame = artwork()
        frame["contours"][1]["enabled"] = False
        self.assertEqual(editing.available(frame), {(0, i) for i in range(7)})


class TransformTests(unittest.TestCase):
    def test_move_only_selected_points_preserves_relative_handles(self):
        frame = artwork()
        original = copy.deepcopy(frame)
        t = editing.Transform(frame, {(0, 3), (0, 4)}, "MOVE", [0, 0], aspect=2)
        t.move([0.12, -0.03])
        result = t.evaluate()
        for ci, c in enumerate(frame["contours"]):
            for pi, p in enumerate(c["points"]):
                if (ci, pi) in t.selected:
                    np.testing.assert_allclose(
                        result["contours"][ci]["points"][pi]["co"],
                        np.asarray(p["co"]) + [0.12, -0.03],
                    )
                    self.assertEqual(result["contours"][ci]["points"][pi]["left"], p["left"])
                else:
                    self.assertEqual(result["contours"][ci]["points"][pi], p)
        self.assertEqual(frame, original)
        self.assertEqual(t.evaluate(), result)

    def test_rotation_in_physical_face_plane_preserves_lengths(self):
        frame = artwork()
        sel = {(1, i) for i in range(3)}
        t = editing.Transform(frame, sel, "ROTATE", [0.7, 0.3], aspect=2.3)
        t.number = "90"
        result = t.evaluate()
        before = np.asarray([p["co"] for p in frame["contours"][1]["points"]])
        after = np.asarray([p["co"] for p in result["contours"][1]["points"]])
        np.testing.assert_allclose(after.mean(axis=0), before.mean(axis=0))
        old = (before - before.mean(axis=0)) * t.metric
        new = (after - after.mean(axis=0)) * t.metric
        np.testing.assert_allclose(new, np.column_stack([-old[:, 1], old[:, 0]]), atol=1e-14)
        self.assertEqual(result["contours"][0], frame["contours"][0])

    def test_constrained_scale_transforms_free_handles(self):
        frame = artwork()
        for p in frame["contours"][1]["points"]:
            p["mode"] = "FREE"
        t = editing.Transform(frame, {(1, i) for i in range(3)}, "SCALE", [0.7, 0.3])
        t.axis = "X"
        t.number = "-2"
        result = t.evaluate()
        for before, after in zip(frame["contours"][1]["points"], result["contours"][1]["points"]):
            self.assertAlmostEqual(after["co"][1], before["co"][1])
            np.testing.assert_allclose(after["right"], np.asarray(before["right"]) * [-2, 1])
        t.axis = "Z"
        self.assertEqual(t.evaluate(), frame)

    def test_free_handle_edit_keeps_anchor_and_other_handle(self):
        frame = artwork()
        p = frame["contours"][1]["points"][0]
        left, right = curves.handles(frame["contours"][1], 0)
        t = editing.Transform(frame, {(1, 0)}, "MOVE", [0, 0], handle="right")
        self.assertEqual(t.evaluate(), frame)
        t.axis = "Y"
        t.number = ".025"
        result = t.evaluate()["contours"][1]["points"][0]
        self.assertEqual(result["co"], p["co"])
        self.assertEqual(result["mode"], "FREE")
        np.testing.assert_allclose(result["left"], left - p["co"])
        np.testing.assert_allclose(result["right"], right - p["co"] + [0, 0.025])

    def test_numeric_input_backspace_axis_and_identity(self):
        frame = artwork()
        t = editing.Transform(frame, {(0, 3)}, "MOVE", [0, 0])
        for char in "-.125":
            t.numeric(char)
        t.numeric("BACK_SPACE")
        self.assertEqual(t.number, "-.12")
        t.axis = "X"
        t.move([0.4, 0.6])
        np.testing.assert_allclose(t.values(True)[0], [-0.12, 0])
        t.axis = "Z"
        self.assertEqual(t.evaluate(), frame)
        t.axis = "Y"
        np.testing.assert_allclose(t.values()[0], [0, -0.12])

    def test_precision_is_incremental_and_snap_respects_numeric_entry(self):
        t = editing.Transform(artwork(), {(0, 3)}, "MOVE", [0, 0])
        t.move([0.02, 0])
        t.move([0.12, 0], True)
        t.move([0.13, 0], False)
        np.testing.assert_allclose(t.values()[0], [0.04, 0])
        t.move([0.1437, 0])
        np.testing.assert_allclose(t.values(True)[0], [0.05, 0])
        np.testing.assert_allclose(t.values(True, True)[0], [0.054, 0])
        t.axis = "X"
        t.number = ".0123"
        np.testing.assert_allclose(t.values(True)[0], [0.0123, 0])

    def test_mouse_rotation_wrap_and_scale_snap(self):
        f = artwork()
        sel = {(1, i) for i in range(3)}
        center = np.mean([p["co"] for p in f["contours"][1]["points"]], axis=0)
        t = editing.Transform(f, sel, "ROTATE", center + [1, 0])
        for angle in (170, 190, 350, 370):
            t.move(center + [math.cos(math.radians(angle)), math.sin(math.radians(angle))])
        self.assertAlmostEqual(math.degrees(t.values()[1]), 370)
        t = editing.Transform(f, sel, "SCALE", center + [0.1, 0])
        t.move(center + [0.137, 0])
        self.assertAlmostEqual(t.values(True)[2], 1.4)

    def test_invalid_values_do_not_mutate_original(self):
        frame = artwork()
        original = copy.deepcopy(frame)
        with self.assertRaises(ValueError):
            editing.Transform(frame, set(), "MOVE", [0, 0])
        t = editing.Transform(frame, {(0, 3)}, "MOVE", [0, 0])
        t.axis = "X"
        t.number = "101"
        with self.assertRaises(ValueError):
            t.evaluate()
        self.assertEqual(frame, original)
