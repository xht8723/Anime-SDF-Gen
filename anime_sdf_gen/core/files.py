"""Numerical image encoding, verified output bundles, and project recovery."""

from .messages import FileError, UserError, msg

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import uuid
import numpy as np
from .model import dumps, loads, MAP_LABELS, BIT_DEPTHS, validate_packing, validate_project
from .thresholds import INTERIOR_MIN, INTERIOR_MAX
from .jobs import run
from .image_io import png_chunks, exr_chunks, verify_steps


def quantize_steps(image, bits=16):
    # Endpoint handling belongs to logical thresholds before channel packing.
    if image.ndim != 3 or image.shape[2] != 3:
        raise UserError("Expected canonical left, right, coverage image data.")
    if type(bits) is not int or bits not in BIT_DEPTHS:
        raise UserError("Unsupported output bit depth.")
    dtype = np.float32 if bits == 32 else np.uint16 if bits == 16 else np.uint8
    codes = np.empty(image.shape, dtype=dtype)
    maximum = (1 << bits) - 1 if bits != 32 else 1
    for row in range(0, len(image), 32):
        block = image[row : row + 32]
        if not np.isfinite(block).all():
            raise UserError("Texture contains non-finite values.")
        clipped = np.clip(block, 0, 1).astype(np.float64)
        encoded = clipped.astype(dtype) if bits == 32 else np.rint(clipped * maximum).astype(dtype)
        for c in (0, 1):
            interior = (block[..., c] > 0) & (block[..., c] < 1)
            lo, hi = (INTERIOR_MIN, INTERIOR_MAX) if bits == 32 else (1, maximum - 1)
            encoded[..., c][interior] = encoded[..., c][interior].clip(lo, hi)
        codes[row : row + 32] = encoded
        yield msg("Encode numerical precision"), 0.985 + 0.005 * min(row + 32, len(image)) / len(
            image
        )
    return codes


def quantize(image, bits=16):
    return run(quantize_steps(image, bits))


def output_extension(project):
    bits = project["settings"]["bit_depth"]
    if type(bits) is not int or bits not in BIT_DEPTHS:
        raise UserError("Unsupported output bit depth.")
    return ".exr" if bits == 32 else ".png"


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def output_layout(project, base):
    """The exact files/channels shared by Confirm, overwrite checks and export."""
    packing = validate_packing(project["settings"]["packing"])
    base = Path(base)
    if base.suffix.lower() in (".png", ".exr"):
        base = base.with_suffix("")
    extension = output_extension(project)
    channels = {route: name for name, route in packing.items() if route != "SEPARATE"}
    textures = [{"path": Path(str(base) + extension), "channels": channels}] if channels else []
    for name, suffix in zip(MAP_LABELS, ("left", "right", "coverage")):
        if packing[name] == "SEPARATE":
            textures.append(
                {"path": Path(str(base) + "_" + suffix + extension), "channels": {"Y": name}}
            )
    return textures, Path(str(base) + ".sdfproject.json")


def output_paths(project, base):
    textures, sidecar = output_layout(project, base)
    return tuple(t["path"] for t in textures) + (sidecar,)


def packed_codes(codes, channels):
    indices = {name: i for i, name in enumerate(MAP_LABELS)}
    if "Y" in channels:
        return codes[..., indices[channels["Y"]]]
    packed = np.zeros_like(codes)
    for channel, name in channels.items():
        packed[..., "RGB".index(channel)] = codes[..., indices[name]]
    return packed


def export_steps(project, image, base):
    """Stage cancellable image work, then commit the complete verified bundle."""
    validate_project(project)
    textures, sidecar = output_layout(project, base)
    destinations = [t["path"] for t in textures] + [sidecar]
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    if any(path.exists() and not path.is_file() for path in destinations):
        raise UserError("An output filename points to a folder. Choose another file name.")
    token = uuid.uuid4().hex
    stages = [p.with_name(p.name + "." + token + ".tmp") for p in destinations]
    backups = [p.with_name(p.name + "." + token + ".bak") for p in destinations]
    moved, committed = [], []
    complete = False
    try:
        bits = project["settings"]["bit_depth"]
        codes = yield from quantize_steps(image, bits)
        saved = deepcopy(project)
        saved["textures"] = []
        for i, texture in enumerate(textures):
            packed = packed_codes(codes, texture["channels"])
            digest = hashlib.sha256()
            chunks = exr_chunks(packed) if bits == 32 else png_chunks(packed)
            with stages[i].open("wb") as stream:
                for chunk in chunks:
                    stream.write(chunk)
                    digest.update(chunk)
                    yield msg(
                        "Encode {filename}", filename=texture["path"].name
                    ), 0.99 + 0.007 * i / len(textures)
                stream.flush()
            for label, progress in verify_steps(stages[i], packed, bits):
                yield msg("Verify {filename}", filename=texture["path"].name), 0.99 + 0.008 * (
                    i + progress
                ) / len(textures)
            saved["textures"].append(
                {
                    "file": texture["path"].name,
                    "sha256": digest.hexdigest(),
                    "width": image.shape[1],
                    "height": image.shape[0],
                    "bits": bits,
                    "colorspace": "Non-Color",
                    "format": "OPEN_EXR" if bits == 32 else "PNG",
                    "sample_type": "FLOAT" if bits == 32 else "UNORM",
                    "color_type": "GRAYSCALE" if packed.ndim == 2 else "RGB",
                    "channels": texture["channels"],
                }
            )
            yield msg("Verified {filename}", filename=texture["path"].name), 0.99 + 0.008 * (
                i + 1
            ) / len(textures)
        stages[-1].write_text(dumps(saved), encoding="utf-8")
        if loads(stages[-1].read_text(encoding="utf-8")) != saved:
            raise FileError("Project round-trip verification failed.")
        yield msg("Commit verified output files"), 0.999
        # No yield while replacing files: cancellation cannot interrupt a commit.
        for dst, backup in zip(destinations, backups):
            if dst.exists():
                os.replace(dst, backup)
                moved.append((dst, backup))
        for tmp, dst in zip(stages, destinations):
            os.replace(tmp, dst)
            committed.append(dst)
        complete = True
        return tuple(str(path) for path in destinations)
    except BaseException:
        for dst in committed:
            dst.unlink(missing_ok=True)
        for dst, backup in reversed(moved):
            os.replace(backup, dst)
        raise
    finally:
        for tmp in stages:
            tmp.unlink(missing_ok=True)
        # Failed rollback backups are deliberately retained for manual recovery.
        if complete:
            for backup in backups:
                backup.unlink(missing_ok=True)


def export_bundle(project, image, base):
    return run(export_steps(project, image, base))


def load_project(path):
    return loads(Path(path).read_text(encoding="utf-8"))
