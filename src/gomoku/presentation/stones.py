"""Anti-aliased 3D stone sprites as PNG PhotoImages (no Pillow)."""

from __future__ import annotations

import struct
import zlib
from math import sqrt

import tkinter as tk


def sphere_image(
    master: tk.Misc,
    radius: int,
    kind: str,
    cache: dict[tuple, tk.PhotoImage],
) -> tk.PhotoImage:
    """Return a cached PhotoImage of a lit sphere."""
    radius = max(6, int(radius))
    key = (kind, radius)
    existing = cache.get(key)
    if existing is not None:
        return existing
    png = _render_png(radius, kind == "black")
    image = tk.PhotoImage(data=png, master=master)
    cache[key] = image
    return image


def _render_png(radius: int, black: bool) -> bytes:
    pad = 3
    size = radius * 2 + pad * 2
    cx = cy = size / 2.0
    lx, ly, lz = _norm(-0.42, -0.58, 0.70)
    pixels = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in (0.25, 0.75):
                for sx in (0.25, 0.75):
                    dx = (x + sx - cx) / radius
                    dy = (y + sy - cy) / radius
                    sample = _shade(dx, dy, lx, ly, lz, black)
                    for index in range(4):
                        acc[index] += sample[index]
            offset = (y * size + x) * 4
            pixels[offset] = min(255, int(acc[0] * 0.25 + 0.5))
            pixels[offset + 1] = min(255, int(acc[1] * 0.25 + 0.5))
            pixels[offset + 2] = min(255, int(acc[2] * 0.25 + 0.5))
            pixels[offset + 3] = min(255, int(acc[3] * 0.25 + 0.5))
    return _png(size, size, bytes(pixels))


def _shade(
    dx: float,
    dy: float,
    lx: float,
    ly: float,
    lz: float,
    black: bool,
) -> tuple[float, float, float, float]:
    dist2 = dx * dx + dy * dy
    dist = sqrt(dist2) if dist2 > 0 else 0.0
    if dist >= 1.12:
        return (0.0, 0.0, 0.0, 0.0)
    if dist >= 1.0:
        alpha = max(0.0, 1.0 - (dist - 1.0) / 0.12) * 255.0
        nx, ny, nz = dx, dy, 0.05
    else:
        alpha = 255.0
        nz = sqrt(max(0.0, 1.0 - dist2))
        nx, ny = dx, dy
    length = sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    nx, ny, nz = nx / length, ny / length, nz / length
    ndot = max(0.0, nx * lx + ny * ly + nz * lz)
    half_z = lz + 1.0
    spec = max(0.0, nx * lx + ny * ly + nz * half_z / sqrt(lx * lx + ly * ly + half_z * half_z))
    spec = spec ** 28
    if black:
        ambient = 22.0
        color = (
            ambient + 58 * ndot + 200 * spec,
            ambient + 58 * ndot + 200 * spec,
            ambient + 62 * ndot + 210 * spec,
        )
    else:
        ambient = 168.0
        color = (
            ambient + 82 * ndot + 55 * spec,
            ambient + 78 * ndot + 52 * spec,
            ambient + 68 * ndot + 48 * spec,
        )
    rim = max(0.0, 1.0 - nz) ** 2
    if black:
        color = (color[0] + 18 * rim, color[1] + 18 * rim, color[2] + 22 * rim)
    else:
        color = (color[0] - 12 * rim, color[1] - 14 * rim, color[2] - 18 * rim)
    return (
        max(0.0, min(255.0, color[0])),
        max(0.0, min(255.0, color[1])),
        max(0.0, min(255.0, color[2])),
        alpha,
    )


def _norm(x: float, y: float, z: float) -> tuple[float, float, float]:
    length = sqrt(x * x + y * y + z * z) or 1.0
    return x / length, y / length, z / length


def _png(width: int, height: int, rgba: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = bytearray()
    stride = width * 4
    for row in range(height):
        raw.append(0)
        raw.extend(rgba[row * stride : (row + 1) * stride])
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
