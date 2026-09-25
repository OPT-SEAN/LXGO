"""草莓园女孩：用 Blender Python 脚本从零搭建 Q 版角色。

运行方式（需要 Blender 4.2，或 pip 安装的 bpy==4.2.*）：
    python build_character.py <输出目录>             # 建模 + 导出 + 渲染预览
    python build_character.py <输出目录> --no-render  # 只建模和导出
    blender -b -P build_character.py -- <输出目录>    # 用 Blender 本体运行

产物：
    strawberry_girl.blend  可在 Blender 里打开继续改
    strawberry_girl.glb    给 Three.js 等引擎用的模型
    preview_front.png / preview_back.png  渲染预览

坐标约定：Blender 是 Z 轴向上，角色面朝 -Y，身高约 1 个单位；
角色的右手在 -X 一侧。
"""
import math
import os
import sys

import bpy  # 必须先于 bmesh / mathutils 导入（pip 版 bpy 由它注册这些模块）
import bmesh
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

# 兼容两种运行方式：blender -b -P xxx.py -- out，以及 python xxx.py out
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
flags = {a for a in argv if a.startswith("--")}
args = [a for a in argv if not a.startswith("--")]
OUT = os.path.abspath(args[0] if args else ".")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# 所有角色部件放进一个集合，并挂在同一个空物体下，导出后在引擎里就是一个整体
char_col = bpy.data.collections.new("Character")
scene.collection.children.link(char_col)
root = bpy.data.objects.new("StrawberryGirl", None)
char_col.objects.link(root)


# ---------------------------------------------------------------------------
# 材质
# ---------------------------------------------------------------------------
def srgb(hex_color):
    """把 #rrggbb 转成 Blender 内部使用的线性颜色。"""
    h = hex_color.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, 1.0)


def make_image(name, pixels):
    """numpy 数组（高, 宽, 4，0~1）存成 PNG 贴图，导出 glb 时会一起打包。"""
    h, w, _ = pixels.shape
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels.foreach_set(pixels.astype(np.float32).ravel())
    os.makedirs(os.path.join(OUT, "textures"), exist_ok=True)
    img.filepath_raw = os.path.join(OUT, "textures", f"{name}.png")
    img.file_format = "PNG"
    img.save()
    img.pack()
    return img


def material(name, hex_color, rough=0.7, image=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = srgb(hex_color)
    bsdf.inputs["Roughness"].default_value = rough
    if image is not None:
        tex = m.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        m.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def hex_rgb(hex_color):
    h = hex_color.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [1.0])


def sweater_texture():
    """芥末黄底 + 两组奶油色折线纹（毛衣和裤子共用）。v 从下往上。"""
    size = 512
    u = (np.arange(size) + 0.5) / size
    v = (np.arange(size) + 0.5) / size
    uu, vv = np.meshgrid(u, v)
    tri = 2 * np.abs(uu * 10 - np.floor(uu * 10 + 0.5))  # 三角波，一圈 10 个折
    mask = np.zeros_like(uu, dtype=bool)
    for v0 in (0.26, 0.72):
        for off in (0.0, 0.05):
            zc = v0 + off + 0.035 * (tri * 2 - 1)
            mask |= np.abs(vv - zc) < 0.011
    px = np.tile(hex_rgb("#d9a53c"), (size, size, 1))
    px[mask] = hex_rgb("#f4e7c6")
    return make_image("tex_sweater", px)


def gingham_texture():
    """野餐布的红白格子。"""
    size = 128
    idx = np.arange(size) // 16 % 2
    a, b = np.meshgrid(idx, idx)
    red, white = hex_rgb("#d8454a"), hex_rgb("#f6ece2")
    pink = (red + white) / 2
    px = np.where((a + b)[..., None] == 2, red, np.where((a + b)[..., None] == 1, pink, white))
    return make_image("tex_gingham", px)


