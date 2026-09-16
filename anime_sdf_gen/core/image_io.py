"""Small numerical image codecs: PNG8/16 and uncompressed FLOAT OpenEXR.

Writers yield bounded chunks for cancellation. Readers verify this writer's
format, not arbitrary third-party files. No Blender state or color transforms.
"""

from .messages import FileError, UserError, msg

from pathlib import Path
import struct
import zlib
import numpy as np


def _chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def _shape(array):
    if not (array.ndim == 2 or (array.ndim == 3 and array.shape[2] == 3)):
        raise UserError("Expected a grayscale or RGB array.")
    if not min(array.shape[:2]):
        raise UserError("The image is empty.")
    return array.shape[:2]


def png_chunks(codes):
    h, w = _shape(codes)
    if codes.dtype not in (np.dtype("uint8"), np.dtype("uint16")):
        raise UserError("Expected uint8 or uint16 PNG samples.")
    bits = codes.dtype.itemsize * 8
    color_type = 0 if codes.ndim == 2 else 2
    yield b"\x89PNG\r\n\x1a\n" + _chunk(
        b"IHDR", struct.pack(">IIBBBBB", w, h, bits, color_type, 0, 0, 0)
    )
    compressor = zlib.compressobj(4)
    for start in range(0, h, 16):
        rows = codes[::-1][start : start + 16]
        raw = b"".join(b"\0" + row.astype(">u2" if bits == 16 else "u1").tobytes() for row in rows)
        data = compressor.compress(raw)
        yield _chunk(b"IDAT", data) if data else b""
    data = compressor.flush()
    if data:
        yield _chunk(b"IDAT", data)
    yield _chunk(b"IEND", b"")


