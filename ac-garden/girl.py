"""动森风的草莓园女孩。

和上一版相比，按动森的人物比例调整：
- 头占身高接近一半，更圆；身体和腿都更短
- 眼睛是位置偏低、间距偏宽的竖椭圆，一大一小两颗高光，眼角带一点睫毛
- 鼻子几乎看不见，小嘴，大块腮红
- 头发是一块块有体积的发束，而不是一个光滑头盔
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from helpers import (Head, Part, active, facing, fuzz, make_image, mat, rgba, uv_grid)


def sweater_texture():
    """芥末黄毛衣 + 奶油色双折线纹，加噪点做出毛线的颗粒感。"""
    size = 512
    uu, vv = uv_grid(size)
    tri = 2 * np.abs(uu * 10 - np.floor(uu * 10 + 0.5))
    mask = np.zeros_like(uu, dtype=bool)
    for v0 in (0.24, 0.7):
        for off in (0.0, 0.06):
            zc = v0 + off + 0.04 * (tri * 2 - 1)
            mask |= np.abs(vv - zc) < 0.016
    px = np.tile(rgba("#e8b43c"), (size, size, 1))
    px[mask] = rgba("#fbf0d2")
    return make_image("girl_sweater", fuzz(px, 0.04, 1))


def gingham_texture():
    size = 128
    idx = np.arange(size) // 16 % 2
    a, b = np.meshgrid(idx, idx)
    red, white = rgba("#e0474c"), rgba("#fbf2e8")
    pink = (red + white) / 2
    s = (a + b)[..., None]
    return make_image("gingham", np.where(s == 2, red, np.where(s == 1, pink, white)))


def wicker_texture():
    size = 256
    y, x = np.mgrid[0:size, 0:size]
    row = y // 16
    cell = (x + (row % 2) * 16) // 32 % 2
    light, dark = rgba("#d6a262"), rgba("#a8763c")
    px = np.where(cell[..., None] == 1, light, dark).astype(float)
    px = np.where((y % 16 < 2)[..., None], dark * 0.85, px)
    px[..., 3] = 1
    return make_image("wicker", px)


def build(parent_col):
    P = Part("Girl", parent_col)
    M = {
        "skin": mat("Girl.Skin", "#f0bf98", 0.7, sheen=0.2),
        "hair": mat("Girl.Hair", "#2e2320", 0.45, coat=0.3),
        "eye": mat("Eye", "#1d1a1a", 0.15, coat=0.6),
        "white": mat("White", "#ffffff", 0.3),
        "blush": mat("Blush", "#f7a3a1", 0.8),
        "mouth": mat("Mouth", "#8e3b35", 0.6),
        "sweater": mat("Girl.Sweater", "#e8b43c", 0.95, sweater_texture(), sheen=0.6),
        "cream": mat("Cream", "#fbf0d2", 0.9, sheen=0.5),
        "bear": mat("Girl.Bear", "#6f4629", 0.9, sheen=0.4),
        "bear_snout": mat("Girl.BearSnout", "#d0a472", 0.9),
        "dark": mat("Dark", "#1c1512", 0.4),
        "sock": mat("Girl.Sock", "#744d2f", 0.9, sheen=0.4),
        "shoe": mat("Girl.Shoe", "#a6d6f2", 0.55),
        "sole": mat("Sole", "#fbf8f2", 0.7),
        "hp_blue": mat("Girl.PhoneBlue", "#86c2f0", 0.35, coat=0.3),
        "hp_pink": mat("Girl.PhonePink", "#f7a8c6", 0.5),
        "wicker": mat("Wicker", "#c89556", 0.9, wicker_texture()),
        "wicker_dark": mat("WickerDark", "#9a6a34", 0.9),
        "gingham": mat("Gingham", "#e0474c", 0.9, gingham_texture(), sheen=0.4),
    }

    # ---------------- 头 ----------------
    H = Head((0, 0, 0.68), (0.27, 0.25, 0.255))
    P.ellipsoid("Head", M["skin"], H.c, H.r, seg=48, rings=24)

    for s in (-1, 1):
        side = "R" if s < 0 else "L"
        p, n = H.surface(0.1 * s, 0.655, lift=0.004)
        P.ellipsoid(f"Eye.{side}", M["eye"], p, (0.036, 0.013, 0.05), facing(n))
        P.ellipsoid(f"EyeShine.{side}", M["white"], p + n * 0.012 + Vector((-0.011, 0, 0.018)),
                    (0.013, 0.005, 0.016), facing(n))
        P.ellipsoid(f"EyeShine2.{side}", M["white"], p + n * 0.012 + Vector((0.01, 0, -0.02)),
                    (0.006, 0.003, 0.006), facing(n))
        lp, ln = H.surface(0.133 * s, 0.692, lift=0.003)  # 眼角的小睫毛
        P.ellipsoid(f"Lash.{side}", M["eye"], lp, (0.016, 0.004, 0.0045), facing(ln, spin=-0.55 * s))
        cp, cn = H.surface(0.168 * s, 0.598, lift=0.0015)
        P.ellipsoid(f"Blush.{side}", M["blush"], cp, (0.04, 0.006, 0.022), facing(cn))

    p, n = H.surface(0.0, 0.615, lift=0.001)
    P.ellipsoid("Nose", M["skin"], p, (0.01, 0.006, 0.007), facing(n))
    pts, radii = [], []
    for i in range(7):
        t = -1 + 2 * i / 6
        mp, _ = H.surface(0.022 * t, 0.572 + 0.008 * t * t, lift=0.001)
        pts.append(mp)
        radii.append(1.0 - 0.35 * abs(t))
    P.tube("Mouth", M["mouth"], pts, radii, 0.004)

    # ---------------- 头发 ----------------
    # 1) 发壳：比头大一圈的球，挖掉脸部，再把切口磨圆
    bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1)
    hair = active()
    bm = bmesh.new()
    bm.from_mesh(hair.data)
    cut = [v for v in bm.verts
           if (v.co.y < -0.2 and v.co.z < 0.5 - 1.3 * v.co.x ** 2) or (v.co.z < -0.5 and v.co.y < 0.35)]
    bmesh.ops.delete(bm, geom=cut, context="VERTS")
    border = {v for e in bm.edges if e.is_boundary for v in e.verts}
    for _ in range(20):
        moved = {}
        for v in border:
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb) == 2:
                moved[v] = (v.co * 0.5 + (nb[0].co + nb[1].co) * 0.25).normalized()
        for v, co in moved.items():
            v.co = co
    bm.to_mesh(hair.data)
    bm.free()
    hair.location = H.c
    hair.scale = H.r * 1.06
    hair.modifiers.new("Thickness", "SOLIDIFY").thickness = 0.014
    P.finish(hair, M["hair"], "HairCap")

    # 2) 刘海：中分，两侧各两块扁而圆润的发束沿发际线排开，盖住发壳的切口
    for s in (-1, 1):
        side = "R" if s < 0 else "L"
        for i, (x, z, sx, sz, spin) in enumerate(((0.08, 0.855, 0.105, 0.055, 0.42),
                                                  (0.2, 0.73, 0.06, 0.1, 0.3))):
            bp, bn = H.surface(x * s, z, grow=1.06, lift=0.002)
            P.ellipsoid(f"Bang{i}.{side}", M["hair"], bp, (sx, 0.022, sz), facing(bn, spin=spin * s))
        # 耳前垂下的一缕
        sp, sn = H.surface(0.245 * s, 0.56, grow=1.04, lift=0.0)
        P.ellipsoid(f"SideLock.{side}", M["hair"], sp, (0.04, 0.035, 0.09), facing(sn, spin=-0.1 * s))

    # 3) 高马尾：脑后上方一根胖乎乎的发束，粉色发圈
    tail = [(0.0, 0.16, 0.92), (0.0, 0.26, 0.93), (0.0, 0.34, 0.84),
            (0.0, 0.36, 0.72), (0.0, 0.33, 0.61), (0.0, 0.28, 0.53)]
    P.tube("Ponytail", M["hair"], tail, (0.85, 1.15, 1.1, 0.95, 0.7, 0.25), 0.075)
    P.torus("HairTie", M["hp_pink"], tail[0], 0.05, 0.018, axis=Vector(tail[1]) - Vector(tail[0]))

    cp, cn = H.dir_point((-0.5, -0.4, 0.77), grow=1.06, lift=0.012)
    P.ellipsoid("HairClip", M["hp_pink"], cp, (0.045, 0.014, 0.017), facing(cn, 0.5))

    # ---------------- 耳机 ----------------
    P.torus("Headband", M["hp_blue"], (0, 0, 0.66), 0.318, 0.025, axis=(0, -1, 0), half=True)
    for s in (-1, 1):
        side = "R" if s < 0 else "L"
        P.ellipsoid(f"EarCup.{side}", M["hp_blue"], (0.33 * s, 0, 0.66), (0.038, 0.082, 0.082))
        P.torus(f"EarCushion.{side}", M["hp_pink"], (0.298 * s, 0, 0.66), 0.06, 0.021, axis=(1, 0, 0))
        P.ellipsoid(f"EarDot.{side}", M["hp_pink"], (0.366 * s, 0, 0.66), (0.007, 0.045, 0.045))

    # ---------------- 身体 ----------------
    P.ellipsoid("Sweater", M["sweater"], (0, 0, 0.3), (0.135, 0.112, 0.145))
    P.torus("Collar", M["cream"], (0, 0, 0.435), 0.07, 0.018)
    P.ellipsoid("Hips", M["sweater"], (0, 0, 0.19), (0.108, 0.09, 0.06))

    P.ellipsoid("Bear.Head", M["bear"], (0, -0.107, 0.3), (0.046, 0.016, 0.038))
    for s in (-1, 1):
        P.ellipsoid(f"Bear.Ear{s}", M["bear"], (0.036 * s, -0.099, 0.335), (0.016, 0.01, 0.016))
        P.ellipsoid(f"Bear.Eye{s}", M["dark"], (0.016 * s, -0.121, 0.31), (0.0055, 0.004, 0.0055))
    P.ellipsoid("Bear.Snout", M["bear_snout"], (0, -0.121, 0.29), (0.018, 0.008, 0.013))
    P.ellipsoid("Bear.Nose", M["dark"], (0, -0.129, 0.295), (0.006, 0.004, 0.005))

    for s in (-1, 1):
        side = "R" if s < 0 else "L"
        P.capsule(f"Leg.{side}", M["sweater"], (0.055 * s, 0, 0.17), (0.058 * s, 0, 0.075), 0.046)
        P.ellipsoid(f"Sock.{side}", M["sock"], (0.058 * s, 0, 0.068), (0.044, 0.044, 0.02))
        P.ellipsoid(f"Shoe.{side}", M["shoe"], (0.058 * s, -0.016, 0.036), (0.05, 0.072, 0.036))
        P.ellipsoid(f"Sole.{side}", M["sole"], (0.058 * s, -0.016, 0.011), (0.052, 0.075, 0.011))

    # ---------------- 手臂：右手草莓送到嘴边，左手拎竹篮 ----------------
    def arm(side, shoulder, hand):
        shoulder, hand = Vector(shoulder), Vector(hand)
        d = (shoulder - hand).normalized()
        wrist = hand + d * 0.03
        P.capsule(f"Sleeve.{side}", M["sweater"], shoulder, wrist, 0.042, 0.036)
        P.torus(f"Cuff.{side}", M["cream"], wrist, 0.032, 0.012, axis=-d)
        P.ellipsoid(f"Hand.{side}", M["skin"], hand, (0.034, 0.034, 0.034))

    arm("R", (-0.115, 0, 0.39), (-0.08, -0.215, 0.49))
    P.strawberry("Strawberry.Hand", (-0.05, -0.265, 0.535), 0.04, tip=(0.1, -0.4, -1))

    arm("L", (0.115, 0, 0.39), (0.19, -0.02, 0.225))
    basket = Vector((0.2, -0.02, 0.105))
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.056, radius2=0.07, depth=0.07,
                                    end_fill_type="NOTHING", location=basket)
    b = active()
    b.modifiers.new("Thickness", "SOLIDIFY").thickness = 0.006
    P.finish(b, M["wicker"], "Basket")
    P.ellipsoid("BasketFill", M["wicker_dark"], basket + Vector((0, 0, 0.022)), (0.064, 0.064, 0.01))
    P.torus("BasketRim", M["wicker_dark"], basket + Vector((0, 0, 0.035)), 0.07, 0.009)
    P.torus("BasketHandle", M["wicker_dark"], basket + Vector((0, 0, 0.035)), 0.065, 0.007,
            axis=(0, -1, 0), half=True)
    for i, (dx, dy, rz) in enumerate(((-0.028, -0.018, 0.3), (0.0, 0.024, -0.4), (0.026, -0.016, 0.9),
                                      (-0.02, 0.026, 1.6))):
        P.strawberry(f"Strawberry.Basket{i}", basket + Vector((dx, dy, 0.046)), 0.02,
                     tip=(math.sin(rz) * 0.5, math.cos(rz) * 0.5, -1))
    P.ellipsoid("Gingham", M["gingham"], basket + Vector((0.032, -0.03, 0.045)), (0.042, 0.032, 0.009),
                (0.2, -0.45, 0.6))
    return P
