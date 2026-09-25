"""狸克（同人造型，按印象还原，细节可能与官方不同）。

特征：圆滚滚的狸猫；眼睛周围一圈深棕色「眼罩」；奶油色的嘴套和黑鼻头；
深色的圆耳朵和四肢；穿绿色树叶花纹的夏威夷衫；大尾巴；双手捧着一箱草莓。
"""
import math

import numpy as np
from mathutils import Vector

from helpers import Head, Part, facing, fuzz, make_image, mat, rgba, stamp_ellipses


def aloha_texture():
    """夏威夷衫：绿色底，随机盖上深浅不一的叶片。"""
    size = 512
    px = np.tile(rgba("#4f9d6c"), (size, size, 1))
    stamp_ellipses(px, 26, [rgba("#2f6f4c")], (26, 40), (9, 14), seed=3)
    stamp_ellipses(px, 26, [rgba("#9fd684"), rgba("#c8eb9e")], (20, 34), (7, 11), seed=4)
    return make_image("nook_aloha", fuzz(px, 0.03, 5))


def build(parent_col):
    P = Part("Nook", parent_col)
    M = {
        "fur": mat("Nook.Fur", "#c49563", 0.85, sheen=0.5),
        "dark": mat("Nook.FurDark", "#5f4331", 0.85, sheen=0.4),
        "cream": mat("Nook.Cream", "#f4e5c6", 0.85, sheen=0.4),
        "eye": mat("Eye", "#1d1a1a", 0.15, coat=0.6),
        "white": mat("White", "#ffffff", 0.3),
        "nose": mat("Nook.Nose", "#231b18", 0.25, coat=0.5),
        "mouth": mat("Mouth", "#8e3b35", 0.6),
        "shirt": mat("Nook.Shirt", "#4f9d6c", 0.9, aloha_texture(), sheen=0.3),
        "crate": mat("Crate", "#c99a5e", 0.9),
        "crate_dark": mat("CrateDark", "#a47440", 0.9),
    }

    # ---------------- 头 ----------------
    H = Head((0, 0, 0.64), (0.255, 0.235, 0.225))
    P.ellipsoid("Head", M["fur"], H.c, H.r, seg=48, rings=24)

    for s in (-1, 1):
        side = "R" if s < 0 else "L"
        # 狸猫的「眼罩」：外侧略微下垂的深色椭圆
        kp, kn = H.surface(0.088 * s, 0.668, lift=-0.004)
        P.ellipsoid(f"Mask.{side}", M["dark"], kp, (0.082, 0.016, 0.056), facing(kn, spin=0.3 * s))
        p, n = H.surface(0.085 * s, 0.675, lift=0.011)
        P.ellipsoid(f"Eye.{side}", M["eye"], p, (0.022, 0.01, 0.028), facing(n))
        P.ellipsoid(f"EyeShine.{side}", M["white"], p + n * 0.009 + Vector((-0.007, 0, 0.01)),
                    (0.008, 0.004, 0.009), facing(n))
        # 圆耳朵：深色外圈 + 奶油色内侧
        P.ellipsoid(f"Ear.{side}", M["dark"], (0.165 * s, 0.02, 0.835), (0.07, 0.035, 0.066),
                    (0, 0.35 * s, 0))
        P.ellipsoid(f"EarInner.{side}", M["cream"], (0.16 * s, -0.012, 0.832), (0.044, 0.012, 0.04),
                    (0, 0.35 * s, 0))

    mp, mn = H.surface(0.0, 0.585)
    P.ellipsoid("Muzzle", M["cream"], mp + mn * 0.018, (0.115, 0.075, 0.074), facing(mn))
    P.ellipsoid("Nose", M["nose"], mp + mn * 0.085 + Vector((0, 0, 0.032)), (0.036, 0.022, 0.025))
    pts = [mp + mn * 0.09 + Vector((0.028 * t, 0.014 * t * t, -0.022 + 0.01 * t * t))
           for t in np.linspace(-1, 1, 7)]
    P.tube("Mouth", M["mouth"], pts, [1 - 0.35 * abs(t) for t in np.linspace(-1, 1, 7)], 0.0038)

    # ---------------- 身体：圆滚滚 + 夏威夷衫 ----------------
    P.ellipsoid("Shirt", M["shirt"], (0, 0, 0.28), (0.152, 0.132, 0.142))
    for s in (-1, 1):
        P.ellipsoid(f"Collar{s}", M["shirt"], (0.045 * s, -0.1, 0.39), (0.055, 0.014, 0.03),
                    facing((0.3 * s, -1, 0.4), spin=0.6 * s))
    P.ellipsoid("Neck", M["cream"], (0, -0.075, 0.405), (0.045, 0.03, 0.03))
    P.ellipsoid("Hips", M["dark"], (0, 0, 0.165), (0.12, 0.1, 0.06))

    # 大尾巴：从屁股后面翘起，尾尖深色
    P.ellipsoid("Tail", M["fur"], (0, 0.17, 0.2), (0.07, 0.11, 0.075), (0.5, 0, 0))
    P.ellipsoid("TailTip", M["dark"], (0, 0.26, 0.25), (0.058, 0.05, 0.058))

    for s in (-1, 1):
        side = "R" if s < 0 else "L"
        P.capsule(f"Leg.{side}", M["dark"], (0.065 * s, 0, 0.15), (0.066 * s, 0, 0.06), 0.048)
        P.ellipsoid(f"Foot.{side}", M["dark"], (0.066 * s, -0.018, 0.03), (0.05, 0.065, 0.03))

    # ---------------- 手臂：双手捧着草莓箱 ----------------
    crate = Vector((0, -0.215, 0.27))
    for s in (-1, 1):
        side = "R" if s < 0 else "L"
        shoulder = Vector((0.14 * s, -0.01, 0.35))
        hand = Vector((0.115 * s, -0.19, 0.25))
        P.ellipsoid(f"Sleeve.{side}", M["shirt"], shoulder, (0.056, 0.056, 0.05))
        P.capsule(f"Arm.{side}", M["dark"], shoulder, hand, 0.036, 0.034)
        P.ellipsoid(f"Hand.{side}", M["dark"], hand, (0.036, 0.034, 0.036))

    P.box("Crate", M["crate"], crate, (0.2, 0.12, 0.08), bevel=0.008)
    for s in (-1, 1):
        P.box(f"CrateSlat{s}", M["crate_dark"], crate + Vector((0, -0.061, 0.018 * s)), (0.205, 0.006, 0.022),
              bevel=0.003)
    for i in range(8):
        x = -0.07 + (i % 4) * 0.047
        y = -0.025 if i < 4 else 0.025
        P.strawberry(f"Strawberry.Crate{i}", crate + Vector((x, y, 0.058)), 0.024,
                     tip=(math.sin(i * 1.7) * 0.4, math.cos(i * 1.7) * 0.4, -1), seeds=i % 2 == 0)
    return P