def png_scanlines(path):
    """Yield (shape, dtype), then bottom-origin rows, with bounded decompression."""
    with Path(path).open("rb") as stream:
        if stream.read(8) != b"\x89PNG\r\n\x1a\n":
            raise UserError("Invalid PNG signature.")
        header = None
        decoder = zlib.decompressobj()
        pending = bytearray()
        row = 0
        while True:
            prefix = stream.read(8)
            if len(prefix) != 8:
                raise UserError("Truncated PNG chunk.")
            length, kind = struct.unpack(">I4s", prefix)
            payload = stream.read(length)
            crc = stream.read(4)
            if len(payload) != length or len(crc) != 4:
                raise UserError("Truncated PNG chunk.")
            if zlib.crc32(kind + payload) & 0xFFFFFFFF != struct.unpack(">I", crc)[0]:
                raise UserError("PNG CRC verification failed.")
            if kind == b"IHDR":
                if header is not None or length != 13:
                    raise UserError("Invalid PNG header.")
                header = struct.unpack(">IIBBBBB", payload)
                w, h, bits, color_type = header[:4]
                if (
                    min(w, h) <= 0
                    or bits not in (8, 16)
                    or color_type not in (0, 2)
                    or header[4:] != (0, 0, 0)
                ):
                    raise UserError("Expected a grayscale or RGB PNG8/16.")
                channels = 1 if color_type == 0 else 3
                row_bytes = 1 + w * channels * (bits // 8)
                dtype = np.dtype("uint16" if bits == 16 else "uint8")
                shape = (h, w) if channels == 1 else (h, w, 3)
                yield shape, dtype
            elif header is None:
                raise UserError("Missing PNG header.")
            elif kind == b"IDAT":
                compressed = payload
                while True:
                    block = decoder.decompress(compressed, row_bytes * 16)
                    pending.extend(block)
                    compressed = decoder.unconsumed_tail
                    count = len(pending) // row_bytes
                    if row + count > h:
                        raise UserError("Too many PNG rows.")
                    for i in range(count):
                        start = i * row_bytes
                        if pending[start]:
                            raise UserError(
                                "Verification reader expects the author's unfiltered PNG rows."
                            )
                        values = np.frombuffer(
                            bytes(pending[start + 1 : start + row_bytes]),
                            dtype=">u2" if bits == 16 else "u1",
                        ).astype(dtype)
                        yield h - 1 - row, (
                            values.reshape(w) if channels == 1 else values.reshape(w, 3)
                        )
                        row += 1
                    del pending[: count * row_bytes]
                    if not compressed and len(block) < row_bytes * 16:
                        break
            elif kind == b"IEND":
                if (
                    payload
                    or stream.read(1)
                    or row != h
                    or pending
                    or not decoder.eof
                    or decoder.unused_data
                ):
                    raise UserError("Incomplete or invalid PNG end.")
                return
            else:
                raise UserError("Unexpected chunk in numerical PNG.")


def _collect(scanlines):
    shape, dtype = next(scanlines)
    image = np.empty(shape, dtype=dtype)
    for y, row in scanlines:
        image[y] = row
    return image


def read_png(path):
    return _collect(png_scanlines(path))


def _attribute(name, kind, value):
    return name.encode() + b"\0" + kind.encode() + b"\0" + struct.pack("<I", len(value)) + value


def exr_chunks(samples):
    h, w = _shape(samples)
    if samples.dtype != np.float32 or not np.isfinite(samples).all():
        raise UserError("Expected finite float32 EXR samples.")
    names = ("Y",) if samples.ndim == 2 else ("B", "G", "R")
    channels = (
        b"".join(name.encode() + b"\0" + struct.pack("<iB3xii", 2, 0, 1, 1) for name in names)
        + b"\0"
    )
    window = struct.pack("<4i", 0, 0, w - 1, h - 1)
    header = struct.pack("<II", 20000630, 2)
    for name, kind, value in (
        ("channels", "chlist", channels),
        ("compression", "compression", b"\0"),
        ("dataWindow", "box2i", window),
        ("displayWindow", "box2i", window),
        ("lineOrder", "lineOrder", b"\0"),
        ("pixelAspectRatio", "float", struct.pack("<f", 1)),
        ("screenWindowCenter", "v2f", struct.pack("<2f", 0, 0)),
        ("screenWindowWidth", "float", struct.pack("<f", 1)),
    ):
        header += _attribute(name, kind, value)
    header += b"\0"
    row_bytes = w * len(names) * 4
    offset = len(header) + 8 * h
    yield header + b"".join(struct.pack("<Q", offset + y * (row_bytes + 8)) for y in range(h))
    for y, row in enumerate(samples[::-1]):
        planar = row if len(names) == 1 else row[:, ::-1].T
        yield struct.pack("<ii", y, row_bytes) + planar.astype("<f4").tobytes()


def exr_scanlines(path):
    """Yield (shape, dtype), then bottom-origin FLOAT rows without a full read."""
    with Path(path).open("rb") as stream:
        if stream.read(8) != struct.pack("<II", 20000630, 2):
            raise UserError("Expected a single-part scanline OpenEXR.")

        def string():
            value = bytearray()
            while True:
                byte = stream.read(1)
                if not byte or len(value) > 255:
                    raise UserError("Invalid EXR string.")
                if byte == b"\0":
                    return value.decode("ascii")
                value.extend(byte)

        attributes = {}
        while True:
            name = string()
            if not name:
                break
            kind = string()
            length = struct.unpack("<I", stream.read(4))[0]
            value = stream.read(length)
            if name in attributes or len(value) != length:
                raise UserError("Invalid EXR attribute.")
            attributes[name] = (kind, value)
        if attributes.get("compression") != ("compression", b"\0") or attributes.get(
            "lineOrder"
        ) != ("lineOrder", b"\0"):
            raise UserError("Expected uncompressed increasing-Y EXR.")
        kind, window = attributes["dataWindow"]
        if kind != "box2i" or attributes.get("displayWindow") != (kind, window):
            raise UserError("Invalid EXR windows.")
        x0, y0, x1, y1 = struct.unpack("<4i", window)
        w, h = x1 + 1, y1 + 1
        if x0 or y0 or min(w, h) <= 0:
            raise UserError("Invalid EXR image size.")
        kind, chlist = attributes["channels"]
        if kind != "chlist":
            raise UserError("Invalid EXR channel list.")
        names, cp = [], 0
        while cp < len(chlist) and chlist[cp]:
            end = chlist.index(b"\0", cp)
            names.append(chlist[cp:end].decode("ascii"))
            cp = end + 1
            if chlist[cp : cp + 16] != struct.pack("<iB3xii", 2, 0, 1, 1):
                raise UserError("Expected full-resolution FLOAT EXR channels.")
            cp += 16
        if cp + 1 != len(chlist) or names not in (["Y"], ["B", "G", "R"]):
            raise UserError("Expected Y or RGB EXR channels.")
        offsets = struct.unpack("<" + "Q" * h, stream.read(8 * h))
        row_bytes = w * len(names) * 4
        yield (h, w) if len(names) == 1 else (h, w, 3), np.dtype("float32")
        for y, offset in enumerate(offsets):
            if offset != stream.tell():
                raise UserError("Invalid EXR scanline offset.")
            if struct.unpack("<ii", stream.read(8)) != (y, row_bytes):
                raise UserError("Invalid EXR scanline.")
            data = stream.read(row_bytes)
            if len(data) != row_bytes:
                raise UserError("Truncated EXR scanline.")
            row = np.frombuffer(data, dtype="<f4")
            if not np.isfinite(row).all():
                raise UserError("Invalid EXR pixel data.")
            yield h - 1 - y, row if len(names) == 1 else row.reshape(3, w)[::-1].T
        if stream.read(1):
            raise UserError("Unexpected EXR trailing data.")


def read_exr(path):
    return _collect(exr_scanlines(path))


def verify_steps(path, expected, bits):
    rows = exr_scanlines(path) if bits == 32 else png_scanlines(path)
    try:
        shape, dtype = next(rows)
        if shape != expected.shape or dtype != expected.dtype:
            raise FileError("The saved image failed numeric verification.")
        for count, (y, row) in enumerate(rows, 1):
            if not np.array_equal(row, expected[y]):
                raise FileError("The saved image failed numeric verification.")
            if count % 16 == 0:
                yield msg("Verify {filename}", filename=Path(path).name), count / len(expected)
    finally:
        rows.close()
