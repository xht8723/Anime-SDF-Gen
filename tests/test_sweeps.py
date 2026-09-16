from anime_sdf_gen.core.thresholds import decode, endpoint_seams
import copy
import math
import unittest
import numpy as np
from anime_sdf_gen.core import model, curves, compile, files
from tests.samples import project


class SweepTests(unittest.TestCase):
    def test_counts_even_odd_and_full_face_endpoints(self):
        for n in (2, 4, 9, 16, 33):
            p = project(n)
            domain = compile.face_domain(64)
            self.assertFalse(any(k in p for k in ("front", "left", "right", "mirror")))
            self.assertEqual(p["authoring"]["keyframe_count"], n)
            for direction in model.SWEEP_LABELS:
                frames = model.sweep(p, direction)
                self.assertEqual(len(frames), n)
                self.assertEqual([k["progress"] for k in frames], [i / (n - 1) for i in range(n)])
                self.assertFalse(curves.raster_keyframe(p, frames[0], direction, 64)[domain].any())
                self.assertTrue(curves.raster_keyframe(p, frames[-1], direction, 64)[domain].all())
            self.assertEqual(model.loads(model.dumps(p)), p)

    def test_fidelity_at_all_frames_in_each_row(self):
        for mirrored in (False, True):
            p = project(8, mirrored)
            if not mirrored:
                for k in model.sweep(p, model.RTL):
                    for pt in k["contours"][0]["points"]:
                        pt["co"][0] -= 0.06 * math.sin(k["progress"] * math.pi)
                model.insert_keyframe(p, model.RTL, 2)
            before = copy.deepcopy(p)
            t = compile.compile_project(p, 128)
            domain = compile.face_domain(128)
            self.assertEqual(p, before)
            for channel, direction in enumerate(model.SWEEP_LABELS):
                for k in model.sweep(p, direction):
                    expected = curves.raster_keyframe(p, k, direction, 128)
                    np.testing.assert_array_equal(
                        decode(t[..., channel], k["progress"])[domain], expected[domain]
                    )
            if mirrored:
                np.testing.assert_allclose(t[..., 0], t[:, ::-1, 1], atol=1e-6)
            else:
                self.assertGreater(np.max(abs(t[..., 0] - t[:, ::-1, 1])), 0.01)

    def test_full_sweep_mirror_does_not_pair_frames_inside_one_row(self):
        p = project(8)
        before = copy.deepcopy(model.sweep(p, model.LTR))
        index = 3
        frame = model.get_keyframe(p, model.LTR, index)
        frame["contours"][0]["points"][3]["co"][0] += 0.02
        model.synchronize_mirror(p, model.LTR)
        for i, k in enumerate(model.sweep(p, model.LTR)):
            if i != index:
                self.assertEqual(k, before[i])
        reflected = model.get_keyframe(p, model.RTL, index)["contours"][0]["points"][3]["co"][0]
        self.assertAlmostEqual(reflected, 1 - frame["contours"][0]["points"][3]["co"][0])
        model.get_keyframe(p, model.RTL, 0)["contours"].append(model.triangle())
        model.synchronize_mirror(p, model.RTL)
        self.assertEqual(len(model.get_keyframe(p, model.LTR, 0)["contours"]), 2)
        self.assertEqual(len(model.get_keyframe(p, model.LTR, -1)["contours"]), 1)

    def test_independent_insert_remove_copy_and_history(self):
        p = project(6, False)
        other = copy.deepcopy(model.sweep(p, model.RTL))
        h = model.History()
        h.push(p)
        i = model.insert_keyframe(p, model.LTR, 1)
        self.assertEqual(i, 2)
        self.assertEqual(len(model.sweep(p, model.LTR)), 7)
        self.assertEqual(model.sweep(p, model.RTL), other)
        model.copy_previous(p, model.LTR, i)
        p = h.undo(p)
        self.assertEqual(len(model.sweep(p, model.LTR)), 6)
        p = h.redo(p)
        model.remove_keyframe(p, model.LTR, i)
        self.assertEqual(len(model.sweep(p, model.LTR)), 6)
        for i in (0, 5):
            with self.assertRaises(ValueError):
                model.remove_keyframe(p, model.LTR, i)
        p["mirror_sweeps"] = True
        model.synchronize_mirror(p, model.RTL)
        model.insert_keyframe(p, model.RTL, 3)
        self.assertEqual(len(model.sweep(p, model.LTR)), 7)
        self.assertEqual(model.loads(model.dumps(p)), p)

    def test_conflict_labels_identify_row_and_one_based_frames(self):
        p = project(6, False)
        for pt in model.get_keyframe(p, model.RTL, 3)["contours"][0]["points"]:
            pt["co"][0] = 1.1
        with self.assertRaises(compile.KeyframeConflict) as caught:
            compile.compile_project(p, 64)
        error = caught.exception
        self.assertEqual(error.direction, model.RTL)
        self.assertIn("Right → Left keyframes 3 → 4", str(error))


class RotationTests(unittest.TestCase):
    def test_cardinals_wrap_and_long_frames(self):
        for angle, expected in (
            (0, (model.LTR, 0)),
            (90, (model.LTR, 0.5)),
            (180, (model.LTR, 1)),
            (270, (model.RTL, 0.5)),
            (360, (model.LTR, 0)),
            (-90, (model.RTL, 0.5)),
            (810, (model.LTR, 0.5)),
        ):
            self.assertEqual(model.rotation_sample(angle), expected)
        self.assertAlmostEqual(model.advance_rotation(359, 2), 1)
        self.assertAlmostEqual(model.advance_rotation(15, 3 * 360 + 70), 85)
        for direction in model.SWEEP_LABELS:
            for p in (0.01, 0.25, 0.5, 0.99):
                self.assertEqual(
                    model.rotation_sample(model.keyframe_rotation(direction, p))[0], direction
                )
                self.assertAlmostEqual(
                    model.rotation_sample(model.keyframe_rotation(direction, p))[1], p
                )

    def test_one_orbit_visits_both_maps_and_full_face_not_half_face(self):
        p = project(9)
        t = compile.compile_project(p, 128)
        domain = compile.face_domain(128)
        masks = []
        for angle in np.linspace(0, 360, 721):
            direction, progress = model.rotation_sample(angle)
            masks.append(decode(t[..., 0 if direction == model.LTR else 1], progress))
        np.testing.assert_array_equal(masks[0], masks[-1])
        self.assertFalse(masks[0][domain].any())
        self.assertTrue(masks[360][domain].all())
        self.assertGreater(masks[270][domain].mean(), 0.75)
        for i in range(360):
            self.assertFalse((masks[i] & ~masks[i + 1] & domain).any())
        for i in range(360, 720):
            self.assertFalse((~masks[i] & masks[i + 1] & domain).any())
        np.testing.assert_array_equal(masks[180][:, ::-1], masks[540])
        self.assertEqual(endpoint_seams(t, domain), {"Front": 0, "Back": 0})

    def test_endpoint_warning_detects_art_difference_without_mutation(self):
        p = project(5, False)
        cut = model.triangle()
        cut["operation"] = "REMOVE"
        model.get_keyframe(p, model.LTR, -1)["contours"].append(cut)
        before = copy.deepcopy(p)
        t = compile.compile_project(p, 64)
        seams = endpoint_seams(t, compile.face_domain(64))
        self.assertEqual(seams["Front"], 0)
        self.assertGreater(seams["Back"], 0)
        self.assertEqual(p, before)
        codes = files.quantize(np.dstack((t, np.ones(t.shape[:2]))))
        self.assertTrue((codes[..., 0] == 65535).any())
