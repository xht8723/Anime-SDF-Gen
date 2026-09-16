"""Maximum-size filter/codec checks, with measured cooperative step duration."""

from pathlib import Path
import json, sys, time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from anime_sdf_gen.core.image_io import read_png, read_exr
from anime_sdf_gen.core import files, smoothing
from tests.samples import project
from tests.support import TestRun

RUN = TestRun("large-output").prepare()
OUT = RUN.out


def measured(steps):
    longest = 0.0
    start = time.perf_counter()
    count = 0
    while True:
        t = time.perf_counter()
        try:
            next(steps)
            count += 1
        except StopIteration as done:
            longest = max(longest, time.perf_counter() - t)
            return done.value, {
                "seconds": time.perf_counter() - start,
                "steps": count,
                "longest_step_seconds": longest,
            }
        longest = max(longest, time.perf_counter() - t)


n = 4096
x = (np.arange(n, dtype=np.float32) + 0.5) / n
fields = np.empty((n, n, 2), np.float32)
fields[..., 0] = 0.08 + 0.84 * x[None, :] + 0.04 * np.sin(70 * x[:, None])
fields[..., 1] = fields[:, ::-1, 0]
fields[:32] = 0
fields[-32:] = 1
filtered, profile = measured(smoothing.smooth_steps(fields, 8, True))
assert np.array_equal(filtered[..., 1], filtered[:, ::-1, 0])
assert np.array_equal(filtered[:32], fields[:32]) and np.array_equal(filtered[-32:], fields[-32:])
assert not np.array_equal(filtered[32:-32], fields[32:-32])
del fields
a = np.empty((n, n, 3), np.float32)
a[..., :2] = filtered
a[..., 2] = 1
del filtered
p = project()
p["settings"].update(resolution=n, smoothing=8)
report = {"status": "RUNNING", "resolution": n, "smoothing": profile, "formats": {}}
for bits in (8, 16, 32):
    p["settings"]["bit_depth"] = bits
    paths, profile = measured(files.export_steps(p, a, OUT / f"face_{bits}"))
    actual = (read_exr if bits == 32 else read_png)(paths[0])
    expected = files.quantize(a, bits)
    assert np.array_equal(actual, expected) and actual.dtype == expected.dtype
    del actual, expected
    profile["bytes"] = Path(paths[0]).stat().st_size
    report["formats"][str(bits)] = profile
    (OUT / "large-output.json").write_text(json.dumps(report, indent=2))
report["status"] = "PASS"
(OUT / "large-output.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report), flush=True)