def wicker_texture():
    """竹篮的交错编织纹。"""
    size = 256
    y, x = np.mgrid[0:size, 0:size]
    row = y // 16
    cell = (x + (row % 2) * 16) // 32 % 2
    light, dark = hex_rgb("#c89556"), hex_rgb("#9a6a34")
    px = np.where(cell[..., None] == 1, light, dark).astype(float)
    edge = (y % 16 < 2)[..., None]
    px = np.where(edge, dark * 0.8, px)
    px[..., 3] = 1
    return make_image("tex_wicker", px)


M = {
    "skin": material("Skin", "#e2a982", 0.75),
    "hair": material("Hair", "#231a17", 0.45),
    "eye": material("Eye", "#2a1a12", 0.25),
    "white": material("White", "#ffffff", 0.3),
    "blush": material("Blush", "#f0928f", 0.8),
    "mouth": material("Mouth", "#8a3a33", 0.6),
    "sweater": material("Sweater", "#d9a53c", 0.9, sweater_texture()),
    "cream": material("Cream", "#f4e7c6", 0.9),
    "bear": material("Bear", "#6b4428", 0.85),
    "bear_snout": material("BearSnout", "#c99a6b", 0.85),
    "dark": material("Dark", "#1c1512", 0.4),
    "sock": material("Sock", "#6d4a2e", 0.9),
    "shoe": material("Shoe", "#a9d3ee", 0.6),
    "sole": material("Sole", "#f6f3ee", 0.7),
    "hp_blue": material("HeadphoneBlue", "#86bdea", 0.35),
    "hp_pink": material("HeadphonePink", "#f4a7c3", 0.5),
    "straw": material("Strawberry", "#e0312f", 0.3),
    "seed": material("Seed", "#f3d36b", 0.5),
    "leaf": material("Leaf", "#4f9a3a", 0.7),
    "wicker": material("Wicker", "#b88a4e", 0.9, wicker_texture()),
    "wicker_dark": material("WickerDark", "#8d6232", 0.9),
    "gingham": material("Gingham", "#d8454a", 0.9, gingham_texture()),
}


# ---------------------------------------------------------------------------
# 造型工具函数
# ---------------------------------------------------------------------------
def finish(obj, mat, name, smooth=True):
    """统一收尾：命名、光滑着色、上材质、放进角色集合并挂到根节点下。"""
    obj.name = name
    if obj.type == "MESH":
        if smooth:
            for p in obj.data.polygons:
                p.use_smooth = True
        if mat is not None:
            obj.data.materials.clear()
            obj.data.materials.append(mat)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    char_col.objects.link(obj)
    obj.parent = root
    return obj


def active():
    return bpy.context.view_layer.objects.active


def ellipsoid(name, mat, loc, scale, rot=None, seg=32, rings=16):
    """最常用的积木：压扁/拉长的球。"""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=1, location=loc)
    o = active()
    o.scale = scale
    if rot is not None:
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = rot
    return finish(o, mat, name)


def capsule(name, mat, p, q, r):
    """两点之间的胶囊体（手臂、腿）。UV 的 v 沿长度方向铺开，折线纹才会绕成一圈圈。"""
    p, q = Vector(p), Vector(q)
    half = (q - p).length / 2
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=r, location=(p + q) / 2)
    o = active()
    me = o.data
    for v in me.vertices:
        if v.co.z > 1e-6:
            v.co.z += half
        elif v.co.z < -1e-6:
            v.co.z -= half
    uv = me.uv_layers.active.data
    total = 2 * (half + r)
    for loop in me.loops:
        uv[loop.index].uv.y = (me.vertices[loop.vertex_index].co.z + half + r) / total
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference((q - p).normalized())
    return finish(o, mat, name)


def torus(name, mat, loc, major, minor, axis=(0, 0, 1), half=False):
    """圆环；axis 是圆环的朝向（法线），half=True 只保留上半圈（耳机头梁、篮子提手）。"""
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=48, minor_segments=12)
    o = active()
    if half:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < -1e-4], context="VERTS")
        bm.to_mesh(o.data)
        bm.free()
    o.location = loc
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized())
    return finish(o, mat, name)


