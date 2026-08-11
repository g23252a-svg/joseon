#!/usr/bin/env python3
"""Build the in-game shaded-relief texture from Natural Earth II.

The source raster is equirectangular.  This script resamples it through the
same Lambert conformal conic projection and uniform fit used by map_geo.js, so
the photographed terrain and the interactive province paths share a coastline.
Natural Earth raster data is public domain.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from shapely.ops import unary_union

from generate_map_geo import MAP_H, MAP_W, PAD, lcc_xy, load_regions, map_coords


def projection_frame(admin1_path: Path):
    regions = load_regions(admin1_path)
    projected = [map_coords(lcc_xy, geom) for geom in regions.values()]
    minx, miny, maxx, maxy = unary_union(projected).bounds
    scale = min((MAP_W - PAD * 2) / (maxx - minx), (MAP_H - PAD * 2) / (maxy - miny))
    draw_w, draw_h = (maxx - minx) * scale, (maxy - miny) * scale
    return minx, miny, maxx, maxy, scale, (MAP_W - draw_w) / 2, (MAP_H - draw_h) / 2


def inverse_lcc(x, y):
    """Vectorized inverse of generate_map_geo.lcc_xy()."""
    phi1, phi2, phi0 = np.radians((25.0, 47.0, 35.0))
    lam0 = math.radians(123.0)
    n = math.log(math.cos(phi1) / math.cos(phi2)) / math.log(
        math.tan(math.pi / 4 + phi2 / 2) / math.tan(math.pi / 4 + phi1 / 2)
    )
    f = math.cos(phi1) * math.tan(math.pi / 4 + phi1 / 2) ** n / n
    rho0 = f / math.tan(math.pi / 4 + phi0 / 2) ** n
    rho = np.hypot(x, rho0 - y)
    theta = np.arctan2(x, rho0 - y)
    lat = 2 * np.arctan(np.power(f / np.maximum(rho, 1e-12), 1 / n)) - math.pi / 2
    lon = lam0 + theta / n
    return np.degrees(lon), np.degrees(lat)


def bilinear_sample(source: np.ndarray, sx, sy):
    h, w = source.shape[:2]
    sx = np.clip(sx, 0, w - 1.001)
    sy = np.clip(sy, 0, h - 1.001)
    x0, y0 = np.floor(sx).astype(np.int32), np.floor(sy).astype(np.int32)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    wx, wy = (sx - x0)[..., None], (sy - y0)[..., None]
    top = source[y0, x0] * (1 - wx) + source[y0, x1] * wx
    bottom = source[y1, x0] * (1 - wx) + source[y1, x1] * wx
    return top * (1 - wy) + bottom * wy


def build(admin1_path: Path, raster_path: Path) -> Image.Image:
    minx, _miny, _maxx, maxy, scale, ox, oy = projection_frame(admin1_path)
    yy, xx = np.mgrid[0:MAP_H, 0:MAP_W]
    projected_x = minx + (xx - ox) / scale
    projected_y = maxy - (yy - oy) / scale
    lon, lat = inverse_lcc(projected_x, projected_y)

    with Image.open(raster_path) as source_image:
        src_w, src_h = source_image.size
        source_x = (lon + 180.0) / 360.0 * src_w - 0.5
        source_y = (90.0 - lat) / 180.0 * src_h - 0.5
        left = max(0, int(np.floor(source_x.min())) - 2)
        top = max(0, int(np.floor(source_y.min())) - 2)
        right = min(src_w, int(np.ceil(source_x.max())) + 3)
        bottom = min(src_h, int(np.ceil(source_y.max())) + 3)
        source = np.asarray(source_image.crop((left, top, right, bottom)).convert("RGB"), dtype=np.float32)
    sampled = np.clip(bilinear_sample(source, source_x - left, source_y - top), 0, 255).astype(np.uint8)

    image = Image.fromarray(sampled, "RGB")
    # Victoria-like readable terrain: warm land color, firmer relief, no neon.
    image = ImageEnhance.Color(image).enhance(1.08)
    image = ImageEnhance.Contrast(image).enhance(1.18)
    image = ImageEnhance.Brightness(image).enhance(0.78)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.1, percent=105, threshold=3))
    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin1", required=True, type=Path)
    parser.add_argument("--raster", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    image = build(args.admin1, args.raster)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.out, "WEBP", quality=91, method=6)
    print(f"wrote {args.out} ({image.width}x{image.height}, {args.out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
