"""Numerical RGB/grayscale PNGs, verified output bundles, and project recovery."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import struct
import uuid
import zlib
import numpy as np
from .model import dumps, loads, MAP_LABELS, validate_packing, validate_project


def quantize(image):
    # Endpoint handling belongs to the two logical thresholds, before packing.
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('Expected canonical left, right, coverage image data.')
    if not np.isfinite(image).all():
        raise ValueError("Texture contains non-finite values.")
    codes = np.rint(np.clip(image, 0, 1)*65535).astype(np.uint16)
    for c in (0, 1):
        interior = (image[..., c] > 0) & (image[..., c] < 1)
        codes[..., c][interior] = codes[..., c][interior].clip(1, 65534)
    return codes


def _chunk(kind, data):
    return struct.pack(">I", len(data))+kind+data+struct.pack(">I", zlib.crc32(kind+data) & 0xffffffff)


def png_bytes(codes):
    if codes.dtype != np.uint16 or not (codes.ndim == 2 or (codes.ndim == 3 and codes.shape[2] == 3)):
        raise ValueError("Expected a uint16 grayscale or RGB array.")
    h, w = codes.shape[:2]
    color_type = 0 if codes.ndim == 2 else 2
    compressor = zlib.compressobj(4)
    packed = []
    for row in codes[::-1]:
        packed.append(compressor.compress(b"\x00"+row.astype(">u2").tobytes()))
    packed.append(compressor.flush())
    return (b"\x89PNG\r\n\x1a\n"+_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 16, color_type, 0, 0, 0))+
            _chunk(b"IDAT", b"".join(packed))+_chunk(b"IEND", b""))


def read_png16(path):
    data = Path(path).read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid PNG signature.")
    pos, chunks, header = 8, [], None
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos+4])[0]
        kind, payload = data[pos+4:pos+8], data[pos+8:pos+8+length]
        crc = struct.unpack(">I", data[pos+8+length:pos+12+length])[0]
        if zlib.crc32(kind+payload) & 0xffffffff != crc:
            raise ValueError("PNG CRC verification failed.")
        if kind == b"IHDR": header = struct.unpack(">IIBBBBB", payload)
        if kind == b"IDAT": chunks.append(payload)
        pos += 12+length
    if header is None or header[2:] not in ((16, 0, 0, 0, 0), (16, 2, 0, 0, 0)):
        raise ValueError("Expected a non-interlaced grayscale16 or RGB16 PNG.")
    w, h = header[:2]
    channels = 1 if header[3] == 0 else 3
    raw = np.frombuffer(zlib.decompress(b"".join(chunks)), dtype=np.uint8).reshape(h, 1+w*channels*2)
    if raw[:, 0].any():
        raise ValueError("Verification reader expects the author's unfiltered PNG rows.")
    shape = (h, w) if channels == 1 else (h, w, 3)
    return np.frombuffer(raw[:, 1:].copy().tobytes(), dtype=">u2").reshape(shape)[::-1].astype(np.uint16)


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
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
    packing = validate_packing(project['settings']['packing'])
    base = Path(base)
    if base.suffix.lower() == ".png": base = base.with_suffix("")
    channels = {route: name for name, route in packing.items() if route != 'SEPARATE'}
    textures = [{'path': Path(str(base)+'.png'), 'channels': channels}] if channels else []
    for name, suffix in zip(MAP_LABELS, ('left', 'right', 'coverage')):
        if packing[name] == 'SEPARATE':
            textures.append({'path': Path(str(base)+'_'+suffix+'.png'), 'channels': {'Y': name}})
    return textures, Path(str(base)+'.sdfproject.json')


def output_paths(project, base):
    textures, sidecar = output_layout(project, base)
    return tuple(t['path'] for t in textures)+(sidecar,)


def packed_codes(codes, channels):
    indices = {name: i for i, name in enumerate(MAP_LABELS)}
    if 'Y' in channels:
        return codes[..., indices[channels['Y']]]
    packed = np.zeros_like(codes)
    for channel, name in channels.items():
        packed[..., 'RGB'.index(channel)] = codes[..., indices[name]]
    return packed


def export_steps(project, image, base):
    """Stage cancellable image work, then commit the complete verified bundle."""
    validate_project(project)
    textures, sidecar = output_layout(project, base)
    destinations = [t['path'] for t in textures]+[sidecar]
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    if any(path.exists() and not path.is_file() for path in destinations):
        raise ValueError('An output filename points to a folder. Choose another file name.')
    token = uuid.uuid4().hex
    stages = [p.with_name(p.name+"."+token+".tmp") for p in destinations]
    backups = [p.with_name(p.name+"."+token+".bak") for p in destinations]
    moved, committed = [], []
    complete = False
    try:
        codes = quantize(image)
        saved = deepcopy(project)
        saved['textures'] = []
        for i, texture in enumerate(textures):
            packed = packed_codes(codes, texture['channels'])
            payload = png_bytes(packed)
            stages[i].write_bytes(payload)
            if not np.array_equal(read_png16(stages[i]), packed):
                raise IOError("The saved PNG failed numeric verification.")
            saved['textures'].append({'file': texture['path'].name,
                'sha256': hashlib.sha256(payload).hexdigest(), 'width': image.shape[1],
                'height': image.shape[0], 'bits': 16, 'colorspace': 'Non-Color',
                'color_type': 'GRAYSCALE' if packed.ndim == 2 else 'RGB', 'channels': texture['channels']})
            yield 'Verified '+texture['path'].name, .99+.008*(i+1)/len(textures)
        stages[-1].write_text(dumps(saved), encoding="utf-8")
        if loads(stages[-1].read_text(encoding="utf-8")) != saved:
            raise IOError("Project round-trip verification failed.")
        yield 'Commit verified output files', .999
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
    steps = export_steps(project, image, base)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


def load_project(path):
    return loads(Path(path).read_text(encoding="utf-8"))
