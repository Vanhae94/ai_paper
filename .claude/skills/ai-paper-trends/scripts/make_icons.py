#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_icons.py — 홈 화면/파비콘용 앱 아이콘 PNG 생성 (표준 라이브러리만 사용, pip 불필요)

Aurora Ink 테마: 제이드→틸 대각 그라데이션 배경 + 흰색 sparkle(astroid) 아이콘.
zlib+struct로 PNG를 직접 인코딩하고, 슈퍼샘플링으로 안티에일리어싱한다.
출력: <root>/_assets/icon-180.png, icon-192.png, icon-512.png

사용: py make_icons.py --root "C:\\...\\논문정리"
"""
import argparse
import math
import os
import struct
import sys
import zlib


def write_png(path, w, h, rgb):
    """rgb: bytearray length w*h*3 (opaque) → 8-bit RGBA PNG."""
    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)  # filter type 0
        row = rgb[y * stride:(y + 1) * stride]
        # RGB → RGBA (alpha 255)
        for x in range(w):
            raw += row[x * 3:x * 3 + 3]
            raw.append(255)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # RGBA
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


def lerp(a, b, t):
    return a + (b - a) * t


def astro(x, y, cx, cy, R, e=0.6):
    """astroid(4-cusp 별) 안쪽이면 <=1. 축(상하좌우) 방향으로 뾰족한 sparkle."""
    dx = abs(x - cx) / R
    dy = abs(y - cy) / R
    return dx ** e + dy ** e


def pixel(x, y):
    """x,y ∈ [0,1) → (r,g,b)."""
    # 대각 제이드→틸 그라데이션
    t = (x + y) / 2.0
    r = lerp(0x34, 0x1A, t)
    g = lerp(0xE2, 0xA2, t)
    b = lerp(0x9B, 0xC6, t)
    # 좌상단 광원 느낌: 살짝 밝게 / 우하단 살짝 어둡게
    lum = 1.0 + 0.10 * (0.5 - t)
    r, g, b = r * lum, g * lum, b * lum

    big = astro(x, y, 0.5, 0.485, 0.33)
    small = astro(x, y, 0.735, 0.265, 0.108)
    if big <= 1.0 or small <= 1.0:
        return (255, 255, 255)
    # 큰 sparkle 주변 부드러운 후광
    halo = max(0.0, (1.7 - big) / 0.7)
    a = halo * halo * 0.22
    if a > 0:
        r = lerp(r, 255, a); g = lerp(g, 255, a); b = lerp(b, 255, a)
    return (int(max(0, min(255, r))), int(max(0, min(255, g))), int(max(0, min(255, b))))


def render(target, ss):
    """target 크기를 ss배 슈퍼샘플 후 박스 다운스케일."""
    W = target * ss
    src = bytearray(W * W * 3)
    for py in range(W):
        yy = (py + 0.5) / W
        base = py * W * 3
        for px in range(W):
            r, g, b = pixel((px + 0.5) / W, yy)
            i = base + px * 3
            src[i] = r; src[i + 1] = g; src[i + 2] = b
    out = bytearray(target * target * 3)
    n = ss * ss
    for oy in range(target):
        for ox in range(target):
            R = G = B = 0
            for dy in range(ss):
                syb = ((oy * ss + dy) * W + ox * ss) * 3
                for dx in range(ss):
                    j = syb + dx * 3
                    R += src[j]; G += src[j + 1]; B += src[j + 2]
            oi = (oy * target + ox) * 3
            out[oi] = R // n; out[oi + 1] = G // n; out[oi + 2] = B // n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    args = ap.parse_args()
    assets = os.path.join(args.root, "_assets")
    os.makedirs(assets, exist_ok=True)
    for size, ss in [(512, 2), (192, 4), (180, 4)]:
        rgb = render(size, ss)
        path = os.path.join(assets, f"icon-{size}.png")
        write_png(path, size, size, rgb)
        print(f"WROTE {path} ({size}x{size}, ss={ss})")
    print("STATUS=ok")


if __name__ == "__main__":
    main()
