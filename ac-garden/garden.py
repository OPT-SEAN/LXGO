"""动森风的草莓园小场景。

动森画面的几个关键：
- 地面往远处弯下去（「滚筒」世界），地平线是一条弧线
- 草地上满是小三角/小叶片的花纹，颜色饱满
- 树、花、石头都是圆润的块状，没有尖锐的细节
"""
import math
import random

import bpy
import numpy as np
from mathutils import Euler, Vector

from helpers import Part, active, fuzz, make_image, mat, rgba, stamp_ellipses

BEND_START, BEND = 1.8, 0.06


def ground_z(x, y):
    """地面高度：y 超过 BEND_START 后按抛物线往下弯。"""
    return -BEND * max(0.0, y - BEND_START) ** 2


def grass_texture():
    size = 512
    px = np.tile(rgba("#87c95a"), (size, size, 1))
    stamp_ellipses(px, 420, [rgba("#9dd86e"), rgba("#a9de7a")], (5, 9), (2, 3), seed=11)
    stamp_ellipses(px, 260, [rgba("#72b64c")], (4, 8), (1.5, 2.5), seed=12)
    return make_image("grass", fuzz(px, 0.03, 13))


def build(parent_col):
    rnd = random.Random(7)
    P = Part("Garden", parent_col)
    M = {
        "grass": mat("Grass", "#87c95a", 1.0, grass_texture()),
        "stone": mat("Stone", "#e9dcb6", 0.9),
        "stone2": mat("Stone2", "#d8c89e", 0.9),
        "wood": mat("Wood", "#b8804a", 0.85),
        "wood_dark": mat("WoodDark", "#8d5e35", 0.85),
        "soil": mat("Soil", "#6e4a33", 1.0),
        "leaf": [mat("Leaf1", "#3f9440", 0.7, sheen=0.3), mat("Leaf2", "#4fa84a", 0.7, sheen=0.3),
                 mat("Leaf3", "#62b653", 0.7, sheen=0.3)],
        "petal": mat("Petal", "#fdfbf4", 0.7),
        "pollen": mat("Pollen", "#f6cf45", 0.7),
        "fence": mat("Fence", "#f6f3ea", 0.7),
        "trunk": mat("Trunk", "#8e603c", 0.9),
        "canopy": mat("Canopy", "#57a849", 0.85, sheen=0.4),
        "canopy2": mat("Canopy2", "#4a9a40", 0.85, sheen=0.4),
        "ink": mat("SignInk", "#5a3a22", 0.8),
        "board": mat("Chalkboard", "#2f4a3c", 0.9),
        "chalk": mat("Chalk", "#f6f2e6", 0.9),
        "chalk_red": mat("ChalkRed", "#f47c7c", 0.9),
        "flowers": [mat("FlowerPink", "#f7a6c2", 0.7), mat("FlowerYellow", "#f8d54c", 0.7),
                    mat("FlowerPurple", "#a98ddc", 0.7), mat("FlowerWhite", "#fdfbf4", 0.7)],
        "stem": mat("Stem", "#4a9a3e", 0.8),
    }

    # ---------------- 地面：细分网格 + 远处下弯 ----------------
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=90, y_subdivisions=90, size=30, calc_uvs=True)
    g = active()
    for v in g.data.vertices:
        v.co.z = ground_z(v.co.x, v.co.y)
    for d in g.data.uv_layers.active.data:  # 草地贴图每 1 个单位重复一次
        d.uv = d.uv * 30
    P.finish(g, M["grass"], "Ground")

    # ---------------- 石板小路：从画面前方蜿蜒通向栅栏门 ----------------
    y = -1.6
    while y < 1.5:
        cx = 0.12 * math.sin(y * 1.3)
        for side in (-1, 1):
            x = cx + side * rnd.uniform(0.07, 0.13)
            s = rnd.uniform(0.09, 0.13)
            P.ellipsoid(f"Stone{y:.2f}{side}", M["stone"] if rnd.random() < 0.6 else M["stone2"],
                        (x, y + rnd.uniform(-0.04, 0.04), ground_z(x, y) + 0.004),
                        (s, s * rnd.uniform(0.75, 0.95), 0.016), (0, 0, rnd.uniform(0, 3.14)), seg=16, rings=8)
        y += rnd.uniform(0.2, 0.26)

    # ---------------- 草莓种植床 ----------------
    def plant(name, c):
        for k in range(7):
            a = k / 7 * math.tau + rnd.uniform(-0.2, 0.2)
            r = rnd.uniform(0.045, 0.07)
            P.ellipsoid(f"{name}.Leaf{k}", rnd.choice(M["leaf"]),
                        c + Vector((math.cos(a) * r, math.sin(a) * r, rnd.uniform(0.06, 0.1))),
                        (0.045, 0.068, 0.011), (rnd.uniform(0.35, 0.6), 0, a - math.pi / 2), seg=14, rings=8)
        for k in range(rnd.choice((2, 3))):
            a = rnd.uniform(0, math.tau)
            P.strawberry(f"{name}.Berry{k}", c + Vector((math.cos(a) * 0.1, math.sin(a) * 0.1, 0.05)),
                         0.028, tip=(math.cos(a) * 0.3, math.sin(a) * 0.3, -1), seeds=False,
                         ripe=rnd.random() < 0.75)
        if rnd.random() < 0.7:
            fc = c + Vector((rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), 0.13))
            for k in range(5):
                a = k / 5 * math.tau
                P.ellipsoid(f"{name}.Petal{k}", M["petal"],
                            fc + Vector((math.cos(a) * 0.014, math.sin(a) * 0.014, 0)),
                            (0.011, 0.016, 0.004), (0, 0, a - math.pi / 2), seg=10, rings=6)
            P.ellipsoid(f"{name}.Pollen", M["pollen"], fc + Vector((0, 0, 0.004)), (0.008, 0.008, 0.005),
                        seg=10, rings=6)

    def bed(name, center, w=1.3, d=0.46, h=0.14):
        c = Vector(center)
        t = 0.04
        for s in (-1, 1):
            P.box(f"{name}.PlankF{s}", M["wood"], c + Vector((0, s * (d / 2 - t / 2), h / 2)), (w, t, h), 0.01)
            P.box(f"{name}.PlankS{s}", M["wood_dark"], c + Vector((s * (w / 2 - t / 2), 0, h / 2)),
                  (t, d - 2 * t, h), 0.01)
        P.box(f"{name}.Soil", M["soil"], c + Vector((0, 0, h / 2 - 0.01)), (w - 2 * t, d - 2 * t, h - 0.02), 0)
        for i in range(5):
            plant(f"{name}.Plant{i}", c + Vector((-w / 2 + 0.16 + i * (w - 0.32) / 4,
                                                 rnd.uniform(-0.05, 0.05), h - 0.02)))

    bed("BedL", (-1.05, 0.85, 0))
    bed("BedR", (1.05, 0.85, 0))
    bed("BedL2", (-1.05, -0.35, 0))

    # ---------------- 白色栅栏，中间留门 ----------------
    fy = 1.45
    x = -2.6
    while x <= 2.6:
        if abs(x) > 0.3:
            P.box(f"Picket{x:.2f}", M["fence"], (x, fy, 0.2), (0.05, 0.022, 0.4), 0.008)
            P.cone(f"PicketTop{x:.2f}", M["fence"], (x, fy, 0.425), 0.036, 0.0, 0.05,
                   rot=(0, 0, math.pi / 4), verts=4)
        x += 0.13
    for s in (-1, 1):
        for zz in (0.12, 0.3):
            P.box(f"Rail{s}{zz}", M["fence"], (s * 1.47, fy + 0.018, zz), (2.34, 0.018, 0.035), 0.006)

    # ---------------- 木牌「草莓园」（门口）和小黑板「今日采摘 20」 ----------------
    sx, sy = -0.55, 1.28
    for s in (-1, 1):
        P.box(f"SignPost{s}", M["wood_dark"], (sx + s * 0.2, sy, 0.3), (0.04, 0.04, 0.6), 0.008)
    P.box("SignBoard", M["wood"], (sx, sy - 0.025, 0.55), (0.56, 0.035, 0.2), 0.015)
    P.text("SignText", M["ink"], "草莓园", (sx, sy - 0.046, 0.55), 0.12)

    bx, by = 1.55, 0.05
    turn = math.radians(-18)
    fwd = Vector((math.sin(turn), -math.cos(turn), 0))  # 黑板正面朝向
    for s in (-1, 1):
        off = Vector((math.cos(turn), math.sin(turn), 0)) * 0.19 * s
        P.box(f"BoardLeg{s}", M["wood_dark"], Vector((bx, by, 0.2)) + off - fwd * 0.03, (0.035, 0.035, 0.4),
              0.006, rot=(0.12, 0, turn))
    base = Vector((bx, by, 0.36))
    P.box("BoardFrame", M["wood"], base, (0.44, 0.03, 0.32), 0.012, rot=(0, 0, turn))
    P.box("Board", M["board"], base + fwd * 0.012, (0.39, 0.012, 0.27), 0.004, rot=(0, 0, turn))
    P.text("BoardText1", M["chalk"], "今日采摘", base + fwd * 0.02 + Vector((0, 0, 0.06)), 0.07,
           rot=(math.pi / 2, 0, turn))
    P.text("BoardText2", M["chalk_red"], "20", base + fwd * 0.02 + Vector((0, 0, -0.05)), 0.11,
           rot=(math.pi / 2, 0, turn))

    # ---------------- 圆润的树（在远处弯下去的地面上） ----------------
    for i, (tx, ty, k) in enumerate(((-2.3, 2.7, 1.0), (2.5, 3.0, 1.1), (-0.9, 3.7, 0.9),
                                     (1.1, 4.3, 1.0), (-3.3, 4.6, 1.2), (3.6, 5.0, 1.0))):
        z0 = ground_z(tx, ty)
        P.cone(f"Tree{i}.Trunk", M["trunk"], (tx, ty, z0 + 0.35 * k), 0.09 * k, 0.06 * k, 0.7 * k,
               verts=12, cap=False)
        top = Vector((tx, ty, z0 + 1.0 * k))
        P.ellipsoid(f"Tree{i}.Crown", M["canopy"], top, (0.5 * k, 0.5 * k, 0.45 * k), seg=24, rings=12)
        for j in range(5):
            a = j / 5 * math.tau + i
            P.ellipsoid(f"Tree{i}.Lobe{j}", M["canopy2"] if j % 2 else M["canopy"],
                        top + Vector((math.cos(a) * 0.32 * k, math.sin(a) * 0.32 * k, rnd.uniform(-0.15, 0.15) * k)),
                        (0.28 * k, 0.28 * k, 0.26 * k), seg=20, rings=10)

    # ---------------- 地上的小花和草丛 ----------------
    spots = [(-1.9, -0.9), (-1.7, -1.3), (-2.1, -0.4), (1.9, -0.9), (2.2, -0.5), (1.7, -1.35),
             (-0.6, -1.5), (0.7, -1.45), (2.3, 0.6), (-2.3, 0.9)]
    for i, (fx, fy2) in enumerate(spots):
        for j in range(3):
            px, py = fx + rnd.uniform(-0.15, 0.15), fy2 + rnd.uniform(-0.12, 0.12)
            h = rnd.uniform(0.1, 0.16)
            P.cone(f"Flower{i}{j}.Stem", M["stem"], (px, py, h / 2), 0.006, 0.004, h, verts=6, cap=False)
            col = M["flowers"][(i + j) % 4]
            for k in range(5):
                a = k / 5 * math.tau
                P.ellipsoid(f"Flower{i}{j}.Petal{k}", col,
                            (px + math.cos(a) * 0.022, py + math.sin(a) * 0.022, h),
                            (0.016, 0.022, 0.006), (0.25, 0, a - math.pi / 2), seg=10, rings=6)
            P.ellipsoid(f"Flower{i}{j}.Center", M["pollen"], (px, py, h + 0.004), (0.01, 0.01, 0.007),
                        seg=10, rings=6)
    for i in range(40):
        gx, gy = rnd.uniform(-2.8, 2.8), rnd.uniform(-1.7, 1.3)
        if abs(gx) < 0.4 or (0.55 < abs(gx) < 1.75 and (0.55 < gy < 1.15 or (gx < 0 and -0.65 < gy < -0.05))):
            continue  # 避开小路和种植床
        for j in range(3):
            a = j / 3 * math.tau + rnd.uniform(0, 1)
            P.cone(f"Tuft{i}.{j}", M["leaf"][j % 3], (gx + math.cos(a) * 0.02, gy + math.sin(a) * 0.02, 0.03),
                   0.02, 0.0, 0.07, rot=(math.cos(a) * 0.35, -math.sin(a) * 0.35, 0), verts=6)
    return P
