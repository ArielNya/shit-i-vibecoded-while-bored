"""A tiny stdlib-only PNG writer for test sprite sheets."""

import struct
import zlib


def png(width: int, height: int, pixel) -> bytes:
    """pixel(x, y) -> (r, g, b, a)."""
    raw = b"".join(
        b"\0" + b"".join(bytes(pixel(x, y)) for x in range(width)) for y in range(height)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


TILE = 16
# 4x1 sheet: grass, dirt, stone, and an empty (transparent) cell.
COLORS = [(76, 175, 80, 255), (121, 85, 72, 255), (120, 120, 130, 255), (0, 0, 0, 0)]


def tile_sheet() -> bytes:
    def pixel(x, y):
        color = COLORS[x // TILE]
        if color[3] and (x % TILE == 0 or y == 0):  # a darker edge, so tiles read as tiles
            return tuple(max(0, c - 40) for c in color[:3]) + (255,)
        return color

    return png(TILE * len(COLORS), TILE, pixel)
