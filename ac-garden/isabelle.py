"""西施惠（同人造型，按印象还原，细节可能与官方不同）。

特征：黄色西施犬；头顶一撮毛用红色发绳扎起、绳上挂着小铃铛；
长长的垂耳；白衬衫外套绿色格子背心；正在朝人挥手。
"""
import numpy as np
from mathutils import Vector

from helpers import Head, Part, facing, fuzz, make_image, mat, rgba, uv_grid


def vest_texture():
    """绿色格子背心：底色 + 横竖两组浅色条纹叠出格子。"""
    size = 256
    uu, vv = uv_grid(size)
    px = np.tile(rgba("#5f9e4a"), (size, size, 1))
    stripe_u = (uu * 16 % 1) < 0.28
    stripe_v = (vv * 12 % 1) < 0.28
    px[stripe_u | stripe_v] = rgba("#7fbb62")
    px[stripe_u & stripe_v] = rgba("#a6d58a")
    return make_image("isabelle_vest", fuzz(px, 0.03, 2))


def build(parent_col):
    P = Part("Isabelle", parent_col)
    M = {
        "fur": mat("Isabelle.Fur", "#f7cf57", 0.85, sheen=0.5),
        "fur_dark": mat("Isabelle.FurDark", "#ebb541", 0.85, sheen=0.5),
        "muzzle": mat("Isabelle.Muzzle", "#fce5a0", 0.85, sheen=0.4),
        "eye": mat("Eye", "#1d1a1a", 0.15, coat=0.6),
        "white": mat("White", "#ffffff", 0.3),
        "nose": mat("Isabelle.Nose", "#2a2020", 0.25, coat=0.5),
        "blush": mat("Blush", "#f7a3a1", 0.8),
        "mouth": mat("Mouth", "#8e3b35", 0.6),
        "shirt": mat("Isabelle.Shirt", "#fbfaf5", 0.9, sheen=0.4),
        "vest": mat("Isabelle.Vest", "#5f9e4a", 0.95, vest_texture(), sheen=0.5),
        "tie": mat("Isabelle.HairTie", "#dc3b3f", 0.5),
        "bell": mat("Isabelle.Bell", "#f2c53a", 0.3, metal=0.7),
    }

    # ---------------- 头 ----------------
    H = Head((0, 0, 0.64), (0.25, 0.23, 0.22))
    P.ellipsoid("Head", M["fur"], H.c, H.r, seg=48, rings=24)

    mp, mn = H.surface(0.0, 0.585)
    P.ellipsoid("Muzzle", M["muzzle"], mp + mn * 0.012, (0.095, 0.06, 0.058), facing(mn))
    P.ellipsoid("Nose", M["nose"], mp + mn * 0.066 + Vector((0, 0, 0.03)), (0.03, 0.02, 0.021))
    pts = []
    for i in range(7):
        t = -1 + 2 * i / 6
        pts.append(mp + mn * 0.071 + Vector((0.024 * t, 0.012 * t * t, -0.018 + 0.008 * t * t)))
    P.tube("Mouth", M["mouth"], pts, [1 - 0.35 * abs(-1 + 2 * i / 6) for i in range(7)], 0.0035)

    for s in (-1, 1):
        side = "R" if s < 0 else "L"
        p, n = H.surface(0.085 * s, 0.672, lift=0.004)
        P.ellipsoid(f"Eye.{side}", M["eye"], p, (0.023, 0.01, 0.03), facing(n))
        P.ellipsoid(f"EyeShine.{side}", M["white"], p + n * 0.009 + Vector((-0.007, 0, 0.011)),
                    (0.008, 0.004, 0.009), facing(n))
        cp, cn = H.surface(0.155 * s, 0.6, lift=0.0015)
        P.ellipsoid(f"Blush.{side}", M["blush"], cp, (0.034, 0.005, 0.018), facing(cn))
        # 长长的垂耳：从头顶两侧垂到脸颊旁，末端微微外翻
        P.ellipsoid(f"Ear.{side}", M["fur_dark"], (0.235 * s, 0.015, 0.6), (0.07, 0.05, 0.165),
                    (0, 0.2 * s, 0))
        P.ellipsoid(f"EarTip.{side}", M["fur_dark"], (0.262 * s, 0.01, 0.46), (0.06, 0.045, 0.05))

    # 头顶那撮毛 + 红发绳 + 小铃铛
    top = Vector((0, 0.0, 0.855))
    P.ellipsoid("Tuft", M["fur"], top + Vector((0, 0, 0.055)), (0.05, 0.05, 0.07))
    for s in (-1, 1):
        P.ellipsoid(f"TuftLobe{s}", M["fur"], top + Vector((0.035 * s, 0, 0.075)), (0.035, 0.035, 0.055),
                    (0, 0.55 * s, 0))
    P.torus("HairTie", M["tie"], top + Vector((0, 0, 0.012)), 0.042, 0.015)
    P.ellipsoid("Bell", M["bell"], top + Vector((0, -0.05, 0.0)), (0.022, 0.022, 0.022))
    P.ellipsoid("BellSlit", M["nose"], top + Vector((0, -0.07, -0.006)), (0.012, 0.004, 0.003))

    # ---------------- 身体：白衬衫 + 绿格子背心 ----------------
    P.ellipsoid("Shirt", M["shirt"], (0, 0, 0.29), (0.122, 0.102, 0.13))
    P.ellipsoid("Vest", M["vest"], (0, 0.004, 0.27), (0.128, 0.106, 0.118))
    for s in (-1, 1):
        P.ellipsoid(f"Collar{s}", M["shirt"], (0.036 * s, -0.088, 0.395), (0.045, 0.012, 0.024),
                    facing((0.25 * s, -1, 0.35), spin=0.55 * s))
    P.ellipsoid("Hips", M["fur"], (0, 0, 0.175), (0.1, 0.085, 0.055))
    P.ellipsoid("Tail", M["fur"], (0, 0.1, 0.2), (0.035, 0.045, 0.035), (-0.7, 0, 0))

    for s in (-1, 1):
        side = "R" if s < 0 else "L"
        P.capsule(f"Leg.{side}", M["fur"], (0.05 * s, 0, 0.16), (0.052 * s, 0, 0.06), 0.042)
        P.ellipsoid(f"Paw.{side}", M["fur"], (0.052 * s, -0.018, 0.03), (0.046, 0.06, 0.03))

    # ---------------- 手臂：右手高高挥起，左手自然下垂 ----------------
    def arm(side, shoulder, hand):
        shoulder, hand = Vector(shoulder), Vector(hand)
        P.ellipsoid(f"Sleeve.{side}", M["shirt"], shoulder, (0.046, 0.046, 0.046))
        P.capsule(f"Arm.{side}", M["fur"], shoulder, hand, 0.034, 0.032)
        P.ellipsoid(f"Hand.{side}", M["fur"], hand, (0.034, 0.03, 0.036))

    arm("R", (-0.118, 0, 0.365), (-0.22, -0.19, 0.52))  # 往前上方举，避开垂耳
    arm("L", (0.118, 0, 0.365), (0.165, -0.03, 0.22))
    return P
