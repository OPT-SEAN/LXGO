"""动森（New Horizons）主人公底模 + 草莓园女孩的发型、耳机和衣服。

比例和画法按 refs/ 里的官方渲染图（Player_*_NH.png）：
- 头约占身高 44%，形状是圆角方块：正面较平、腮帮饱满、下巴宽圆
- 五官是画在脸上的贴图：大眼睛（眼白 + 深棕粗描边 + 大虹膜 + 高光 + 睫毛）、
  细线微笑、圆腮红；只有鼻子是立体的小凸起
- 躯干宽约为头宽的一半，胳膊细、末端是圆拳头，腿细而直
- 头发是光滑的整块曲面，带细发丝纹理和一圈柔光；刘海末端有尖
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from helpers import (MeshProbe, Part, active, facing, fuzz, make_image, mat, rgba,
                     rounded_column, smooth_border, stamp_ellipses, uv_grid)

# 头：中心和三个方向的半径（半宽、半深、半高）
HC = Vector((0, 0, 0.76))
HR = Vector((0.245, 0.215, 0.21))
SKIN = "#efb487"


def head_shape(d, grow=1.0):
    """单位球上的方向 d -> 头部表面的点。圆角方块 + 下巴收窄 + 正面压平。"""
    p = 2.6  # 超椭球指数：2 是球，越大越方
    x, y, z = d
    s = (abs(x) ** p + abs(y) ** p + abs(z) ** p) ** (-1 / p)
    x, y, z = x * s, y * s, z * s
    if z < 0:
        k = 1 - 0.14 * z * z
        x, y = x * k, y * k
    if y < 0:
        y *= 0.9
    return HC + Vector((x * HR.x, y * HR.y, z * HR.z)) * grow


# ---------------------------------------------------------------------------
# 贴图
# ---------------------------------------------------------------------------
def face_texture():
    """脸部贴图：从正面投影到头上。坐标 X、Z 都是 -1..1（对应头的半宽、半高）。
    先画 2048 再缩到 1024，线条边缘更平滑。"""
    n = 2048
    uu, vv = uv_grid(n)
    X, Z = uu * 2 - 1, vv * 2 - 1
    px = np.tile(rgba(SKIN), (n, n, 1))
    aspect = HR.x / HR.z  # 让「圆」在头上真的是圆

    def ell(cx, cz, rx, rz):
        return ((X - cx) / rx) ** 2 + ((Z - cz) / rz) ** 2

    def paint(mask, color, alpha=1.0):
        a = np.clip(mask, 0, 1)[..., None] * alpha
        px[:] = px * (1 - a) + rgba(color) * a

    def arc_stroke(points, width, color):
        """沿折线画一定粗细的线（嘴、眉毛、睫毛）。"""
        d = np.full(X.shape, 9.0)
        for (x0, z0), (x1, z1) in zip(points[:-1], points[1:]):
            vx, vz = x1 - x0, (z1 - z0) * aspect
            wx, wz = X - x0, (Z - z0) * aspect
            t = np.clip((wx * vx + wz * vz) / (vx * vx + vz * vz), 0, 1)
            d = np.minimum(d, np.hypot(wx - t * vx, wz - t * vz))
        paint(np.clip((width - d) / 0.004, 0, 1), color)

    brown = "#4a2c20"
    # 腮红：柔和的圆形渐变
    for s in (-1, 1):
        r = np.sqrt(ell(0.66 * s, -0.42, 0.2, 0.2 * aspect))
        paint(np.clip(1 - r, 0, 1) ** 1.5, "#f4907f", 0.55)
    for s in (-1, 1):
        cx, cz = 0.45 * s, -0.08
        # 眼睛：描边 -> 眼白 -> 虹膜 -> 瞳孔 -> 高光
        paint(ell(cx, cz, 0.215, 0.265) < 1, brown)
        paint(ell(cx, cz - 0.012, 0.175, 0.225) < 1, "#fbf6ea")
        ix, iz = cx - 0.025 * s, cz - 0.02
        iris = ell(ix, iz, 0.155, 0.155 * aspect * 1.1)
        paint(iris < 1, "#3f2519")
        paint((iris < 1) & (Z < iz - 0.03), "#5a3624", 0.6)
        paint(ell(ix, iz - 0.01, 0.07, 0.07 * aspect * 1.1) < 1, "#2a1810")
        paint(ell(ix + 0.05 * s, iz + 0.075, 0.045, 0.045 * aspect) < 1, "#ffffff")
        paint(ell(ix - 0.045 * s, iz - 0.07, 0.022, 0.022 * aspect) < 1, "#ffffff", 0.9)
        # 上眼线加粗 + 外眼角两根睫毛
        top = [(cx + 0.215 * math.cos(a) * s, cz + 0.265 * math.sin(a)) for a in np.linspace(0.25, 2.9, 14)]
        arc_stroke(top, 0.028, brown)
        ox, oz = cx + 0.2 * s, cz + 0.14
        arc_stroke([(ox, oz), (ox + 0.09 * s, oz + 0.06)], 0.018, brown)
        arc_stroke([(ox - 0.01 * s, oz + 0.07), (ox + 0.06 * s, oz + 0.15)], 0.016, brown)
        # 眉毛：细弧线
        arc_stroke([(cx - 0.12 * s, 0.29), (cx, 0.335), (cx + 0.12 * s, 0.31)], 0.02, "#2e211c")
    # 嘴：细线微笑
    arc_stroke([(x, -0.6 + 0.09 * (x / 0.2) ** 2) for x in np.linspace(-0.2, 0.2, 15)], 0.022, brown)

    px = px.reshape(n // 2, 2, n // 2, 2, 4).mean(axis=(1, 3))
    return make_image("girl_face", px)


def hair_texture():
    """发丝：沿 u 方向起伏的竖条纹 + 一圈柔和高光。"""
    size = 512
    uu, vv = uv_grid(size)
    rng = np.random.default_rng(21)
    strands = np.zeros(size)
    for f, a in ((40, 0.5), (90, 0.3), (170, 0.2)):
        strands += a * np.sin(uu[0] * f * math.tau + rng.uniform(0, math.tau))
    strands = strands[None, :] * (0.6 + 0.4 * np.sin(vv * 9))
    band = np.exp(-((vv - 0.72) / 0.05) ** 2) * (0.7 + 0.3 * strands)
    base = rgba("#2b2321")
    px = np.tile(base, (size, size, 1))
    px[..., :3] = base[:3] * (1 + 0.18 * strands[..., None]) + np.array([0.34, 0.3, 0.28]) * band[..., None]
    return make_image("girl_hair", px)


def _knit(px, uu, vv, amount=0.035):
    """细密的针织纹：一行行小 V 字，明暗交替。"""
    knit = ((np.floor(vv * 90) % 2) * 2 - 1) * np.sign(np.sin(uu * 180 * math.pi))
    px[..., :3] *= (1 + amount * knit)[..., None]
    return px


def _rib(px, uu, mask):
    """罗纹边（领口、下摆、袖口）：深一点的黄 + 竖向螺纹。"""
    rib = rgba("#c99a34")[:3] * (1 + 0.08 * np.sign(np.sin(uu * 140 * math.pi)))[..., None]
    px[mask, :3] = rib[mask]
    return px


def _tri(t):
    return 2 * np.abs(t - np.floor(t + 0.5))


YELLOW, CREAM, BEAR = "#e2b53c", "#fbefcf", "#6b4226"


def sweater_texture():
    """按设定表：正面一只举手的大熊剪影，两侧竖向大折线，背后一道菱形折线，罗纹下摆和领口。
    球面 UV 里正面(-Y) 在 u=0.25，背面在 0.75，两侧在 0 和 0.5。"""
    size = 1024
    uu, vv = uv_grid(size)
    px = np.tile(rgba(YELLOW), (size, size, 1))
    # 换算成物理尺寸（米），让图案不被拉扁：周长约 0.62，高 0.26
    du = (uu - 0.25 + 0.5) % 1 - 0.5
    X, Y = du * 0.62, (vv - 0.5) * 0.26

    def ell(cx, cy, rx, ry, rot=0.0):
        c, s_ = math.cos(rot), math.sin(rot)
        x, y = X - cx, Y - cy
        return ((x * c + y * s_) / rx) ** 2 + ((-x * s_ + y * c) / ry) ** 2 < 1

    # 两侧竖向折线、背后菱形折线
    for side_u in (0.0, 0.5):
        d = (uu - side_u + 0.5) % 1 - 0.5
        px[np.abs(d - 0.035 * (_tri(vv * 3.5) * 2 - 1)) < 0.03] = rgba(CREAM)
    d = (uu - 0.75 + 0.5) % 1 - 0.5
    zig = 0.05 * _tri(vv * 3.5)
    px[(np.abs(np.abs(d) - zig) < 0.018) | (np.abs(d) < zig * 0.35)] = rgba(CREAM)

    # 正面大熊：身体、头、尖耳朵、举起的双手、两条腿
    k = 0.9
    bear = ell(0, -0.015 * k, 0.052 * k, 0.06 * k) | ell(0, 0.05 * k, 0.04 * k, 0.033 * k)
    for sgn in (-1, 1):
        bear |= ell(0.027 * sgn * k, 0.079 * k, 0.011 * k, 0.02 * k, -0.45 * sgn)
        bear |= ell(0.058 * sgn * k, 0.03 * k, 0.016 * k, 0.042 * k, 0.6 * sgn)
        bear |= ell(0.03 * sgn * k, -0.07 * k, 0.021 * k, 0.026 * k)
    px[bear] = rgba(BEAR)
    face = ell(-0.013 * k, 0.055 * k, 0.005, 0.006) | ell(0.013 * k, 0.055 * k, 0.005, 0.006)
    smile = (np.abs(np.hypot(X, (Y - 0.05 * k) * 1.2) - 0.016) < 0.0025) & (Y < 0.043 * k)
    px[face | smile] = rgba(CREAM)

    px = _rib(px, uu, (vv < 0.09) | (vv > 0.93))
    return make_image("girl_sweater", fuzz(_knit(px, uu, vv), 0.025, 1))


def sleeve_texture():
    """袖子：前后两道沿长度方向的折线，手腕处罗纹袖口（v 从肩膀 0 到手腕 1）。"""
    size = 512
    uu, vv = uv_grid(size)
    px = np.tile(rgba(YELLOW), (size, size, 1))
    for u0 in (0.0, 0.25, 0.5, 0.75):
        d = (uu - u0 + 0.5) % 1 - 0.5
        px[np.abs(d - 0.035 * (_tri(vv * 4) * 2 - 1)) < 0.03] = rgba(CREAM)
    px = _rib(px, uu, vv > 0.84)
    return make_image("girl_sleeve", fuzz(_knit(px, uu, vv), 0.025, 2))


def pants_texture():
    """裤子：两侧各一道奶油色竖条。"""
    size = 512
    uu, vv = uv_grid(size)
    px = np.tile(rgba("#e0b83c"), (size, size, 1))
    for u0 in (0.0, 0.5, 1.0):
        px[np.abs(uu - u0) < 0.03] = rgba(CREAM)
    return make_image("girl_pants", fuzz(_knit(px, uu, vv, 0.02), 0.02, 3))


def shoe_texture():
    """浅蓝运动鞋，鞋面上撒彩色小斑点。"""
    size = 256
    px = np.tile(rgba("#a9d4f0"), (size, size, 1))
    stamp_ellipses(px, 160, [rgba("#f7a8c6"), rgba("#bff0d8"), rgba("#fbe38a"), rgba("#ffffff")],
                   (2, 4), (2, 4), seed=31)
    return make_image("girl_shoe", px)


def gingham_texture():
    size = 128
    idx = np.arange(size) // 16 % 2
    a, b = np.meshgrid(idx, idx)
    red, white = rgba("#e0474c"), rgba("#fbf2e8")
    s = (a + b)[..., None]
    return make_image("gingham", np.where(s == 2, red, np.where(s == 1, (red + white) / 2, white)))


def wicker_texture():
    size = 256
    y, x = np.mgrid[0:size, 0:size]
    cell = (x + (y // 16 % 2) * 16) // 32 % 2
    light, dark = rgba("#d6a262"), rgba("#a8763c")
    px = np.where(cell[..., None] == 1, light, dark).astype(float)
    px = np.where((y % 16 < 2)[..., None], dark * 0.85, px)
    px[..., 3] = 1
    return make_image("wicker", px)


# ---------------------------------------------------------------------------
# 造型
# ---------------------------------------------------------------------------
def shaped_sphere(seg, rings, keep=None, grow=lambda d: 1.0, smooth=0):
    """单位球 ->（可选）按条件挖掉一部分 -> 磨圆切口 -> 套上头的形状。"""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=1)
    o = active()
    bm = bmesh.new()
    bm.from_mesh(o.data)
    if keep is not None:
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep(v.co)], context="VERTS")
        if smooth:
            smooth_border(bm, smooth)
    for v in bm.verts:
        d = v.co.normalized()
        v.co = head_shape(d, grow(d))
    bm.to_mesh(o.data)
    bm.free()
    return o


def build(parent_col):
    P = Part("Girl", parent_col)
    skin = mat("Girl.Skin", SKIN, 0.6)
    b = skin.node_tree.nodes["Principled BSDF"]
    b.inputs["Subsurface Weight"].default_value = 0.25
    b.inputs["Subsurface Scale"].default_value = 0.03
    M = {
        "face": mat("Girl.Face", SKIN, 0.6, face_texture()),
        "skin": skin,
        "nose": mat("Girl.Nose", "#f0977a", 0.55),
        "hair": mat("Girl.Hair", "#2b2321", 0.45, hair_texture(), coat=0.25),
        "sweater": mat("Girl.Sweater", "#e2b53c", 0.95, sweater_texture(), sheen=0.6),
        "sleeve": mat("Girl.Sleeve", "#e2b53c", 0.95, sleeve_texture(), sheen=0.6),
        "pants": mat("Girl.Pants", "#e0b83c", 0.95, pants_texture(), sheen=0.5),
        "rib": mat("Girl.Rib", "#c99a34", 0.95, sheen=0.5),
        "cream": mat("Cream", "#fbf0d2", 0.9, sheen=0.5),
        "bear": mat("Girl.Bear", "#6f4629", 0.9, sheen=0.4),
        "bear_snout": mat("Girl.BearSnout", "#d0a472", 0.9),
        "dark": mat("Dark", "#1c1512", 0.4),
        "sock": mat("Girl.Sock", "#744d2f", 0.9, sheen=0.4),
        "shoe": mat("Girl.Shoe", "#a9d4f0", 0.55, shoe_texture()),
        "sole": mat("Sole", "#fbf8f2", 0.7),
        "hp_blue": mat("Girl.PhoneBlue", "#86c2f0", 0.35, coat=0.3),
        "hp_pink": mat("Girl.PhonePink", "#f7a8c6", 0.5),
        "wicker": mat("Wicker", "#c89556", 0.9, wicker_texture()),
        "wicker_dark": mat("WickerDark", "#9a6a34", 0.9),
        "gingham": mat("Gingham", "#e0474c", 0.9, gingham_texture(), sheen=0.4),
    }
    sk = M["face"].node_tree.nodes["Principled BSDF"]
    sk.inputs["Subsurface Weight"].default_value = 0.25
    sk.inputs["Subsurface Scale"].default_value = 0.03

    # ---------------- 头：圆角方块 + 正面投影的脸部贴图 ----------------
    head = shaped_sphere(64, 32)
    me = head.data
    uv = me.uv_layers.active.data
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        if co.y < 0.02:
            uv[loop.index].uv = (0.5 + co.x / (2 * HR.x), 0.5 + (co.z - HC.z) / (2 * HR.z))
        else:  # 后脑勺统一取贴图角落的纯肤色
            uv[loop.index].uv = (0.02, 0.02)
    P.finish(head, M["face"], "Head")
    probe = MeshProbe(head)

    p, n = probe.front(0.0, HC.z - 0.3 * HR.z, lift=-0.004)
    P.ellipsoid("Nose", M["nose"], p, (0.02, 0.018, 0.017), facing(n))
    for s in (-1, 1):  # 半圆形的耳朵（大部分会被耳机挡住）
        P.ellipsoid(f"Ear.{'R' if s < 0 else 'L'}", M["skin"], (0.24 * s, 0.01, 0.72), (0.03, 0.05, 0.065))

    # ---------------- 头发 ----------------
    # 发壳 + 刘海是同一块曲面：前沿就是刘海的下缘（中分、往两侧扫、末端一簇簇尖角），
    # 前额部分再往外鼓一点做出刘海的厚度，整块没有接缝
    def tri(t):
        return 2 * abs(t - math.floor(t + 0.5))

    def cap_keep(c):
        ax = abs(c.x)
        if c.y < 0.1:
            if ax < 0.03 and c.z < 0.88 and c.y < -0.2:  # 分缝
                return False
            edge = 0.66 - 0.6 * ax - 0.13 * (1 - tri(ax * 5.5 + 0.25))
            if c.y < -0.12 and c.z < edge:
                return False
        return not (c.z < -0.25 and c.y < 0.45)

    def cap_grow(d):
        front = min(1.0, max(0.0, -d.y / 0.5)) * min(1.0, max(0.0, (d.z + 0.1) / 0.5))
        return 1.07 + 0.035 * front
    cap = shaped_sphere(128, 64, cap_keep, grow=cap_grow, smooth=4)
    cap.modifiers.new("Thickness", "SOLIDIFY").thickness = 0.02
    cap.modifiers.new("Smooth", "SUBSURF").levels = 1
    P.finish(cap, M["hair"], "Hair")

    # 高马尾 + 粉色发圈 + 发夹
    tail = [(0, 0.115, 0.95), (0, 0.2, 0.99), (0, 0.3, 0.93), (0, 0.34, 0.82), (0, 0.32, 0.7), (0, 0.27, 0.6)]
    P.tube("Ponytail", M["hair"], tail[:5], (0.8, 1.1, 1.05, 0.9, 0.7), 0.08)
    # 马尾末端散开成几绺，显得蓬松随意（设定表里的马尾比较乱）
    for i, (tx, ty, tz) in enumerate(((-0.05, 0.3, 0.55), (0.0, 0.25, 0.53), (0.05, 0.31, 0.56),
                                      (0.035, 0.36, 0.6), (-0.04, 0.37, 0.62))):
        P.tube(f"PonytailTip{i}", M["hair"],
               [(0, 0.34, 0.8), (tx * 0.5, 0.33 + (ty - 0.33) * 0.4, 0.7), (tx, ty, tz)], (1.0, 0.8, 0.12), 0.035)
    # 脸两侧垂下的碎发，和头顶几根翘起的毛
    for s in (-1, 1):
        for j, (dz, dx) in enumerate(((0.0, 0.0), (-0.04, 0.02))):
            root = head_shape(Vector((0.72 * s, -0.55, 0.3 + dz)).normalized(), 1.08)
            P.tube(f"Wisp{j}.{'R' if s < 0 else 'L'}", M["hair"],
                   [root, root + Vector((0.01 * s, -0.03, -0.07)), root + Vector((dx * s - 0.005 * s, -0.045, -0.15 + dz))],
                   (1.0, 0.75, 0.15), 0.015)
    for j, (x, y) in enumerate(((-0.1, 0.05), (0.08, 0.12), (0.02, -0.02))):
        root = head_shape(Vector((x, y, 1)).normalized(), 1.07)
        P.tube(f"Flyaway{j}", M["hair"], [root, root + Vector((x * 0.3, 0.02, 0.03)), root + Vector((x * 0.6 + 0.02, 0.05, 0.035))],
               (1.0, 0.6, 0.1), 0.006)
    P.torus("HairTie", M["hp_pink"], tail[0], 0.052, 0.018, axis=Vector(tail[1]) - Vector(tail[0]))
    d = Vector((-0.55, -0.45, 0.7)).normalized()
    cp = head_shape(d, 1.12)
    P.ellipsoid("HairClip", M["hp_pink"], cp, (0.045, 0.014, 0.017), facing(cp - HC, 0.5))

    # ---------------- 耳机 ----------------
    P.torus("Headband", M["hp_blue"], (0, 0, 0.74), 0.272, 0.024, axis=(0, -1, 0), half=True)
    for s in (-1, 1):
        side = "R" if s < 0 else "L"
        P.ellipsoid(f"EarCup.{side}", M["hp_blue"], (0.3 * s, 0, 0.72), (0.036, 0.085, 0.085))
        P.torus(f"EarCushion.{side}", M["hp_pink"], (0.268 * s, 0, 0.72), 0.062, 0.021, axis=(1, 0, 0))
        P.ellipsoid(f"EarDot.{side}", M["hp_pink"], (0.337 * s, 0, 0.72), (0.007, 0.046, 0.046))

    # ---------------- 身体：细脖子、窄躯干、细腿 ----------------
    P.capsule("Neck", M["skin"], (0, 0, 0.5), (0, 0, 0.58), 0.032)
    rounded_column(P, "Sweater", M["sweater"], 0.3, 0.56, 0.118, 0.1, depth=0.82)
    P.torus("Collar", M["rib"], (0, 0, 0.553), 0.046, 0.015)  # 正面的大熊画在毛衣贴图上

    rounded_column(P, "Hips", M["pants"], 0.22, 0.32, 0.085, 0.09, depth=0.8)
    for s in (-1, 1):
        side = "R" if s < 0 else "L"
        P.capsule(f"Leg.{side}", M["pants"], (0.048 * s, 0, 0.28), (0.05 * s, 0, 0.12), 0.042)
        # 棕色护腿 + 上沿一圈奶油色毛边
        P.ellipsoid(f"LegWarmer.{side}", M["sock"], (0.05 * s, 0, 0.1), (0.047, 0.047, 0.04))
        P.torus(f"LegFluff.{side}", M["cream"], (0.05 * s, 0, 0.135), 0.043, 0.011)
        P.ellipsoid(f"Shoe.{side}", M["shoe"], (0.05 * s, -0.018, 0.04), (0.05, 0.075, 0.04))
        P.ellipsoid(f"Sole.{side}", M["sole"], (0.05 * s, -0.018, 0.012), (0.052, 0.078, 0.012))

    # ---------------- 手臂：细胳膊 + 圆拳头 ----------------
    def arm(side, shoulder, fist):
        shoulder, fist = Vector(shoulder), Vector(fist)
        dvec = (shoulder - fist).normalized()
        wrist = fist + dvec * 0.04
        P.capsule(f"Sleeve.{side}", M["sleeve"], shoulder, wrist, 0.034, 0.03)
        P.ellipsoid(f"Fist.{side}", M["skin"], fist, (0.042, 0.042, 0.042))

    arm("R", (-0.105, 0, 0.53), (-0.075, -0.2, 0.6))
    P.strawberry("Strawberry.Hand", (-0.045, -0.262, 0.655), 0.04, tip=(0.1, -0.4, -1))

    arm("L", (0.105, 0, 0.53), (0.17, -0.03, 0.34))
    basket = Vector((0.18, -0.03, 0.22))
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.05, radius2=0.062, depth=0.06,
                                    end_fill_type="NOTHING", location=basket)
    bk = active()
    bk.modifiers.new("Thickness", "SOLIDIFY").thickness = 0.006
    P.finish(bk, M["wicker"], "Basket")
    P.ellipsoid("BasketFill", M["wicker_dark"], basket + Vector((0, 0, 0.018)), (0.057, 0.057, 0.009))
    P.torus("BasketRim", M["wicker_dark"], basket + Vector((0, 0, 0.03)), 0.062, 0.008)
    P.torus("BasketHandle", M["wicker_dark"], basket + Vector((0, 0, 0.03)), 0.058, 0.0065,
            axis=(0, -1, 0), half=True)
    for i, (dx, dy, rz) in enumerate(((-0.024, -0.016, 0.3), (0.0, 0.022, -0.4), (0.024, -0.014, 0.9))):
        P.strawberry(f"Strawberry.Basket{i}", basket + Vector((dx, dy, 0.04)), 0.019,
                     tip=(math.sin(rz) * 0.5, math.cos(rz) * 0.5, -1))
    P.ellipsoid("Gingham", M["gingham"], basket + Vector((0.028, -0.026, 0.04)), (0.036, 0.028, 0.008),
                (0.2, -0.45, 0.6))
    return P