def tube(name, mat, pts, radii, bevel):
    """沿一串点生成平滑的管子（马尾、刘海、嘴巴），radii 控制每处粗细。"""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    cu.resolution_u = 12
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for pt, p, r in zip(sp.points, pts, radii):
        pt.co = (*p, 1.0)
        pt.radius = r
    sp.order_u = min(4, len(pts))
    sp.use_endpoint_u = True
    o = bpy.data.objects.new(name, cu)
    scene.collection.objects.link(o)
    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.convert(target="MESH")
    return finish(active(), mat, name)


def facing(normal, spin=0.0):
    """让压扁物体的薄面（本地 -Y）贴着表面朝外，spin 是绕法线的旋转。"""
    q = Vector((0, -1, 0)).rotation_difference(Vector(normal).normalized())
    return Quaternion(Vector(normal).normalized(), spin) @ q


# ---------------------------------------------------------------------------
# 头部：Q 版大头，身体只有头的一半高
# ---------------------------------------------------------------------------
HC = Vector((0, 0, 0.72))            # 头部中心
HS = Vector((0.231, 0.209, 0.22))    # 头部三个方向的半径（略宽、略扁）


def head_point(x, z, lift=0.0, scale=1.0):
    """给定正面的 x、z，求头部椭球表面上的点和法线（面朝 -Y 的半球）。"""
    nx, nz = x / (HS.x * scale), (z - HC.z) / (HS.z * scale)
    ny = -math.sqrt(max(0.0, 1 - nx * nx - nz * nz))
    p = HC + Vector((nx * HS.x * scale, ny * HS.y * scale, nz * HS.z * scale))
    n = Vector((nx / HS.x, ny / HS.y, nz / HS.z)).normalized()
    return p + n * lift, n


ellipsoid("Head", M["skin"], HC, HS, seg=48, rings=24)

# 眼睛：大而圆的深棕色，加两颗高光
for s in (-1, 1):
    p, n = head_point(0.085 * s, 0.675, lift=0.004)
    ellipsoid(f"Eye.{'R' if s < 0 else 'L'}", M["eye"], p, (0.034, 0.014, 0.043), facing(n))
    ellipsoid(f"EyeShine.{'R' if s < 0 else 'L'}", M["white"],
              p + n * 0.012 + Vector((-0.011, 0, 0.014)), (0.011, 0.005, 0.011), facing(n))
    ellipsoid(f"EyeShine2.{'R' if s < 0 else 'L'}", M["white"],
              p + n * 0.012 + Vector((0.01, 0, -0.012)), (0.005, 0.003, 0.005), facing(n))
    bp, bn = head_point(0.085 * s, 0.752, lift=0.002)
    ellipsoid(f"Brow.{'R' if s < 0 else 'L'}", M["hair"], bp, (0.02, 0.004, 0.0055),
              facing(bn, spin=-0.12 * s))
    cp, cn = head_point(0.135 * s, 0.635, lift=0.0015)
    ellipsoid(f"Blush.{'R' if s < 0 else 'L'}", M["blush"], cp, (0.03, 0.005, 0.017), facing(cn))

p, n = head_point(0.0, 0.652, lift=0.002)
ellipsoid("Nose", M["skin"], p, (0.012, 0.008, 0.009), facing(n))

# 嘴巴：一道浅浅的微笑弧线
mouth_pts, mouth_r = [], []
for i in range(7):
    t = -1 + 2 * i / 6
    mp, _ = head_point(0.024 * t, 0.607 + 0.008 * t * t, lift=0.001)
    mouth_pts.append(mp)
    mouth_r.append(1.0 - 0.35 * abs(t))
tube("Mouth", M["mouth"], mouth_pts, mouth_r, 0.0038)

