#!/usr/bin/env python3
"""Generate the exact PNG sprite sheets described in ASSETS.md.

The artwork is intentionally deterministic and drawn at 4x resolution before
being downsampled. This keeps the tiny in-game sprites crisp while retaining a
soft, painted-map edge.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SCALE = 4

INK = "#171a1d"
INK_SOFT = "#353738"
PAPER = "#e8e1d1"
PAPER_DARK = "#c9bfa8"
BRASS = "#e0bd76"
GOOD = "#8fa86a"
BAD = "#c4534a"
BLUE = "#9fd0e8"
SEA = "#101820"

TERRAIN = ["#5d6b45", "#6a6247", "#585349", "#4f6459"]
NATIONS = ["#4f7fb5", "#b5654f", "#8a6fae"]


def rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def blend(a, b, amount: float) -> tuple[int, int, int, int]:
    ca = rgba(a) if isinstance(a, str) else a
    cb = rgba(b) if isinstance(b, str) else b
    return tuple(round(ca[i] * (1 - amount) + cb[i] * amount) for i in range(3)) + (255,)


def q(value: float) -> int:
    return round(value * SCALE)


def box(x0: float, y0: float, x1: float, y1: float) -> tuple[int, int, int, int]:
    return q(x0), q(y0), q(x1), q(y1)


def points(values: list[tuple[float, float]]) -> list[tuple[int, int]]:
    return [(q(x), q(y)) for x, y in values]


def canvas(width: int, height: int, color=(0, 0, 0, 0)) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (width * SCALE, height * SCALE), color)
    return image, ImageDraw.Draw(image, "RGBA")


def finish(image: Image.Image, width: int, height: int) -> Image.Image:
    return image.resize((width, height), Image.Resampling.LANCZOS)


def line(draw: ImageDraw.ImageDraw, xy, fill, width=1, joint="curve"):
    draw.line(points(xy), fill=fill, width=max(1, q(width)), joint=joint)


def polygon(draw: ImageDraw.ImageDraw, xy, fill, outline=None, width=1):
    pts = points(xy)
    draw.polygon(pts, fill=fill)
    if outline:
        draw.line(pts + [pts[0]], fill=outline, width=max(1, q(width)), joint="curve")


def ellipse(draw: ImageDraw.ImageDraw, xy, fill, outline=None, width=1):
    draw.ellipse(box(*xy), fill=fill, outline=outline, width=max(1, q(width)))


def rectangle(draw: ImageDraw.ImageDraw, xy, fill, outline=None, width=1):
    draw.rectangle(box(*xy), fill=fill, outline=outline, width=max(1, q(width)))


def rounded(draw: ImageDraw.ImageDraw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box(*xy), radius=q(radius), fill=fill, outline=outline, width=max(1, q(width)))


def paper_fibres(draw: ImageDraw.ImageDraw, ox: int, oy: int, w: int, h: int, seed: int, base, count: int = 72):
    rng = random.Random(seed)
    for _ in range(count):
        x = ox + rng.uniform(1, w - 1)
        y = oy + rng.uniform(1, h - 1)
        length = rng.uniform(0.8, 4.2)
        color = blend(base, INK, rng.uniform(0.035, 0.085)) if rng.random() < 0.62 else blend(base, PAPER, rng.uniform(0.04, 0.10))
        line(draw, [(x, y), (x + length, y + rng.uniform(-0.35, 0.35))], color, rng.choice([0.35, 0.5, 0.7]))


def draw_plain(draw: ImageDraw.ImageDraw, ox: int):
    base = blend(TERRAIN[0], PAPER, 0.26)
    rectangle(draw, (ox, 0, ox + 44, 44), base)
    paper_fibres(draw, ox, 0, 44, 44, 101, base)
    # Irrigation paths, deliberately low contrast so nation tint still reads.
    line(draw, [(ox + 1, 14), (ox + 17, 13), (ox + 29, 15), (ox + 43, 13)], blend(base, INK, 0.18), 0.75)
    line(draw, [(ox + 1, 30), (ox + 12, 28), (ox + 27, 30), (ox + 43, 29)], blend(base, INK, 0.15), 0.7)
    line(draw, [(ox + 15, 1), (ox + 15, 14), (ox + 12, 28), (ox + 13, 43)], blend(base, INK, 0.14), 0.7)
    line(draw, [(ox + 31, 1), (ox + 29, 15), (ox + 28, 30), (ox + 31, 43)], blend(base, INK, 0.12), 0.7)
    for x, y in [(6, 7), (22, 8), (37, 7), (7, 22), (21, 23), (37, 22), (6, 37), (22, 37), (38, 37)]:
        sprout = blend(base, "#38452f", 0.46)
        line(draw, [(ox + x, y + 2), (ox + x, y - 1)], sprout, 0.65)
        line(draw, [(ox + x, y), (ox + x - 1.7, y - 2)], sprout, 0.5)
        line(draw, [(ox + x, y), (ox + x + 1.7, y - 2)], sprout, 0.5)


def draw_hills(draw: ImageDraw.ImageDraw, ox: int):
    base = blend(TERRAIN[1], PAPER, 0.24)
    rectangle(draw, (ox, 0, ox + 44, 44), base)
    paper_fibres(draw, ox, 0, 44, 44, 202, base)
    ellipse(draw, (ox - 9, 16, ox + 23, 49), blend(base, TERRAIN[1], 0.30))
    ellipse(draw, (ox + 9, 10, ox + 42, 45), blend(base, INK, 0.12))
    ellipse(draw, (ox + 27, 18, ox + 57, 49), blend(base, TERRAIN[1], 0.24))
    arc_color = blend(base, INK, 0.23)
    draw.arc(box(ox - 8, 16, ox + 24, 49), 190, 350, fill=arc_color, width=q(0.85))
    draw.arc(box(ox + 8, 10, ox + 43, 45), 190, 350, fill=blend(base, INK, 0.28), width=q(0.9))
    draw.arc(box(ox + 27, 18, ox + 58, 49), 190, 350, fill=arc_color, width=q(0.8))
    line(draw, [(ox + 7, 31), (ox + 13, 27), (ox + 18, 28)], blend(base, PAPER, 0.17), 0.7)
    line(draw, [(ox + 22, 27), (ox + 28, 22), (ox + 34, 24)], blend(base, PAPER, 0.14), 0.7)


def draw_mountains(draw: ImageDraw.ImageDraw, ox: int):
    base = blend(TERRAIN[2], PAPER, 0.2)
    rectangle(draw, (ox, 0, ox + 44, 44), base)
    paper_fibres(draw, ox, 0, 44, 44, 303, base)
    polygon(draw, [(ox - 8, 43), (ox + 7, 18), (ox + 20, 43)], blend(base, INK, 0.18))
    polygon(draw, [(ox + 5, 43), (ox + 22, 7), (ox + 39, 43)], blend(base, INK, 0.27))
    polygon(draw, [(ox + 25, 43), (ox + 38, 16), (ox + 53, 43)], blend(base, INK, 0.20))
    line(draw, [(ox + 22, 8), (ox + 18, 19), (ox + 22, 16), (ox + 15, 31)], blend(base, PAPER, 0.31), 1)
    line(draw, [(ox + 7, 19), (ox + 3, 31), (ox + 8, 27)], blend(base, PAPER, 0.22), 0.8)
    line(draw, [(ox + 38, 17), (ox + 34, 29), (ox + 39, 25)], blend(base, PAPER, 0.20), 0.8)
    for x0, y0, x1, y1 in [(11, 39, 19, 26), (27, 39, 34, 26), (30, 35, 37, 21)]:
        line(draw, [(ox + x0, y0), (ox + x1, y1)], blend(base, INK, 0.22), 0.65)


def draw_coast(draw: ImageDraw.ImageDraw, ox: int):
    base = blend(TERRAIN[3], PAPER, 0.16)
    rectangle(draw, (ox, 0, ox + 44, 44), base)
    paper_fibres(draw, ox, 0, 44, 44, 404, base)
    # A faint sand wash and ripples rather than a literal shoreline; this avoids
    # visible vertical seams when many coast cells repeat side by side.
    polygon(draw, [(ox, 0), (ox + 16, 0), (ox + 12, 12), (ox + 16, 24), (ox + 11, 34), (ox + 15, 44), (ox, 44)], blend(base, "#9a8967", 0.28))
    line(draw, [(ox + 15, 0), (ox + 12, 12), (ox + 16, 24), (ox + 11, 34), (ox + 15, 44)], blend(base, PAPER, 0.25), 0.8)
    for y, shift in [(7, 0), (15, 4), (24, 1), (33, 5), (40, 0)]:
        line(draw, [(ox + 21 + shift, y), (ox + 27 + shift, y - 1), (ox + 34 + shift, y)], blend(base, BLUE, 0.34), 0.75)
    for x, y in [(6, 8), (14, 20), (8, 34), (20, 39)]:
        ellipse(draw, (ox + x, y, ox + x + 1.1, y + 1.1), blend(base, INK, 0.12))


def terrain_sheet() -> Image.Image:
    image, draw = canvas(176, 44)
    draw_plain(draw, 0)
    draw_hills(draw, 44)
    draw_mountains(draw, 88)
    draw_coast(draw, 132)
    return finish(image, 176, 44)


def icon_coin(draw, ox):
    for x, y in [(11, 12), (20, 10), (17, 20), (24, 20)]:
        ellipse(draw, (ox + x - 6, y - 6, ox + x + 6, y + 6), rgba(BRASS), rgba(INK), 1.3)
        rectangle(draw, (ox + x - 1.7, y - 1.7, ox + x + 1.7, y + 1.7), rgba(INK))
    line(draw, [(ox + 6, 6), (ox + 26, 26)], rgba("#b5654f"), 1.5)


def icon_rice(draw, ox):
    for dx, tilt in [(10, -3), (16, 0), (22, 3)]:
        line(draw, [(ox + dx, 27), (ox + dx + tilt, 6)], rgba(PAPER), 1.3)
        for i in range(4):
            y = 10 + i * 4
            x = dx + tilt * (1 - y / 28)
            ellipse(draw, (ox + x - 3.5, y - 1.5, ox + x - 0.5, y + 1.5), rgba(BRASS), rgba(INK), 0.5)
            ellipse(draw, (ox + x + 0.5, y - 1.5, ox + x + 3.5, y + 1.5), rgba(BRASS), rgba(INK), 0.5)
    line(draw, [(ox + 7, 25), (ox + 25, 25)], rgba(INK), 1)


def icon_people(draw, ox):
    for x, y, r in [(16, 9, 4), (8, 13, 3.4), (24, 13, 3.4)]:
        ellipse(draw, (ox + x - r, y - r, ox + x + r, y + r), rgba(PAPER), rgba(INK), 1)
    ellipse(draw, (ox + 7, 15, ox + 25, 31), rgba(BLUE), rgba(INK), 1.2)
    ellipse(draw, (ox + 1, 18, ox + 14, 30), rgba(PAPER), rgba(INK), 1)
    ellipse(draw, (ox + 18, 18, ox + 31, 30), rgba(PAPER), rgba(INK), 1)


def icon_army(draw, ox):
    line(draw, [(ox + 5, 27), (ox + 27, 5)], rgba(PAPER), 2)
    polygon(draw, [(ox + 27, 4), (ox + 24, 11), (ox + 21, 8)], rgba(BRASS), rgba(INK), 1)
    line(draw, [(ox + 6, 6), (ox + 27, 27)], rgba("#a66b4f"), 2)
    polygon(draw, [(ox + 16, 10), (ox + 25, 13), (ox + 24, 23), (ox + 16, 28), (ox + 8, 23), (ox + 7, 13)], rgba("#596b70"), rgba(INK), 1.3)
    line(draw, [(ox + 16, 13), (ox + 16, 24)], rgba(BRASS), 1)


def icon_tech(draw, ox):
    rounded(draw, (ox + 4, 6, ox + 24, 27), 2, rgba(PAPER), rgba(INK), 1.2)
    line(draw, [(ox + 8, 11), (ox + 20, 11), (ox + 8, 16), (ox + 18, 16), (ox + 8, 21), (ox + 16, 21)], rgba("#7d7467"), 0.8)
    line(draw, [(ox + 26, 5), (ox + 19, 27)], rgba("#7a4f36"), 2.2)
    polygon(draw, [(ox + 25, 4), (ox + 29, 5), (ox + 27, 10), (ox + 23, 9)], rgba(BLUE), rgba(INK), 0.7)


def icon_province(draw, ox):
    polygon(draw, [(ox + 3, 14), (ox + 16, 5), (ox + 29, 14), (ox + 25, 17), (ox + 7, 17)], rgba("#485057"), rgba(INK), 1.2)
    rectangle(draw, (ox + 7, 16, ox + 25, 28), rgba(PAPER), rgba(INK), 1.2)
    rectangle(draw, (ox + 13, 19, ox + 19, 28), rgba("#7a4f36"), rgba(INK), 0.8)
    line(draw, [(ox + 5, 13), (ox + 27, 13)], rgba(BRASS), 1.2)


def icon_scale(draw, ox, broken=False):
    if broken:
        line(draw, [(ox + 16, 5), (ox + 14, 14), (ox + 17, 17), (ox + 14, 28)], rgba(PAPER), 1.5)
        line(draw, [(ox + 7, 12), (ox + 26, 9)], rgba(BAD), 1.7)
        line(draw, [(ox + 8, 12), (ox + 4, 22)], rgba(PAPER), 0.9)
        line(draw, [(ox + 25, 9), (ox + 29, 23)], rgba(PAPER), 0.9)
        draw.arc(box(ox + 1, 20, ox + 11, 28), 0, 180, fill=rgba(BAD), width=q(1.3))
        draw.arc(box(ox + 24, 21, ox + 32, 30), 0, 180, fill=rgba(BAD), width=q(1.3))
        line(draw, [(ox + 20, 18), (ox + 24, 21), (ox + 21, 24)], rgba(BAD), 1.2)
    else:
        line(draw, [(ox + 16, 5), (ox + 16, 27)], rgba(PAPER), 1.6)
        line(draw, [(ox + 6, 11), (ox + 26, 11)], rgba(BRASS), 1.7)
        line(draw, [(ox + 7, 11), (ox + 4, 22), (ox + 25, 11), (ox + 28, 22)], rgba(PAPER), 0.9)
        draw.arc(box(ox + 1, 20, ox + 9, 28), 0, 180, fill=rgba(GOOD), width=q(1.5))
        draw.arc(box(ox + 24, 20, ox + 32, 28), 0, 180, fill=rgba(GOOD), width=q(1.5))
        line(draw, [(ox + 10, 28), (ox + 22, 28)], rgba(PAPER), 1.4)


def icons_sheet() -> Image.Image:
    image, draw = canvas(256, 32)
    painters = [icon_coin, icon_rice, icon_people, icon_army, icon_tech, icon_province]
    for i, painter in enumerate(painters):
        painter(draw, i * 32)
    icon_scale(draw, 6 * 32, False)
    icon_scale(draw, 7 * 32, True)
    return finish(image, 256, 32)


def flag_shape(draw, ox, color):
    pts = [(ox + 3, 5), (ox + 42, 5), (ox + 45, 10), (ox + 42, 16), (ox + 45, 22), (ox + 42, 27), (ox + 3, 27)]
    polygon(draw, pts, rgba(color), rgba(INK), 1.2)
    line(draw, [(ox + 5, 7), (ox + 40, 7)], rgba(PAPER, 70), 0.8)


def flags_sheet() -> Image.Image:
    image, draw = canvas(144, 32)
    for i, color in enumerate(NATIONS):
        flag_shape(draw, i * 48, color)
    # Joseon: restrained two-tone taegeuk-like roundel.
    ellipse(draw, (16, 9, 32, 25), rgba(PAPER), rgba(INK), 0.8)
    draw.pieslice(box(17.3, 10.3, 30.7, 23.7), 90, 270, fill=rgba("#b5654f"))
    draw.pieslice(box(17.3, 10.3, 30.7, 23.7), 270, 90, fill=rgba("#2f5a86"))
    ellipse(draw, (20.5, 11.5, 27.2, 18.2), rgba("#2f5a86"))
    ellipse(draw, (20.8, 15.8, 27.5, 22.5), rgba("#b5654f"))
    # China: sun-and-cloud emblem, dynasty-neutral and text-free.
    cx = 48 + 24
    ellipse(draw, (cx - 5.5, 10.5, cx + 5.5, 21.5), rgba(BRASS), rgba(INK), 0.8)
    for angle in range(0, 360, 45):
        a = math.radians(angle)
        line(draw, [(cx + math.cos(a) * 7, 16 + math.sin(a) * 7), (cx + math.cos(a) * 10, 16 + math.sin(a) * 10)], rgba(BRASS), 1)
    # Japan: five-petal plum crest, avoiding a modern national flag.
    cx = 96 + 24
    for angle in range(-90, 270, 72):
        a = math.radians(angle)
        px, py = cx + math.cos(a) * 5.5, 16 + math.sin(a) * 5.5
        ellipse(draw, (px - 4.2, py - 4.2, px + 4.2, py + 4.2), rgba(PAPER), rgba(INK), 0.6)
    ellipse(draw, (cx - 3.2, 12.8, cx + 3.2, 19.2), rgba(BRASS), rgba(INK), 0.6)
    return finish(image, 144, 32)


PORTRAIT_ROBES = ["#36566b", "#486652", "#7a493d", "#5b506e", "#48615f", "#6a5842", "#394c62", "#74413c"]
SKINS = ["#d9ad87", "#cf9d78", "#e0b893", "#c88f6e"]


def portrait_backdrop(draw, ox, oy, index):
    rounded(draw, (ox + 3, oy + 3, ox + 61, oy + 63), 5, rgba("#222a2d", 245), rgba(BRASS, 110), 0.8)
    ellipse(draw, (ox + 9, oy + 7, ox + 55, oy + 54), rgba("#d8cfba", 55))
    line(draw, [(ox + 8, oy + 55), (ox + 56, oy + 55)], rgba(BRASS, 85), 0.8)


def portrait_hat(draw, ox, oy, kind, accent):
    if kind == "gat":
        ellipse(draw, (ox + 13, oy + 18, ox + 51, oy + 29), rgba("#101518", 245), rgba(INK), 1)
        polygon(draw, [(ox + 23, oy + 20), (ox + 27, oy + 7), (ox + 37, oy + 7), (ox + 42, oy + 20)], rgba("#111719", 245), rgba(INK), 1)
        line(draw, [(ox + 21, oy + 23), (ox + 18, oy + 47), (ox + 43, oy + 23), (ox + 46, oy + 47)], rgba(INK, 190), 0.75)
    elif kind == "warrior":
        ellipse(draw, (ox + 13, oy + 19, ox + 51, oy + 29), rgba(accent), rgba(INK), 1)
        polygon(draw, [(ox + 21, oy + 21), (ox + 27, oy + 7), (ox + 37, oy + 7), (ox + 44, oy + 21)], rgba(accent), rgba(INK), 1)
        line(draw, [(ox + 32, oy + 7), (ox + 32, oy + 3)], rgba(BRASS), 1.2)
        ellipse(draw, (ox + 30, oy + 1, ox + 34, oy + 5), rgba(BRASS))
    elif kind == "scholar":
        polygon(draw, [(ox + 21, oy + 22), (ox + 23, oy + 6), (ox + 40, oy + 6), (ox + 43, oy + 22)], rgba("#111719"), rgba(INK), 1)
        line(draw, [(ox + 14, oy + 16), (ox + 23, oy + 14), (ox + 40, oy + 14), (ox + 50, oy + 16)], rgba("#111719"), 4)
    else:  # samo
        rounded(draw, (ox + 22, oy + 6, ox + 42, oy + 23), 5, rgba("#111719"), rgba(INK), 1)
        polygon(draw, [(ox + 23, oy + 15), (ox + 10, oy + 12), (ox + 12, oy + 20), (ox + 24, oy + 19)], rgba("#111719"), rgba(INK), 0.8)
        polygon(draw, [(ox + 41, oy + 15), (ox + 54, oy + 12), (ox + 52, oy + 20), (ox + 40, oy + 19)], rgba("#111719"), rgba(INK), 0.8)


def draw_portrait(draw, ox, oy, index):
    portrait_backdrop(draw, ox, oy, index)
    robe = PORTRAIT_ROBES[(index * 3 + index // 8) % len(PORTRAIT_ROBES)]
    skin = SKINS[(index * 5 + index // 8) % len(SKINS)]
    hat_types = [
        "samo", "gat", "samo", "warrior", "scholar", "gat", "warrior", "samo",
        "gat", "scholar", "warrior", "samo", "gat", "samo", "scholar", "warrior",
    ]
    hat = hat_types[index]
    # Bust and collar.
    polygon(draw, [(ox + 10, oy + 63), (ox + 14, oy + 48), (ox + 25, oy + 41), (ox + 39, oy + 41), (ox + 50, oy + 48), (ox + 55, oy + 63)], rgba(robe), rgba(INK), 1.1)
    polygon(draw, [(ox + 24, oy + 41), (ox + 32, oy + 51), (ox + 40, oy + 41), (ox + 37, oy + 55), (ox + 27, oy + 55)], rgba(PAPER), rgba(INK), 0.8)
    # Anonymous face types.
    ellipse(draw, (ox + 20, oy + 18, ox + 44, oy + 45), rgba(skin), rgba(INK), 1)
    ellipse(draw, (ox + 18.5, oy + 27, ox + 22, oy + 34), rgba(skin), rgba(INK), 0.7)
    ellipse(draw, (ox + 42, oy + 27, ox + 45.5, oy + 34), rgba(skin), rgba(INK), 0.7)
    brow_y = oy + 28 + (index % 5 - 2) * 0.28
    line(draw, [(ox + 24, brow_y), (ox + 29, brow_y - 0.8)], rgba(INK), 0.75)
    line(draw, [(ox + 35, brow_y - 0.8), (ox + 40, brow_y)], rgba(INK), 0.75)
    ellipse(draw, (ox + 26, oy + 30, ox + 27.3, oy + 31.3), rgba(INK))
    ellipse(draw, (ox + 36.7, oy + 30, ox + 38, oy + 31.3), rgba(INK))
    line(draw, [(ox + 32, oy + 30), (ox + 31, oy + 35), (ox + 33, oy + 35.5)], rgba("#8b654f"), 0.65)
    face_style = index % 7
    if face_style == 0:
        line(draw, [(ox + 27, oy + 38), (ox + 32, oy + 40), (ox + 37, oy + 38)], rgba("#6a4032"), 0.7)
    elif face_style in (1, 5):
        line(draw, [(ox + 28, oy + 38.5), (ox + 36, oy + 38.5)], rgba("#6a4032"), 0.7)
        line(draw, [(ox + 26, oy + 38), (ox + 31, oy + 40), (ox + 38, oy + 38)], rgba(INK), 1.2)
    elif face_style in (2, 6):
        line(draw, [(ox + 29, oy + 39), (ox + 35, oy + 39)], rgba("#6a4032"), 0.7)
        beard = "#5d5b57" if index in (9, 14) else INK
        polygon(draw, [(ox + 27, oy + 39), (ox + 32, oy + 49), (ox + 37, oy + 39), (ox + 35, oy + 51), (ox + 29, oy + 51)], rgba(beard, 230))
    else:
        draw.arc(box(ox + 27, oy + 35, ox + 37, oy + 42), 20, 160, fill=rgba("#6a4032"), width=q(0.7))
    portrait_hat(draw, ox, oy, hat, "#98443a")
    # Small rank patch motif, deliberately abstract and text-free.
    rounded(draw, (ox + 27, oy + 55, ox + 37, oy + 63), 1, rgba("#253942"), rgba(BRASS, 170), 0.55)
    line(draw, [(ox + 29, oy + 60), (ox + 32, oy + 57), (ox + 35, oy + 60)], rgba(BRASS, 180), 0.55)
    if index >= 8:
        line(draw, [(ox + 16, oy + 55), (ox + 23, oy + 61)], rgba(BRASS, 95), 0.7)


def portraits_sheet() -> Image.Image:
    image, draw = canvas(512, 128)
    for index in range(16):
        draw_portrait(draw, (index % 8) * 64, (index // 8) * 64, index)
    return finish(image, 512, 128)


def clipped_panel(draw, ox, oy, w, h, cut, fill, outline, width=1):
    polygon(draw, [(ox + cut, oy), (ox + w - cut, oy), (ox + w, oy + cut), (ox + w, oy + h - cut), (ox + w - cut, oy + h), (ox + cut, oy + h), (ox, oy + h - cut), (ox, oy + cut)], fill, outline, width)


def ui_sheet() -> Image.Image:
    image, draw = canvas(576, 64)
    # Cell 0: panel header decoration.
    clipped_panel(draw, 7, 6, 178, 52, 8, rgba("#152128", 245), rgba(INK), 1.5)
    clipped_panel(draw, 11, 10, 170, 44, 6, rgba("#243d49", 225), rgba(BRASS, 210), 0.8)
    line(draw, [(18, 18), (174, 18)], rgba(PAPER, 85), 0.75)
    for x in [24, 168]:
        polygon(draw, [(x, 32), (x + 7, 24), (x + 14, 32), (x + 7, 40)], rgba("#2f6754"), rgba(BRASS, 180), 0.7)
        ellipse(draw, (x + 4, 29, x + 10, 35), rgba("#a74335"), rgba(PAPER, 180), 0.6)
    # Cell 1: button background.
    ox = 192
    clipped_panel(draw, ox + 11, 10, 170, 44, 7, rgba("#1a2a31", 248), rgba(INK), 1.5)
    clipped_panel(draw, ox + 15, 14, 162, 36, 5, rgba("#304e5b", 238), rgba(BRASS), 0.9)
    line(draw, [(ox + 27, 20), (ox + 165, 20)], rgba(PAPER, 80), 0.7)
    ellipse(draw, (ox + 25, 29, ox + 31, 35), rgba(BRASS), rgba(INK), 0.6)
    ellipse(draw, (ox + 161, 29, ox + 167, 35), rgba(BRASS), rgba(INK), 0.6)
    # Cell 2: divider line with understated dancheong knot.
    ox = 384
    line(draw, [(ox + 8, 32), (ox + 76, 32)], rgba(BRASS, 190), 1.2)
    line(draw, [(ox + 116, 32), (ox + 184, 32)], rgba(BRASS, 190), 1.2)
    line(draw, [(ox + 8, 35), (ox + 76, 35)], rgba("#2f6754", 150), 0.65)
    line(draw, [(ox + 116, 35), (ox + 184, 35)], rgba("#2f6754", 150), 0.65)
    polygon(draw, [(ox + 96, 16), (ox + 111, 32), (ox + 96, 48), (ox + 81, 32)], rgba("#24445a"), rgba(BRASS), 1)
    polygon(draw, [(ox + 96, 22), (ox + 105, 32), (ox + 96, 42), (ox + 87, 32)], rgba("#2f6754"), rgba(PAPER, 170), 0.7)
    ellipse(draw, (ox + 92, 28, ox + 100, 36), rgba("#a74335"), rgba(BRASS), 0.6)
    return finish(image, 576, 64)


def load_preview_font(size: int, bold: bool = False):
    names = [
        Path("C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in names:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def alpha_paste_scaled(dst: Image.Image, src: Image.Image, xy, scale: int):
    enlarged = src.resize((src.width * scale, src.height * scale), Image.Resampling.NEAREST)
    dst.alpha_composite(enlarged, xy)


def make_preview(out_dir: Path, destination: Path):
    preview = Image.new("RGBA", (1280, 1240), rgba("#0a0b0e"))
    d = ImageDraw.Draw(preview, "RGBA")
    title = load_preview_font(34, True)
    label = load_preview_font(17, True)
    small = load_preview_font(13)
    d.text((48, 36), "DONGA — HISTORICAL STRATEGY ASSET KIT", font=title, fill=rgba(PAPER))
    d.text((49, 82), "restrained Joseon map painting · exact production sprite sheets", font=small, fill=rgba(BRASS))

    def panel(y, h, heading, detail):
        d.rounded_rectangle((40, y, 1240, y + h), radius=12, fill=rgba("#11181c"), outline=rgba("#665d4d"), width=1)
        d.text((62, y + 18), heading, font=label, fill=rgba(PAPER))
        d.text((62, y + 45), detail, font=small, fill=rgba("#8d918d"))

    terrain = Image.open(out_dir / "terrain.png").convert("RGBA")
    icons = Image.open(out_dir / "icons.png").convert("RGBA")
    flags = Image.open(out_dir / "flags.png").convert("RGBA")
    portraits = Image.open(out_dir / "portraits.png").convert("RGBA")
    frame = Image.open(out_dir / "ui_frame.png").convert("RGBA")

    panel(120, 190, "TERRAIN", "176×44 · four 44×44 seamless cells · plain / hill / mountain / coast")
    alpha_paste_scaled(preview, terrain, (285, 194), 4)
    panel(330, 170, "RESOURCE ICONS", "256×32 · eight 32×32 cells · designed to remain legible at 18×18")
    alpha_paste_scaled(preview, icons, (130, 395), 4)
    panel(520, 150, "FACTION FLAGS", "144×32 · three 48×32 text-free, dynasty-neutral emblems")
    alpha_paste_scaled(preview, flags, (352, 570), 4)
    panel(690, 320, "OFFICIAL PORTRAITS", "512×128 · sixteen anonymous 64×64 court archetypes")
    alpha_paste_scaled(preview, portraits, (128, 746), 2)
    panel(1030, 194, "UI FRAME", "576×64 · panel head / button background / divider")
    alpha_paste_scaled(preview, frame, (64, 1082), 2)
    destination.parent.mkdir(parents=True, exist_ok=True)
    preview.save(destination, "PNG", optimize=True)


def generate(out_dir: Path, preview: Path | None):
    out_dir.mkdir(parents=True, exist_ok=True)
    sheets = {
        "terrain.png": terrain_sheet(),
        "icons.png": icons_sheet(),
        "flags.png": flags_sheet(),
        "portraits.png": portraits_sheet(),
        "ui_frame.png": ui_sheet(),
    }
    for name, image in sheets.items():
        image.save(out_dir / name, "PNG", optimize=True)
    if preview:
        make_preview(out_dir, preview)
    return {name: list(image.size) for name, image in sheets.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("assets"))
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.out, args.preview), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
