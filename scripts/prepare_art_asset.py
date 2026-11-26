#!/usr/bin/env python3
"""Prepare and validate transparent RGBA PNG art assets for calimara.ro.

Follows design/art-style.md ("Tuș și laviu sepia"):
- Removes pure-white (#FFFFFF) generation backgrounds via border-seeded flood-fill
- Applies 4-ring smoothstep anti-aliased edge feathering + white-matte decontamination
- Optionally clears enclosed pure-white holes (--clear-holes, useful for frames/handles)
- Crops to optical bounding box and centers on a uniform square transparent canvas
- Optionally generates a 4-backdrop visual QA sheet (--verify)
- Validates existing PNG assets against the art-style technical spec (--check)
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from collections import deque
from pathlib import Path
from PIL import Image


BG_HARD_THRESH = 20.0  # Euclidean RGB distance from pure white (255, 255, 255)
EDGE_SOFT_MAX = 82.0   # Boundary band threshold for smooth anti-aliased feathering


def _white_dist(r: int, g: int, b: int) -> float:
    dr, dg, db = 255 - r, 255 - g, 255 - b
    return math.sqrt(dr * dr + dg * dg + db * db)


def prepare_transparent_png(
    src_path: str,
    dst_path: str,
    *,
    out_size: int = 768,
    pad_ratio: float = 0.08,
    clear_holes: bool = False,
) -> Path:
    img = Image.open(src_path).convert("RGBA")
    w, h = img.size
    px = img.load()

    # Step 1: Flood-fill connected pure-white background starting from all 4 image edges
    bg = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque()

    def try_seed(x: int, y: int) -> None:
        if not bg[y][x]:
            r, g, b, _ = px[x, y]
            if _white_dist(r, g, b) <= BG_HARD_THRESH:
                bg[y][x] = True
                q.append((x, y))

    for x in range(w):
        try_seed(x, 0)
        try_seed(x, h - 1)
    for y in range(h):
        try_seed(0, y)
        try_seed(w - 1, y)

    while q:
        cx, cy = q.popleft()
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < w and 0 <= ny < h and not bg[ny][nx]:
                r, g, b, _ = px[nx, ny]
                if _white_dist(r, g, b) <= BG_HARD_THRESH:
                    bg[ny][nx] = True
                    q.append((nx, ny))

    # Optional: clear large enclosed pure-white regions (e.g. frames, teacup handles)
    if clear_holes:
        visited = [[bg[y][x] for x in range(w)] for y in range(h)]
        min_hole_pixels = max(64, int(w * h * 0.0015))
        for sy in range(h):
            for sx in range(w):
                if visited[sy][sx]:
                    continue
                r, g, b, _ = px[sx, sy]
                if _white_dist(r, g, b) > BG_HARD_THRESH * 0.75:
                    continue
                comp: list[tuple[int, int]] = []
                hq: deque[tuple[int, int]] = deque([(sx, sy)])
                visited[sy][sx] = True
                while hq:
                    cx, cy = hq.popleft()
                    comp.append((cx, cy))
                    for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                        if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                            nr, ng, nb, _ = px[nx, ny]
                            if _white_dist(nr, ng, nb) <= BG_HARD_THRESH * 0.75:
                                visited[ny][nx] = True
                                hq.append((nx, ny))
                if len(comp) >= min_hole_pixels:
                    for cx, cy in comp:
                        bg[cy][cx] = True

    # Step 2: 4-ring smoothstep anti-aliased edge feathering along the bg boundary
    alpha = [[0 if bg[y][x] else 255 for x in range(w)] for y in range(h)]
    fringe_prev: set[tuple[int, int]] = set()
    for y in range(h):
        for x in range(w):
            if not bg[y][x]:
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < w and 0 <= ny < h and bg[ny][nx]:
                        fringe_prev.add((x, y))
                        break

    visited_fringe = set(fringe_prev)
    for ring in range(4):
        next_fringe: set[tuple[int, int]] = set()
        ring_max = EDGE_SOFT_MAX if ring == 0 else (EDGE_SOFT_MAX * 0.72 if ring == 1 else EDGE_SOFT_MAX * 0.50)
        for x, y in fringe_prev:
            r, g, b, _ = px[x, y]
            d = _white_dist(r, g, b)
            if d < ring_max:
                t = max(0.0, min(1.0, (d - BG_HARD_THRESH * 0.85) / (ring_max - BG_HARD_THRESH * 0.85)))
                t = t * t * (3.0 - 2.0 * t)
                a = int(round(t * 255))
                if a < alpha[y][x]:
                    alpha[y][x] = a
                if a < 180:
                    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        if 0 <= nx < w and 0 <= ny < h and not bg[ny][nx] and (nx, ny) not in visited_fringe:
                            visited_fringe.add((nx, ny))
                            next_fringe.add((nx, ny))
        fringe_prev = next_fringe
        if not fringe_prev:
            break

    # Step 3: White-matte decontamination (un-premultiply semi-transparent edge pixels)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out_px = out.load()

    for y in range(h):
        for x in range(w):
            a = alpha[y][x]
            if a == 0:
                out_px[x, y] = (0, 0, 0, 0)
            elif a == 255:
                r, g, b, _ = px[x, y]
                out_px[x, y] = (r, g, b, 255)
            else:
                r, g, b, _ = px[x, y]
                af = a / 255.0
                denom = max(af, 0.35)
                ur = int(max(0, min(255, round((r - (1.0 - af) * 255.0) / denom))))
                ug = int(max(0, min(255, round((g - (1.0 - af) * 255.0) / denom))))
                ub = int(max(0, min(255, round((b - (1.0 - af) * 255.0) / denom))))
                if af < 0.45:
                    sr = sg = sb = cnt = 0
                    for dy in (-2, -1, 0, 1, 2):
                        for dx in (-2, -1, 0, 1, 2):
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < w and 0 <= ny < h and alpha[ny][nx] >= 220:
                                nr, ng, nb, _ = px[nx, ny]
                                sr += nr
                                sg += ng
                                sb += nb
                                cnt += 1
                    if cnt > 0:
                        ur, ug, ub = sr // cnt, sg // cnt, sb // cnt
                out_px[x, y] = (ur, ug, ub, a)

    # Step 4: Crop to non-transparent bounding box & center with consistent safe padding
    bbox = out.getbbox()
    if not bbox:
        raise RuntimeError(f"Empty image after background removal: {src_path}")
    cropped = out.crop(bbox)
    cw, ch = cropped.size
    inner_max = int(round(out_size * (1.0 - 2.0 * pad_ratio)))
    scale = min(inner_max / cw, inner_max / ch)
    nw = max(1, int(round(cw * scale)))
    nh = max(1, int(round(ch * scale)))
    resized = cropped.resize((nw, nh), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (out_size, out_size), (0, 0, 0, 0))
    canvas.paste(resized, ((out_size - nw) // 2, (out_size - nh) // 2), resized)

    dst = Path(dst_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst, "PNG", optimize=True)
    return dst


def make_verification_sheet(png_paths: list[str | Path], out_path: str | Path, cell: int = 280) -> Path:
    """Render PNGs across 4 backdrops (checkerboard, #ffffff, #f3f2ee, #1a1a1d) for visual QA."""
    cols = len(png_paths)
    sheet = Image.new("RGB", (cols * cell, 4 * cell), (255, 255, 255))

    checker = Image.new("RGB", (cell, cell), (235, 235, 235))
    cp = checker.load()
    for y in range(cell):
        for x in range(cell):
            if ((x // 14) + (y // 14)) % 2 == 0:
                cp[x, y] = (205, 205, 205)

    backdrops = [
        checker,
        Image.new("RGB", (cell, cell), (255, 255, 255)),
        Image.new("RGB", (cell, cell), (243, 242, 238)),
        Image.new("RGB", (cell, cell), (26, 26, 29)),
    ]

    for col, path in enumerate(png_paths):
        item = Image.open(path).convert("RGBA").resize((cell, cell), Image.Resampling.LANCZOS)
        for row, bg_tile in enumerate(backdrops):
            tile = bg_tile.copy()
            tile.paste(item, (0, 0), item)
            sheet.paste(tile, (col * cell, row * cell))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, "PNG")
    return out


def check_art_asset(path: str | Path, *, min_size: int = 512, max_bytes: int = 750_000) -> list[str]:
    """Return a list of style/technical violations for a prepared PNG asset."""
    errors: list[str] = []
    asset = Path(path)
    if not asset.is_file():
        return [f"{asset}: file not found"]

    size_bytes = asset.stat().st_size
    if size_bytes > max_bytes:
        errors.append(f"{asset}: file size {size_bytes} bytes exceeds {max_bytes} bytes")

    with Image.open(asset) as img:
        if img.format != "PNG":
            errors.append(f"{asset}: format is {img.format}, expected PNG")
        if img.mode != "RGBA":
            errors.append(f"{asset}: mode is {img.mode}, expected RGBA")
            return errors
        w, h = img.size
        if w < min_size or h < min_size:
            errors.append(f"{asset}: dimensions {w}x{h} smaller than {min_size}x{min_size}")
        for cx, cy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            if img.getpixel((cx, cy))[3] != 0:
                errors.append(f"{asset}: corner ({cx},{cy}) is not transparent")
        alpha_vals = list(img.getchannel("A").get_flattened_data())
        total = w * h
        transparent_ratio = sum(1 for a in alpha_vals if a == 0) / total
        opaque_ratio = sum(1 for a in alpha_vals if a > 200) / total
        if transparent_ratio < 0.20:
            errors.append(f"{asset}: only {transparent_ratio*100:.1f}% transparent pixels (expected >= 20%)")
        if opaque_ratio < 0.12:
            errors.append(f"{asset}: only {opaque_ratio*100:.1f}% opaque pixels (expected >= 12%)")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or validate calimara.ro transparent PNG art assets.")
    parser.add_argument("--check", nargs="+", metavar="PNG", help="Validate existing transparent PNG assets.")
    parser.add_argument("--size", type=int, default=768, help="Square output dimension in pixels (default: 768).")
    parser.add_argument("--pad", type=float, default=0.08, help="Transparent safe padding ratio (default: 0.08).")
    parser.add_argument("--clear-holes", action="store_true", help="Also clear enclosed pure-white holes (frames/handles).")
    parser.add_argument("--verify", metavar="SHEET_PNG", help="Optional path to save a 4-backdrop visual QA sheet.")
    parser.add_argument("src", nargs="?", help="Source white-background image path.")
    parser.add_argument("dst", nargs="?", help="Destination transparent RGBA PNG path.")
    args = parser.parse_args(argv)

    if args.check:
        failed = False
        for item in args.check:
            errs = check_art_asset(item)
            if errs:
                failed = True
                for err in errs:
                    print(f"FAIL: {err}", file=sys.stderr)
            else:
                print(f"OK: {item}")
        return 1 if failed else 0

    if not args.src or not args.dst:
        parser.error("Provide <src> <dst> to process an image, or --check <png...> to validate.")

    out = prepare_transparent_png(
        args.src,
        args.dst,
        out_size=args.size,
        pad_ratio=args.pad,
        clear_holes=args.clear_holes,
    )
    errs = check_art_asset(out)
    if errs:
        for err in errs:
            print(f"WARN: {err}", file=sys.stderr)
    print(f"Prepared: {out} ({os.path.getsize(out) // 1024} KB)")
    if args.verify:
        sheet = make_verification_sheet([out], args.verify)
        print(f"Verification sheet: {sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