# ---------------------------------------------------------------------------
# 头发：比头大一圈的球，挖掉脸部；再加斜刘海和高马尾
# ---------------------------------------------------------------------------
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1)
hair = active()
bm = bmesh.new()
bm.from_mesh(hair.data)
cut = []
for v in bm.verts:
    x, y, z = v.co
    hairline = 0.55 - 1.3 * x * x          # 中分发际线：中间高，两鬓低
    if y < -0.25 and z < hairline:         # 脸
        cut.append(v)
    elif z < -0.55 and y < 0.3:            # 下巴和脖子两侧
        cut.append(v)
bmesh.ops.delete(bm, geom=cut, context="VERTS")
# 斜着切网格会留下锯齿：把边界点反复向相邻边界点的平均位置靠拢，再投影回球面
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
hair.location = HC
hair.scale = HS * 1.07
hair.modifiers.new("Thickness", "SOLIDIFY").thickness = 0.012
finish(hair, M["hair"], "HairCap")

for s in (-1, 1):  # 从分缝处沿发际线向两侧梳下来的细刘海
    pts = []
    for nx, nz in ((0.04, 0.72), (0.22, 0.62), (0.42, 0.44), (0.6, 0.2), (0.7, -0.08)):
        ny = -math.sqrt(max(0.0, 1 - nx * nx - nz * nz))
        pts.append(HC + Vector((nx * s * HS.x, ny * HS.y, nz * HS.z)) * 1.0
                   + Vector((nx * s * HS.x, ny * HS.y, nz * HS.z)) * 0.075)
    tube(f"Bangs.{'R' if s < 0 else 'L'}", M["hair"], pts, (0.6, 1.0, 1.0, 0.8, 0.3), 0.024)

ponytail = [(0.037, 0.123, 0.905), (0.04, 0.205, 0.93), (0.046, 0.29, 0.865),
            (0.05, 0.33, 0.745), (0.05, 0.315, 0.625), (0.045, 0.28, 0.515)]
tube("Ponytail", M["hair"], ponytail, (0.8, 1.1, 1.0, 0.85, 0.6, 0.2), 0.058)
torus("HairTie", M["hp_pink"], ponytail[0], 0.04, 0.014,
      axis=Vector(ponytail[1]) - Vector(ponytail[0]))

# 粉色发夹，别在角色右侧（画面左侧）
d = Vector((-0.5, -0.45, 0.74)).normalized()
clip_p = HC + Vector((d.x * HS.x, d.y * HS.y, d.z * HS.z)) * 1.07
clip_n = Vector((d.x / HS.x, d.y / HS.y, d.z / HS.z)).normalized()
ellipsoid("HairClip", M["hp_pink"], clip_p + clip_n * 0.01, (0.04, 0.012, 0.014), facing(clip_n, 0.5))

# ---------------------------------------------------------------------------
# 耳机：半圈头梁 + 两个圆润的耳罩
# ---------------------------------------------------------------------------
torus("Headband", M["hp_blue"], (0, 0, 0.70), 0.275, 0.02, axis=(0, -1, 0), half=True)
for s in (-1, 1):
    side = "R" if s < 0 else "L"
    ellipsoid(f"EarCup.{side}", M["hp_blue"], (0.283 * s, 0, 0.70), (0.032, 0.072, 0.072))
    torus(f"EarCushion.{side}", M["hp_pink"], (0.255 * s, 0, 0.70), 0.052, 0.018, axis=(1, 0, 0))
    ellipsoid(f"EarDot.{side}", M["hp_pink"], (0.312 * s, 0, 0.70), (0.006, 0.038, 0.038))

# ---------------------------------------------------------------------------
# 身体：毛衣 + 胸前小熊
# ---------------------------------------------------------------------------
ellipsoid("Sweater", M["sweater"], (0, 0, 0.36), (0.145, 0.118, 0.16))
ellipsoid("Hips", M["sweater"], (0, 0, 0.245), (0.112, 0.09, 0.07))

