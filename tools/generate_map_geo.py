#!/usr/bin/env python3
"""Build the game's lightweight East Asia vector map from Natural Earth.

Natural Earth is public domain. The input is intentionally not checked in;
download the 10m admin-1 GeoJSON and pass it with --admin1.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Point, Polygon, box, shape
from shapely.ops import transform, unary_union


MAP_W, MAP_H, PAD = 888, 480, 12
SOURCE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "v5.1.2/geojson/ne_10m_admin_1_states_provinces.geojson"
)


GROUPS = {
    # v0.2 조선 16권역. 개성·안동은 아래에서 실제 도형을 작게 분할한다.
    "hamb": {"KP-09", "KP-10", "KP-13"},
    "hamn": {"KP-08"},
    "pyab": {"KP-03", "KP-04"},
    "pyan": {"KP-01", "KP-02"},
    "hwan": {"KP-05", "KP-06"},
    "gaes": set(),
    "hans": {"KR-11"},
    "gyeo": {"KR-28", "KR-41"},
    "gang": {"KP-07", "KR-42"},
    "chub": {"KR-43"},
    "chun": {"KR-30", "KR-44", "KR-50"},
    "gyeb": {"KR-27", "KR-47"},
    "ando": set(),
    "gyen": {"KR-26", "KR-31", "KR-48"},
    "jeon": {"KR-29", "KR-45", "KR-46"},
    "jeju": {"KR-49"},
    # v0.2 중국 14권역. 누락 없이 중국 본토와 게임의 몽골 권역을 덮는다.
    "mong": {
        "CN-NM", "MN-1", "MN-035", "MN-037", "MN-039", "MN-041", "MN-043",
        "MN-046", "MN-047", "MN-049", "MN-051", "MN-053", "MN-055", "MN-057",
        "MN-059", "MN-061", "MN-063", "MN-064", "MN-065", "MN-067", "MN-069",
        "MN-071", "MN-073",
    },
    "manj": {"CN-HL", "CN-JL"},
    "liao": {"CN-LN"},
    "hebe": {"CN-BJ", "CN-TJ", "CN-HE"},
    "shan": {"CN-SD"},
    "shax": {"CN-SX"},
    "shaa": {"CN-SN", "CN-NX", "CN-GS", "CN-QH", "CN-XJ"},
    "hena": {"CN-HA"},
    "sich": {"CN-SC", "CN-CQ", "CN-GZ", "CN-YN", "CN-XZ"},
    "hube": {"CN-AH", "CN-HB", "CN-HN", "CN-JX"},
    "jian": {"CN-JS", "CN-SH"},
    "zhej": {"CN-ZJ"},
    "fuji": {"CN-FJ"},
    "guan": {"CN-GD", "CN-GX", "CN-HI"},
    # 일본 9권역 + 대마도, 유구, 타이완.
    "hokk": {"JP-01"},
    "toho": {"JP-02", "JP-03", "JP-04", "JP-05", "JP-06", "JP-07"},
    "kant": {"JP-08", "JP-09", "JP-10", "JP-11", "JP-12", "JP-13", "JP-14", "JP-19", "JP-20"},
    "chubu": {"JP-15", "JP-16", "JP-17", "JP-18", "JP-21", "JP-22", "JP-23"},
    "kans": {"JP-24", "JP-25", "JP-26", "JP-27", "JP-28", "JP-29", "JP-30"},
    "chug": {"JP-31", "JP-32", "JP-33", "JP-34", "JP-35"},
    "shik": {"JP-36", "JP-37", "JP-38", "JP-39"},
    "kyus": {"JP-40", "JP-41", "JP-42", "JP-43", "JP-44", "JP-45"},
    "sats": {"JP-46"},
    "tsus": set(),
    "ryuk": {"JP-47"},
    "taiw": {
        "TW-CHA", "TW-CYI", "TW-CYQ", "TW-HSQ", "TW-HSZ", "TW-HUA", "TW-ILA",
        "TW-KEE", "TW-KHH", "TW-KIN", "TW-MIA", "TW-NAN", "TW-PEN", "TW-PIF",
        "TW-TAO", "TW-TNN", "TW-TPE", "TW-TPQ", "TW-TTT", "TW-TXG", "TW-YUN",
    },
}


LABEL_LONLAT = {
    "hamb": (129.2, 42.0), "hamn": (127.8, 40.4), "pyab": (125.7, 40.8),
    "pyan": (126.1, 39.4), "hwan": (126.2, 38.4), "gaes": (126.55, 37.97),
    "hans": (126.98, 37.57), "gyeo": (127.15, 37.15), "gang": (128.4, 38.0),
    "chub": (127.75, 36.8), "chun": (126.8, 36.45), "gyeb": (128.8, 36.3),
    "ando": (128.73, 36.57), "gyen": (128.2, 35.2), "jeon": (126.8, 35.0),
    "jeju": (126.55, 33.4),
    "mong": (103.5, 46.0), "manj": (127.0, 47.1), "liao": (122.7, 41.4),
    "hebe": (115.3, 39.0), "shan": (118.5, 36.4), "shax": (112.2, 37.5),
    "shaa": (93.5, 38.5), "hena": (113.5, 34.5), "sich": (91.5, 30.5),
    "hube": (113.0, 29.5), "jian": (119.0, 32.0), "zhej": (120.2, 29.1),
    "fuji": (118.7, 26.2), "guan": (111.4, 22.7),
    "hokk": (142.3, 43.2), "toho": (140.4, 39.0), "kant": (139.0, 36.1),
    "chubu": (137.0, 36.0), "kans": (135.5, 35.0), "chug": (133.0, 34.8),
    "shik": (133.7, 33.7), "kyus": (131.5, 32.8), "sats": (130.5, 31.5),
    "tsus": (129.3, 34.35), "ryuk": (127.7, 26.35), "taiw": (121.0, 23.7),
}

CAPITAL_LONLAT = {
    "hans": (126.9780, 37.5665),
    "hebe": (116.4074, 39.9042),
    "kans": (135.7681, 35.0116),
}

# 작은 지역은 도형을 보존하고 글자만 바깥으로 분산한다.
LABEL_OFFSET = {
    "hamb": (14, -5), "hamn": (17, 0), "pyab": (-18, -5), "pyan": (-19, 1),
    "hwan": (-20, 5), "gaes": (-20, -7), "hans": (-18, 8), "gyeo": (-19, 16),
    "gang": (22, -2), "chub": (22, 5), "chun": (-20, 19), "gyeb": (23, 10),
    "ando": (24, 19), "gyen": (21, 26), "jeon": (-15, 28), "jeju": (-2, 13),
    "hokk": (3, -8), "toho": (18, 0), "kant": (22, 4), "chubu": (16, -7),
    "kans": (20, 3), "chug": (12, -7), "shik": (18, 14), "kyus": (12, 14),
    "sats": (11, 19), "tsus": (-12, 0), "ryuk": (-6, 12), "taiw": (-8, 4),
}


def lcc_xy(lon: float, lat: float) -> tuple[float, float]:
    """Spherical Lambert conformal conic centered on East Asia."""
    phi1, phi2, phi0 = map(math.radians, (25.0, 47.0, 35.0))
    lam0 = math.radians(123.0)
    phi, lam = math.radians(lat), math.radians(lon)
    n = math.log(math.cos(phi1) / math.cos(phi2)) / math.log(
        math.tan(math.pi / 4 + phi2 / 2) / math.tan(math.pi / 4 + phi1 / 2)
    )
    f = math.cos(phi1) * math.tan(math.pi / 4 + phi1 / 2) ** n / n
    rho = f / math.tan(math.pi / 4 + phi / 2) ** n
    rho0 = f / math.tan(math.pi / 4 + phi0 / 2) ** n
    theta = n * (lam - lam0)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


def map_coords(func, geom):
    def adapter(x, y, z=None):
        if hasattr(x, "__iter__"):
            pairs = [func(float(a), float(b)) for a, b in zip(x, y)]
            return tuple(p[0] for p in pairs), tuple(p[1] for p in pairs)
        return func(float(x), float(y))

    return transform(adapter, geom)


def valid(geom):
    if geom.is_empty:
        return geom
    return geom if geom.is_valid else geom.buffer(0)


def iter_polygons(geom):
    if isinstance(geom, Polygon):
        yield geom
    elif isinstance(geom, MultiPolygon):
        yield from geom.geoms
    elif isinstance(geom, GeometryCollection):
        for part in geom.geoms:
            yield from iter_polygons(part)


def prune(geom, min_area=0.32):
    polys = [p for p in iter_polygons(geom) if p.area >= min_area]
    return unary_union(polys) if polys else GeometryCollection()


def fmt(value: float) -> str:
    value = round(value * 4) / 4
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def ring_path(coords) -> str:
    pts = list(coords)
    if len(pts) < 3:
        return ""
    return "M" + "L".join(f"{fmt(x)},{fmt(y)}" for x, y in pts[:-1]) + "Z"


def polygon_path(geom) -> str:
    chunks = []
    for poly in iter_polygons(geom):
        chunks.append(ring_path(poly.exterior.coords))
        chunks.extend(ring_path(r.coords) for r in poly.interiors if Polygon(r).area >= 0.3)
    return "".join(c for c in chunks if c)


def line_path(geom) -> str:
    chunks = []

    def add(line):
        pts = list(line.coords)
        if len(pts) > 1:
            chunks.append("M" + "L".join(f"{fmt(x)},{fmt(y)}" for x, y in pts))

    if isinstance(geom, LineString):
        add(geom)
    elif isinstance(geom, MultiLineString):
        for line in geom.geoms:
            add(line)
    elif isinstance(geom, GeometryCollection):
        for part in geom.geoms:
            if isinstance(part, (LineString, MultiLineString, GeometryCollection)):
                nested = line_path(part)
                if nested:
                    chunks.append(nested)
    return "".join(chunks)


def load_regions(admin1_path: Path):
    data = json.loads(admin1_path.read_text(encoding="utf-8"))
    by_code = {}
    for feature in data["features"]:
        props = feature.get("properties", {})
        code = props.get("iso_3166_2")
        if code and code.startswith(("CN-", "KR-", "KP-", "JP-", "MN-", "TW-")):
            by_code[code] = valid(shape(feature["geometry"]))

    missing = sorted(code for codes in GROUPS.values() for code in codes if code not in by_code)
    if missing:
        raise SystemExit("Missing Natural Earth codes: " + ", ".join(missing))

    assigned = set().union(*GROUPS.values())
    unassigned_china = sorted(
        code for code in by_code
        if code.startswith("CN-") and code not in assigned and code != "CN-X01~"
    )
    if unassigned_china:
        raise SystemExit("Unassigned Chinese provinces: " + ", ".join(unassigned_china))

    # Keep the complete mainland outline: western China starts near 73E.
    crop = box(70.0, 15.0, 148.0, 56.0)
    regions = {}
    for region_id, codes in GROUPS.items():
        if not codes:
            continue
        pieces = [by_code[c] for c in codes]
        regions[region_id] = valid(unary_union(pieces).intersection(crop))

    # 현대 행정구역에 없는 게임용 도시 권역 두 곳을 실제 도형 안에서 작게 분할한다.
    gaeseong_mask = Point(126.55, 37.97).buffer(0.27)
    regions["gaes"] = valid(regions["hwan"].intersection(gaeseong_mask))
    regions["hwan"] = valid(regions["hwan"].difference(gaeseong_mask))

    andong_mask = Point(128.73, 36.57).buffer(0.34)
    regions["ando"] = valid(regions["gyeb"].intersection(andong_mask))
    regions["gyeb"] = valid(regions["gyeb"].difference(andong_mask))

    # 나가사키현에서 대마도 두 섬만 떼어 별도 게임 지역으로 만든다.
    tsushima_box = box(128.95, 33.95, 129.60, 34.82)
    nagasaki = by_code["JP-42"]
    regions["tsus"] = valid(nagasaki.intersection(tsushima_box))
    regions["kyus"] = valid(regions["kyus"].difference(tsushima_box))
    return regions


def build(admin1_path: Path):
    geo = load_regions(admin1_path)
    projected = {key: map_coords(lcc_xy, geom) for key, geom in geo.items()}
    all_projected = unary_union(list(projected.values()))
    minx, miny, maxx, maxy = all_projected.bounds
    scale = min((MAP_W - PAD * 2) / (maxx - minx), (MAP_H - PAD * 2) / (maxy - miny))
    draw_w, draw_h = (maxx - minx) * scale, (maxy - miny) * scale
    ox, oy = (MAP_W - draw_w) / 2, (MAP_H - draw_h) / 2

    def to_local(x, y):
        # One projection and one uniform scale preserve shapes, borders and
        # the countries' true relative positions.
        return ox + (x - minx) * scale, oy + (maxy - y) * scale

    local = {}
    small_regions = {"gaes", "hans", "ando", "tsus", "ryuk"}
    for key, geom in projected.items():
        g = map_coords(to_local, geom).simplify(0.32, preserve_topology=True)
        local[key] = prune(valid(g), 0.045 if key in small_regions else 0.20)

    coast = prune(valid(unary_union(list(local.values()))), 0.18).simplify(0.35, preserve_topology=True)
    borders = []
    ids = list(GROUPS)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            shared = local[a].boundary.intersection(local[b].boundary)
            if not shared.is_empty and shared.length > 0.7:
                shared = shared.simplify(0.35, preserve_topology=True)
                d = line_path(shared)
                if d:
                    borders.append({"a": a, "b": b, "d": d})

    def project_point(lonlat):
        x, y = lcc_xy(*lonlat)
        return [round(v, 2) for v in to_local(x, y)]

    out_regions = {}
    for key in ids:
        geom = local[key]
        preferred = Point(project_point(LABEL_LONLAT[key]))
        anchor = preferred if geom.buffer(0.25).contains(preferred) else geom.representative_point()
        dx, dy = LABEL_OFFSET.get(key, (0, 0))
        label = [round(anchor.x + dx, 2), round(anchor.y + dy, 2)]
        bounds = [round(v, 2) for v in geom.bounds]
        entry = {
            "d": polygon_path(geom),
            "anchor": [round(anchor.x, 2), round(anchor.y, 2)],
            "label": label,
            "bbox": bounds,
            "small": geom.area < 120,
        }
        if key in CAPITAL_LONLAT:
            entry["capital"] = project_point(CAPITAL_LONLAT[key])
        out_regions[key] = entry

    return {
        "width": MAP_W,
        "height": MAP_H,
        "projection": "Lambert conformal conic (25°, 47° / 123°E)",
        "source": SOURCE_URL,
        "license": "Natural Earth public domain",
        "coast": polygon_path(coast),
        "regions": out_regions,
        "borders": borders,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin1", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    payload = json.dumps(build(args.admin1), ensure_ascii=False, separators=(",", ":"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "/* Generated by tools/generate_map_geo.py from Natural Earth 5.1.2 (public domain). */\n"
        "window.MAP_GEO=" + payload + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {args.out} ({len(payload):,} bytes)")


if __name__ == "__main__":
    main()
