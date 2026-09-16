"""Map identity, endpoint precision, bundle integrity and straight fitted presets."""

from anime_sdf_gen.core.image_io import read_png
import copy
import hashlib
import itertools
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from anime_sdf_gen.core import model, curves, files
from tests.samples import project


class StraightPresetTests(unittest.TestCase):
    def test_clean_boundaries_stay_straight_after_fitting_and_mirroring(self):
        for mirror in (False, True):
            p = project(9, mirror)
            p["landmarks"] = {"nose": [0.68, 0.39], "mouth": [0.40, 0.19], "chin": [0.57, 0.06]}
            for count in (9, 17):
                model.refit(p, count)
                for side in (model.LTR, model.RTL):
                    for ph in model.sweep(p, side):
                        c = ph["contours"][0]
                        self.assertEqual(len(c["points"]), 7)
                        x = c["points"][0]["co"][0]
                        np.testing.assert_allclose(curves.flatten(c)[:, 0], x, atol=1e-14)
                        for i in range(7):
                            for handle in curves.handles(c, i):
                                self.assertAlmostEqual(handle[0], x)
                        if ph["progress"]:
                            expected = -0.2 + ph["progress"] * 1.4
                            self.assertAlmostEqual(
                                x, expected if side == model.LTR else 1 - expected
                            )
                self.assertEqual(model.loads(model.dumps(p)), p)

    def test_nose_accent_keeps_fitted_profile(self):
        p = project()
        p["preset"] = "NOSE"
        p["landmarks"]["nose"][0] = 0.61
        model.refit(p)
        c = p["sweeps"][model.LTR][len(p["sweeps"][model.LTR]) // 2]["contours"][0]
        self.assertGreater(np.ptp(curves.flatten(c)[:, 0]), 0.1)
        self.assertAlmostEqual(c["points"][3]["co"][0], 0.72)


class PackingTests(unittest.TestCase):
    def image(self):
        image = np.random.default_rng(908).random((11, 17, 3))
        image[0, 0] = [0, 1, 0]
        image[-1, -1] = [1, 0, 1]
        image[1, 1] = [1e-9, 1 - 1e-9, 1e-9]
        image[1, 2] = [1 - 1e-9, 1e-9, 1 - 1e-9]
        return image

    def test_every_valid_packing_roundtrips_exact_values_and_map_metadata(self):
        image = self.image()
        canonical = files.quantize(image)
        np.testing.assert_array_equal(canonical[1, 1], [1, 65534, 0])
        np.testing.assert_array_equal(canonical[1, 2], [65534, 1, 65535])
        count = 0
        with tempfile.TemporaryDirectory() as tmp:
            for choices in itertools.product(model.OUTPUT_ROUTES, repeat=3):
                rgb = [c for c in choices if c != "SEPARATE"]
                if len(rgb) != len(set(rgb)):
                    continue
                count += 1
                p = project()
                p["settings"]["packing"] = dict(zip(model.MAP_LABELS, choices))
                base = Path(tmp) / str(count) / "face.PNG"
                paths = files.export_bundle(p, image, base)
                self.assertEqual(tuple(map(Path, paths)), files.output_paths(p, base))
                saved = files.load_project(paths[-1])
                self.assertEqual(saved["settings"]["packing"], p["settings"]["packing"])
                self.assertEqual(saved["encoding"], model.ENCODING)
                self.assertEqual(len(saved["textures"]), len(paths) - 1)
                seen = []
                for path, info in zip(paths, saved["textures"]):
                    data = Path(path).read_bytes()
                    codes = read_png(path)
                    self.assertEqual(info["file"], Path(path).name)
                    self.assertEqual(info["sha256"], hashlib.sha256(data).hexdigest())
                    self.assertEqual((info["width"], info["height"], info["bits"]), (17, 11, 16))
                    self.assertEqual(info["colorspace"], "Non-Color")
                    header = struct.unpack(">IIBBBBB", data[16:29])
                    self.assertEqual(header, (17, 11, 16, 0 if codes.ndim == 2 else 2, 0, 0, 0))
                    for channel, name in info["channels"].items():
                        c = list(model.MAP_LABELS).index(name)
                        seen.append(name)
                        sample = codes if channel == "Y" else codes[..., "RGB".index(channel)]
                        np.testing.assert_array_equal(sample, canonical[..., c])
                    if codes.ndim == 3:
                        for channel in set("RGB") - set(info["channels"]):
                            self.assertFalse(codes[..., "RGB".index(channel)].any())
                    else:
                        self.assertEqual(info["color_type"], "GRAYSCALE")
                self.assertCountEqual(seen, model.MAP_LABELS)
                self.assertEqual(len(list(base.parent.iterdir())), len(paths))
        self.assertEqual(count, 34)

    def test_routing_swaps_occupied_channels_and_allows_multiple_individuals(self):
        p = project()
        model.set_packing(p, "character_left", "B")
        self.assertEqual(
            p["settings"]["packing"],
            dict(character_left="B", character_right="G", face_coverage="R"),
        )
        model.set_packing(p, "character_left", "SEPARATE")
        model.set_packing(p, "character_left", "G")
        self.assertEqual(
            p["settings"]["packing"],
            dict(character_left="G", character_right="SEPARATE", face_coverage="R"),
        )
        for name in model.MAP_LABELS:
            model.set_packing(p, name, "SEPARATE")
        self.assertEqual(
            [v.name for v in files.output_paths(p, "face")],
            ["face_left.png", "face_right.png", "face_coverage.png", "face.sdfproject.json"],
        )
        self.assertEqual(model.loads(model.dumps(p)), p)
        before = copy.deepcopy(p)
        with self.assertRaises(ValueError):
            model.set_packing(p, "missing", "R")
        with self.assertRaises(ValueError):
            model.set_packing(p, "character_left", "A")
        self.assertEqual(p, before)

    def test_missing_duplicate_and_unknown_routes_rejected(self):
        for packing in (
            None,
            {},
            {"character_left": "R"},
            dict(character_left="R", character_right="R", face_coverage="B"),
            dict(character_left="A", character_right="G", face_coverage="B"),
        ):
            p = project()
            p["settings"]["packing"] = packing
            with self.assertRaises(ValueError):
                model.dumps(p)
        p = project()
        p["encoding"]["colorspace"] = "sRGB"
        with self.assertRaisesRegex(ValueError, "encoding"):
            model.dumps(p)


class BundleFailureTests(unittest.TestCase):
    def setUp(self):
        self.p = project()
        for name in model.MAP_LABELS:
            model.set_packing(self.p, name, "SEPARATE")
        self.image = np.random.default_rng(901).random((8, 13, 3))

    def test_rollback_at_each_backup_and_commit_keeps_existing_outputs(self):
        for existing_count in (0, 2, 4):
            for fail_at in range(existing_count + 4):
                with self.subTest(
                    existing=existing_count, fail_at=fail_at
                ), tempfile.TemporaryDirectory() as tmp:
                    base = Path(tmp) / "face"
                    paths = files.output_paths(self.p, base)
                    original = {
                        path.name: f"original {i}".encode()
                        for i, path in enumerate(paths[:existing_count])
                    }
                    for name, data in original.items():
                        (Path(tmp) / name).write_bytes(data)
                    replace = files.os.replace
                    calls = 0

                    def fail_once(src, dst):
                        nonlocal calls
                        calls += 1
                        if calls == fail_at + 1:
                            raise OSError("injected replacement failure")
                        return replace(src, dst)

                    with patch.object(files.os, "replace", side_effect=fail_once):
                        with self.assertRaises(OSError):
                            files.export_bundle(self.p, self.image, base)
                    self.assertEqual(
                        {p.name: p.read_bytes() for p in Path(tmp).iterdir()}, original
                    )

    def test_cancel_after_each_staging_yield_keeps_outputs_and_removes_temporary_files(self):
        for stage_count in range(1, 5):
            with tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp) / "face"
                paths = files.export_bundle(self.p, self.image, base)
                original = {Path(p).name: Path(p).read_bytes() for p in paths}
                steps = files.export_steps(self.p, 1 - self.image, base)
                for _ in range(stage_count):
                    next(steps)
                steps.close()
                self.assertEqual({p.name: p.read_bytes() for p in Path(tmp).iterdir()}, original)

    def test_bad_verification_and_folder_collision_cannot_replace_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "face"
            paths = files.export_bundle(self.p, self.image, base)
            original = {Path(p).name: Path(p).read_bytes() for p in paths}
            with patch.object(
                files, "verify_steps", side_effect=IOError("numeric verification failure")
            ):
                with self.assertRaisesRegex(IOError, "numeric verification"):
                    files.export_bundle(self.p, 1 - self.image, base)
            self.assertEqual({p.name: p.read_bytes() for p in Path(tmp).iterdir()}, original)
            path = files.output_paths(self.p, Path(tmp) / "blocked")[1]
            path.mkdir()
            with self.assertRaisesRegex(ValueError, "folder"):
                files.export_bundle(self.p, self.image, Path(tmp) / "blocked")
            self.assertTrue(path.is_dir())


if __name__ == "__main__":
    unittest.main()