ellipsoid("Bear.Head", M["bear"], (0, -0.113, 0.36), (0.05, 0.018, 0.042))
for s in (-1, 1):
    ellipsoid(f"Bear.Ear{s}", M["bear"], (0.04 * s, -0.104, 0.4), (0.018, 0.01, 0.018))
    ellipsoid(f"Bear.Eye{s}", M["dark"], (0.018 * s, -0.13, 0.372), (0.006, 0.004, 0.006))
ellipsoid("Bear.Snout", M["bear_snout"], (0, -0.13, 0.35), (0.02, 0.008, 0.014))
ellipsoid("Bear.Nose", M["dark"], (0, -0.139, 0.356), (0.006, 0.004, 0.005))

# ---------------------------------------------------------------------------
# 腿和鞋
# ---------------------------------------------------------------------------
for s in (-1, 1):
    side = "R" if s < 0 else "L"
    capsule(f"Leg.{side}", M["sweater"], (0.065 * s, 0, 0.22), (0.07 * s, 0, 0.1), 0.052)
    ellipsoid(f"Sock.{side}", M["sock"], (0.07 * s, 0, 0.088), (0.05, 0.05, 0.022))
    ellipsoid(f"Shoe.{side}", M["shoe"], (0.07 * s, -0.02, 0.045), (0.055, 0.08, 0.04))
    ellipsoid(f"Sole.{side}", M["sole"], (0.07 * s, -0.02, 0.014), (0.058, 0.083, 0.014))


# ---------------------------------------------------------------------------
# 草莓（手里一颗，篮子里几颗）
# ---------------------------------------------------------------------------
def strawberry(name, loc, size, tip=(0, 0, -1), seeds=True):
    """球 -> 下半部收尖成草莓形，加籽、五片萼叶和小梗，合并成一个物体。"""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=14, radius=1)
    body = active()
    for v in body.data.vertices:
        x, y, z = v.co
        f = 1 + 0.5 * z if z < 0 else 1 - 0.15 * z * z
        v.co = (x * f, y * f, z * 1.15 if z < 0 else z * 0.9)
    for p in body.data.polygons:
        p.use_smooth = True
    body.data.materials.append(M["straw"])
    parts = [body]

    if seeds:
        bm = bmesh.new()
        for i, v in enumerate(body.data.vertices):
            if i % 2 == 0 and -1.0 < v.co.z < 0.55:
                bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.055,
                                           matrix=Matrix.Translation(v.co * 1.01))
        me = bpy.data.meshes.new(name + "Seeds")
        bm.to_mesh(me)
        bm.free()
        so = bpy.data.objects.new(name + "Seeds", me)
        scene.collection.objects.link(so)
        me.materials.append(M["seed"])
        parts.append(so)

    for k in range(5):
        a = k / 5 * math.tau
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=1,
                                             location=(math.cos(a) * 0.32, math.sin(a) * 0.32, 0.9))
        leaf = active()
        leaf.scale = (0.16, 0.42, 0.05)
        leaf.rotation_euler = Euler((-0.35, 0, a - math.pi / 2))
        leaf.data.materials.append(M["leaf"])
        parts.append(leaf)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=1, location=(0, 0, 1.02))
    stem = active()
    stem.scale = (0.06, 0.06, 0.16)
    stem.data.materials.append(M["leaf"])
    parts.append(stem)

    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    for ob in parts:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.location = loc
    body.scale = (size, size, size)
    body.rotation_mode = "QUATERNION"
    body.rotation_quaternion = Vector((0, 0, -1)).rotation_difference(Vector(tip).normalized())
    return finish(body, None, name, smooth=False)


# ---------------------------------------------------------------------------
# 手臂：右手把草莓送到嘴边，左手拎着小竹篮
# ---------------------------------------------------------------------------
def arm(side, shoulder, hand):
    shoulder, hand = Vector(shoulder), Vector(hand)
    d = (shoulder - hand).normalized()
    wrist = hand + d * 0.035
    capsule(f"Sleeve.{side}", M["sweater"], shoulder, wrist, 0.042)
    torus(f"Cuff.{side}", M["cream"], wrist, 0.036, 0.012, axis=-d)
    ellipsoid(f"Hand.{side}", M["skin"], hand, (0.038, 0.038, 0.038))


