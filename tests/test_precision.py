"""Storage precision, codec integrity and cancellation across all formats."""

from tests.samples import image
from anime_sdf_gen.core.image_io import read_png, read_exr
from anime_sdf_gen.core.thresholds import INTERIOR_MAX, INTERIOR_MIN, decode
from copy import deepcopy
from pathlib import Path
import itertools
import struct
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from anime_sdf_gen.core import model, files, compile, geometry
from anime_sdf_gen.core.jobs import run
from anime_sdf_gen.core.image_io import png_chunks, exr_chunks
from tests.samples import project


class PrecisionTests(unittest.TestCase):
    def test_defaults_strict_schema_and_settings(self):
        p = project()
        self.assertEqual(p["format_version"], 4)
        self.assertEqual((p["settings"]["bit_depth"], p["settings"]["smoothing"]), (16, 0))
        for bits in (8, 16, 32):
            p["settings"].update(bit_depth=bits, smoothing=8)
            self.assertEqual(model.loads(model.dumps(p)), p)
        for key, values in [
            ("bit_depth", (None, True, 16.0, 24, "16")),
            ("smoothing", (None, True, -1, 8.01, float("nan"), float("inf"))),
        ]:
            for value in values:
                bad = deepcopy(p)
                bad["settings"][key] = value
                with self.assertRaises(ValueError):
                    model.dumps(bad)
        for old in (1, 2, 3):
            p["format_version"] = old
            with self.assertRaisesRegex(ValueError, "Unsupported project"):
                model.dumps(p)

    def test_quantization_error_and_endpoint_semantics(self):
        a = image()
        for bits in (8, 16, 32):
            encoded = files.quantize(a, bits)
            decoded = encoded if bits == 32 else encoded.astype(float) / ((1 << bits) - 1)
            np.testing.assert_array_equal(decoded[0, 0], [0, 1, 1])
            np.testing.assert_array_equal(decoded[-1, -1], [1, 0, 0])
            self.assertGreater(decoded[0, 1, 0], 0)
            self.assertLess(decoded[0, 1, 1], 1)
            self.assertTrue(np.isin(decoded[..., 2], (0, 1)).all())
            if bits != 32:
                limit = (1 << bits) - 1
                interior = (a[..., :2] >= 1 / limit) & (a[..., :2] <= 1 - 1 / limit)
                self.assertLessEqual(
                    np.abs(decoded[..., :2] - a[..., :2])[interior].max(), 0.500001 / limit
                )
            self.assertTrue(decode(decoded[0, 0, 0], 0))
            self.assertFalse(decode(decoded[0, 0, 1], 1))
        self.assertEqual(files.quantize(a, 16)[0, 2, 0], files.quantize(a, 16)[0, 2, 1])
        self.assertNotEqual(files.quantize(a, 32)[0, 2, 0], files.quantize(a, 32)[0, 2, 1])

    def test_all_packing_routes_all_depths_exactly_roundtrip(self):
        a = image()
        with tempfile.TemporaryDirectory() as tmp:
            for bits in (8, 16, 32):
                for index, routes in enumerate(itertools.product(model.OUTPUT_ROUTES, repeat=3)):
                    assigned = [c for c in routes if c != "SEPARATE"]
                    if len(set(assigned)) != len(assigned):
                        continue
                    p = project()
                    p["settings"].update(
                        bit_depth=bits, packing=dict(zip(model.MAP_LABELS, routes))
                    )
                    base = Path(tmp) / str(bits) / str(index) / "face.PNG"
                    paths = files.export_bundle(p, a, base)
                    info = files.load_project(paths[-1])
                    self.assertEqual(tuple(map(Path, paths)), files.output_paths(p, base))
                    codes = files.quantize(a, bits)
                    for path, entry in zip(paths, info["textures"]):
                        self.assertEqual(Path(path).suffix, ".exr" if bits == 32 else ".png")
                        self.assertEqual(entry["bits"], bits)
                        self.assertEqual(entry["sample_type"], "FLOAT" if bits == 32 else "UNORM")
                        self.assertEqual(entry["format"], "OPEN_EXR" if bits == 32 else "PNG")
                        reader = read_exr if bits == 32 else read_png
                        actual = reader(path)
                        expected = files.packed_codes(codes, entry["channels"])
                        self.assertEqual(actual.dtype, expected.dtype)
                        np.testing.assert_array_equal(actual, expected)
                        if bits != 32:
                            self.assertEqual(Path(path).read_bytes()[24], bits)

    def test_extensions_and_format_switch_do_not_delete_other_outputs(self):
        p = project()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "face"
            pngs = files.export_bundle(p, image(), base)
            png = Path(pngs[0]).read_bytes()
            p["settings"]["bit_depth"] = 32
            self.assertEqual(files.output_paths(p, str(base) + ".EXR")[0], base.with_suffix(".exr"))
            self.assertEqual(files.output_paths(p, str(base) + ".PNG")[0], base.with_suffix(".exr"))
            files.export_bundle(p, image(), base)
            self.assertEqual(Path(pngs[0]).read_bytes(), png)
            self.assertTrue(base.with_suffix(".exr").is_file())

    def test_cancel_during_quantization_encoding_and_before_commit(self):
        a = image()
        for bits in (8, 16, 32):
            p = project()
            p["settings"]["bit_depth"] = bits
            model.set_packing(p, "character_right", "SEPARATE")
            with tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp) / "face"
                files.export_bundle(p, a, base)
                original = {q.name: q.read_bytes() for q in Path(tmp).iterdir()}
                for target in (
                    "Encode numerical",
                    "Encode face.",
                    "Encode face_right.",
                    "Verify face.",
                    "Verify face_right.",
                    "Commit verified",
                ):
                    steps = files.export_steps(p, 1 - a, base)
                    for label, _ in steps:
                        if str(label).startswith(target):
                            steps.close()
                            break
                    else:
                        self.fail("Missing cancellation point: " + target)
                    self.assertEqual(
                        {q.name: q.read_bytes() for q in Path(tmp).iterdir()}, original
                    )

    def test_verification_failure_and_exr_commit_rollback(self):
        p = project()
        p["settings"]["bit_depth"] = 32
        for name in model.MAP_LABELS:
            model.set_packing(p, name, "SEPARATE")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "face"
            files.export_bundle(p, image(), base)
            original = {q.name: q.read_bytes() for q in Path(tmp).iterdir()}
            with patch.object(
                files, "exr_chunks", side_effect=lambda data: exr_chunks(data + np.float32(0.001))
            ):
                with self.assertRaisesRegex(IOError, "numeric verification"):
                    files.export_bundle(p, image(), base)
            real = files.os.replace
            for failure in range(1, 9):
                counter = [0]

                def replace(src, dst):
                    counter[0] += 1
                    if counter[0] == failure:
                        raise OSError("injected")
                    return real(src, dst)

                with patch.object(files.os, "replace", side_effect=replace):
                    with self.assertRaises(OSError):
                        files.export_bundle(p, 1 - image(), base)
                self.assertEqual({q.name: q.read_bytes() for q in Path(tmp).iterdir()}, original)

    def test_codec_corruption_and_sample_type_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test"
            for bits in (8, 16, 32):
                codes = files.quantize(image(), bits)
                payload = b"".join(exr_chunks(codes) if bits == 32 else png_chunks(codes))
                reader = read_exr if bits == 32 else read_png
                p.write_bytes(payload[:-3])
                with self.assertRaises((ValueError, struct.error)):
                    reader(p)
                bad = bytearray(payload)
                if bits == 32:
                    # FLOAT->HALF declaration, without changing stored samples.
                    at = payload.index(b"B\0" + struct.pack("<i", 2)) + 2
                    bad[at] = 1
                else:
                    bad[35] ^= 1
                p.write_bytes(bad)
                with self.assertRaises(ValueError):
                    reader(p)
        for bits in (8, 16, 32):
            a = image()
            a[2, 3, 0] = float("nan")
            with self.assertRaises(ValueError):
                files.quantize(a, bits)

    def test_uv_interpolation_cannot_round_ordinary_values_to_sentinels(self):
        fields = np.ones((64, 64, 2), np.float32)
        fields[:, :32, 0] = INTERIOR_MAX
        fields[..., 1] = 0
        fields[:, :32, 1] = INTERIOR_MIN
        uv = np.array([[[0, 0], [1, 0], [1, 1]], [[0, 0], [1, 1], [0, 1]]], float)
        projected = np.concatenate((0.499 + uv * 0.002, np.zeros((2, 3, 1))), axis=2)
        out = run(
            geometry.bake_steps(fields, uv, projected, np.zeros((64, 64)), np.ones(2, bool), 8)
        )
        np.testing.assert_array_equal(out[..., 0], INTERIOR_MAX)
        np.testing.assert_array_equal(out[..., 1], INTERIOR_MIN)

    def test_compilation_keeps_transitions_beyond_16bit_endpoint_bounds(self):
        p = project(2)
        # The narrow progress interval forces ordinary values near the endpoint.
        frames = model.sweep(p, model.LTR)
        middle = deepcopy(frames[1])
        middle["id"] = model.uid()
        middle["progress"] = 1e-6
        frames.insert(1, middle)
        model.synchronize_mirror(p)
        data = compile.compile_project(p, 64)
        ordinary = data[..., 0][(data[..., 0] > 0) & (data[..., 0] < 1)]
        self.assertTrue(len(ordinary))
        self.assertLess(ordinary.max(), 1 / 65535)


if __name__ == "__main__":
    unittest.main()
