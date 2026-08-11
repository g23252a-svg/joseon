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


MAP_W, MAP_H, PAD = 968, 572, 14
SOURCE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "v5.1.2/geojson/ne_10m_admin_1_states_provinces.geojson"
)


GROUPS = {
    # 조선 팔도 (현대 행정구역을 역사 권역으로 병합)
    "ham": {"KP-08", "KP-09", "KP-10", "KP-13"},
    "pya": {"KP-01", "KP-02", "KP-03", "KP-04"},
    "hwa": {"KP-05", "KP-06"},
    "gan": {"KP-07", "KR-42"},
    "gyu": {"KR-11", "KR-28", "KR-41"},
    "chu": {"KR-30", "KR-43", "KR-44", "KR-50"},
    "gyb": {"KR-26", "KR-27", "KR-31", "KR-47", "KR-48"},
    "jeo": {"KR-29", "KR-45", "KR-46", "KR-49"},
    # 중국의 게임용 대권역
    "man": {"CN-HL", "CN-JL"},
    "lia": {"CN-LN"},
    "heb": {"CN-BJ", "CN-TJ", "CN-HE", "CN-SX", "CN-HA"},
    "sha": {"CN-SD"},
    # The western provinces must remain in the silhouette.  The game has only
    # nine Chinese macro-regions, so Xinjiang/Qinghai join the northwest and
    # Tibet joins the southwest rather than being cut off the map.
    "sxi": {"CN-SN", "CN-NX", "CN-GS", "CN-XJ", "CN-QH"},
    "sch": {"CN-SC", "CN-CQ", "CN-GZ", "CN-YN", "CN-XZ"},
    "jia": {"CN-AH", "CN-HB", "CN-HN", "CN-JS", "CN-JX", "CN-SH", "CN-ZJ"},
    "fuj": {"CN-FJ"},
    "gua": {"CN-GD", "CN-GX", "CN-HI"},
    # 일본의 전통 지방. 주부는 관동/간사이에 나누어 혼슈가 끊기지 않게 한다.
    "hok": {"JP-01"},
    "toh": {"JP-02", "JP-03", "JP-04", "JP-05", "JP-06", "JP-07"},
    "kto": {"JP-08", "JP-09", "JP-10", "JP-11", "JP-12", "JP-13", "JP-14", "JP-15", "JP-19", "JP-20", "JP-22"},
    "kan": {"JP-16", "JP-17", "JP-18", "JP-21", "JP-23", "JP-24", "JP-25", "JP-26", "JP-27", "JP-28", "JP-29", "JP-30"},
    "chg": {"JP-31", "JP-32", "JP-33", "JP-34", "JP-35"},
    "shi": {"JP-36", "JP-37", "JP-38", "JP-39"},
    "kyu": {"JP-40", "JP-41", "JP-42", "JP-43", "JP-44", "JP-45", "JP-46"},
    "ryu": {"JP-47"},
    "tsu": set(),
}


LABEL_LONLAT = {
    "ham": (128.7, 41.6), "pya": (126.0, 40.0), "hwa": (126.1, 38.5),
    "gyu": (127.0, 37.5), "gan": (128.5, 38.0), "chu": (127.1, 36.4),
    "gyb": (128.6, 35.6), "jeo": (126.7, 34.8),
    "man": (127.0, 47.1), "lia": (122.7, 41.4), "heb": (115.3, 38.3),
    "sha": (118.5, 36.4), "sxi": (93.5, 38.5), "sch": (91.5, 30.5),
    "jia": (116.4, 29.4), "fuj": (118.7, 26.2), "gua": (111.4, 22.7),
    "hok": (142.3, 43.2), "toh": (140.4, 39.0), "kto": (138.8, 36.2),
    "kan": (136.0, 35.0), "chg": (133.0, 34.8), "shi": (133.7, 33.7),
    "kyu": (131.0, 32.6), "tsu": (129.3, 34.35), "ryu": (127.7, 26.35),
}

CAPITAL_LONLAT = {
    "gyu": (126.9780, 37.5665),
    "heb": (116.4074, 39.9042),
    "kan": (135.7681, 35.0116),
}

# 작은 나라를 실제 축척 그대로 놓으면 지명이 한 점에 겹친다. 해안선은 실제
# 벡터를 유지하고 라벨만 바깥으로 빼며, 필요할 때 리더선을 그린다.
LABEL_OFFSET = {
    "ham": (12, -3), "pya": (-20, -5), "hwa": (-23, 0), "gyu": (-24, 4),
    "gan": (25, -2), "chu": (-21, 7), "gyb": (24, 5), "jeo": (-6, 15),
    "hok": (3, -8), "toh": (19, 0), "kto": (23, 5), "kan": (20, 1),
    "chg": (14, -6), "shi": (20, 15), "kyu": (12, 14), "tsu": (-12, 0),
    "ryu": (-6, 12),
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
        if code and (code.startswith("CN-") or code.startswith("KR-") or code.startswith("KP-") or code.startswith("JP-")):
            by_code[code] = valid(shape(feature["geometry"]))

    missing = sorted(code for codes in GROUPS.values() for code in codes if code not in by_code)
    if missing:
        raise SystemExit("Missing Natural Earth codes: " + ", ".join(missing))

    assigned = set().union(*GROUPS.values()) | {"CN-NM"}
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
        if region_id == "tsu":
            continue
        pieces = [by_code[c] for c in codes]
        regions[region_id] = valid(unary_union(pieces).intersection(crop))

    # 내몽골은 116E를 기준으로 동부는 만주, 서부는 하북 권역에 붙인다.
    inner = by_code.get("CN-NM", GeometryCollection()).intersection(crop)
    regions["man"] = valid(unary_union([regions["man"], inner.intersection(box(116, -90, 180, 90))]))
    regions["heb"] = valid(unary_union([regions["heb"], inner.intersection(box(-180, -90, 116, 90))]))

    # 나가사키현에서 대마도 두 섬만 떼어 별도 게임 지역으로 만든다.
    tsushima_box = box(128.95, 33.95, 129.60, 34.82)
    nagasaki = by_code["JP-42"]
    regions["tsu"] = valid(nagasaki.intersection(tsushima_box))
    regions["kyu"] = valid(regions["kyu"].difference(tsushima_box))
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
    for key, geom in projected.items():
        g = map_coords(to_local, geom).simplify(0.38, preserve_topology=True)
        local[key] = prune(valid(g), 0.10 if key in {"tsu", "ryu"} else 0.26)

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
