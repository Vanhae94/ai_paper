#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_icons.py — 홈 화면/파비콘용 앱 아이콘 PNG 생성 (표준 라이브러리만, pip 불필요)

Aurora Ink 테마: 제이드→틸 대각 그라데이션 배경 위에
'AI 논문' 모티프 = 흰색 문서(텍스트 줄) + 제이드 AI 반짝임(sparkle).
zlib+struct로 PNG를 직접 인코딩하고 슈퍼샘플링으로 안티에일리어싱한다.
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
    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        row = rgb[y * stride:(y + 1) * stride]
        for x in range(w):
            raw += row[x * 3:x * 3 + 3]
            raw.append(255)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def blend(c, other, a):
    return [lerp(c[0], other[0], a), lerp(c[1], other[1], a), lerp(c[2], other[2], a)]


def rbox(x, y, x0, y0, x1, y1, r):
    """둥근 사각형 signed distance. <=0 이면 내부."""
    ccx, ccy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2, (y1 - y0) / 2
    px, py = abs(x - ccx) - (hx - r), abs(y - ccy) - (hy - r)
    return math.hypot(max(px, 0.0), max(py, 0.0)) + min(max(px, py), 0.0) - r


def bar(x, y, x0, x1, cy, h):
    """가로 둥근 막대(텍스트 줄) SDF."""
    return rbox(x, y, x0, cy - h / 2, x1, cy + h / 2, h / 2)


def astro(x, y, cx, cy, R, e=0.6):
    """astroid(4-cusp) sparkle: <=1 이면 내부."""
    return (abs(x - cx) / R) ** e + (abs(y - cy) / R) ** e


# 팔레트
GRAD_A = (0x34, 0xE2, 0x9B)   # 제이드(좌상)
GRAD_B = (0x1A, 0xA2, 0xC6)   # 틸(우하)
PAGE = (255, 255, 255)
TITLE = (0x16, 0xA6, 0x73)    # 제목 줄(제이드, 흰 배경에서 대비)
BODY = (0x9C, 0xAB, 0xBD)     # 본문 줄(회색)
SPARK = (0x10, 0xC4, 0x86)    # AI 반짝임(밝은 제이드)

# 문서 영역
PX0, PY0, PX1, PY1 = 0.30, 0.33, 0.70, 0.83
PR = 0.045
# 반짝임(문서 우상단 모서리에 걸침)
SPX, SPY, SPR = 0.695, 0.305, 0.135


def pixel(x, y):
    t = (x + y) / 2.0
    r = lerp(GRAD_A[0], GRAD_B[0], t)
    g = lerp(GRAD_A[1], GRAD_B[1], t)
    b = lerp(GRAD_A[2], GRAD_B[2], t)
    lum = 1.0 + 0.10 * (0.5 - t)
    col = [r * lum, g * lum, b * lum]

    # 문서 그림자(깊이감)
    sd = rbox(x, y, PX0 + 0.015, PY0 + 0.024, PX1 + 0.015, PY1 + 0.024, PR)
    if sd < 0.04:
        col = blend(col, [0, 0, 0], clamp((0.04 - sd) / 0.05, 0, 1) * 0.26)

    # 문서(흰 페이지)
    on_page = rbox(x, y, PX0, PY0, PX1, PY1, PR) <= 0
    if on_page:
        col = list(PAGE)
        # 텍스트 줄
        if bar(x, y, 0.375, 0.560, 0.455, 0.040) <= 0:
            col = list(TITLE)                       # 제목(굵게, 제이드)
        elif (bar(x, y, 0.375, 0.625, 0.560, 0.024) <= 0
              or bar(x, y, 0.375, 0.625, 0.645, 0.024) <= 0
              or bar(x, y, 0.375, 0.545, 0.730, 0.024) <= 0):
            col = list(BODY)                        # 본문 줄

    # AI 반짝임(제이드) — 흰 페이지 위/그라데이션 걸침
    if astro(x, y, SPX, SPY, SPR) <= 1.0:
        col = list(SPARK)
    elif (not on_page) and astro(x, y, SPX, SPY, SPR * 1.18) <= 1.0:
        col = list(PAGE)                            # 그라데이션 쪽엔 흰 테두리로 분리
    # 작은 보조 반짝임
    if astro(x, y, 0.815, 0.475, 0.045) <= 1.0:
        col = list(PAGE)

    return (int(clamp(col[0], 0, 255)), int(clamp(col[1], 0, 255)), int(clamp(col[2], 0, 255)))


def render(target, ss):
    W = target * ss
    src = bytearray(W * W * 3)
    for py in range(W):
        yy = (py + 0.5) / W
        base = py * W * 3
        for px in range(W):
            rr, gg, bb = pixel((px + 0.5) / W, yy)
            i = base + px * 3
            src[i] = rr; src[i + 1] = gg; src[i + 2] = bb
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
        write_png(os.path.join(assets, f"icon-{size}.png"), size, size, render(size, ss))
        print(f"WROTE icon-{size}.png ({size}x{size}, ss={ss})")
    print("STATUS=ok")


if __name__ == "__main__":
    main()