arm("R", (-0.12, 0, 0.44), (-0.06, -0.225, 0.54))
strawberry("Strawberry.Hand", (-0.045, -0.255, 0.585), 0.038, tip=(0.1, -0.4, -1))

arm("L", (0.12, 0, 0.44), (0.2, -0.01, 0.27))
BASKET = Vector((0.21, -0.01, 0.15))
bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.06, radius2=0.075, depth=0.075,
                                end_fill_type="NOTHING", location=BASKET)
basket = active()
basket.modifiers.new("Thickness", "SOLIDIFY").thickness = 0.006
finish(basket, M["wicker"], "Basket")
ellipsoid("BasketFill", M["wicker_dark"], BASKET + Vector((0, 0, 0.025)), (0.068, 0.068, 0.01))
torus("BasketRim", M["wicker_dark"], BASKET + Vector((0, 0, 0.0375)), 0.075, 0.009)
torus("BasketHandle", M["wicker_dark"], BASKET + Vector((0, 0, 0.0375)), 0.07, 0.007,
      axis=(0, -1, 0), half=True)
for i, (dx, dy, rz) in enumerate(((-0.03, -0.02, 0.3), (0.0, 0.025, -0.4), (0.028, -0.018, 0.9),
                                  (-0.022, 0.028, 1.6), (0.012, 0.0, 2.2))):
    strawberry(f"Strawberry.Basket{i}", BASKET + Vector((dx, dy, 0.05)), 0.021,
               tip=(math.sin(rz) * 0.5, math.cos(rz) * 0.5, -1), seeds=True)
ellipsoid("Gingham", M["gingham"], BASKET + Vector((0.035, -0.035, 0.048)), (0.045, 0.035, 0.009),
          Euler((0.2, -0.45, 0.6)).to_quaternion())

# ---------------------------------------------------------------------------
# 保存与导出
# ---------------------------------------------------------------------------
glb_path = os.path.join(OUT, "strawberry_girl.glb")
for ob in bpy.context.selected_objects:
    ob.select_set(False)
for ob in char_col.objects:
    ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB", use_selection=True,
                          export_apply=True)
print("导出模型:", glb_path)

# ---------------------------------------------------------------------------
# 预览渲染：草地 + 天空色环境光 + 暖色阳光
# ---------------------------------------------------------------------------
bpy.ops.mesh.primitive_circle_add(vertices=64, radius=4, fill_type="NGON")
ground = active()
ground.name = "Ground"
ground.data.materials.append(material("Grass", "#86b85a", 1.0))

world = bpy.data.worlds.new("Sky")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = srgb("#b4daf7")
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.1
scene.world = world

sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 3.2
sun.data.angle = math.radians(12)
sun.data.color = (1.0, 0.95, 0.86)
sun.rotation_euler = Euler((math.radians(50), 0, math.radians(-35)))
scene.collection.objects.link(sun)

target = bpy.data.objects.new("CamTarget", None)
target.location = (0, 0, 0.5)
scene.collection.objects.link(target)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 60
scene.collection.objects.link(cam)
track = cam.constraints.new("TRACK_TO")
track.target = target
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis = "UP_Y"
scene.camera = cam

scene.render.resolution_x, scene.render.resolution_y = 900, 1200
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
except TypeError:
    pass

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "strawberry_girl.blend"))
print("保存工程:", os.path.join(OUT, "strawberry_girl.blend"))

if "--no-render" not in flags:
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    for name, azimuth in (("preview_front", 25), ("preview_back", 150)):
        a = math.radians(azimuth)
        cam.location = (2.3 * math.sin(a), -2.3 * math.cos(a), 0.95)
        scene.render.filepath = os.path.join(OUT, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print("渲染:", scene.render.filepath)
