"""公共工具：颜色、贴图、材质，以及用基础几何体拼角色/道具的「积木」函数。

所有造型都由这些积木组成：
    ellipsoid  压扁/拉长的球（头、身体、眼睛、耳朵……几乎一切）
    capsule    两点之间的胶囊（手臂、腿）
    torus      圆环 / 半圆环（发绳、耳机头梁、篮子提手）
    tube       沿一串点的平滑管子（马尾、嘴巴）
    box        带圆角的方块（木板、木箱）
    strawberry 草莓
"""
import math
import os

import bpy  # 必须先于 bmesh / mathutils 导入（pip 版 bpy 由它注册这些模块）
import bmesh
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

TEX_DIR = None  # 贴图输出目录，由 build.py 设置


# ---------------------------------------------------------------------------
# 颜色与贴图
# ---------------------------------------------------------------------------
def srgb(hex_color):
    """#rrggbb -> Blender 内部使用的线性颜色 (r, g, b, a)。"""
    h = hex_color.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, 1.0)


def rgba(hex_color):
    """#rrggbb -> numpy 贴图用的 sRGB 颜色（0~1）。"""
    h = hex_color.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [1.0])


def make_image(name, pixels):
    """numpy 数组（高, 宽, 4）存成 PNG 并打包进工程，导出 glb 时会带上。"""
    h, w, _ = pixels.shape
    img = bpy.data.images.new(name, w, h, alpha=True)
    img.pixels.foreach_set(np.clip(pixels, 0, 1).astype(np.float32).ravel())
    os.makedirs(TEX_DIR, exist_ok=True)
    img.filepath_raw = os.path.join(TEX_DIR, f"{name}.png")
    img.file_format = "PNG"
    img.save()
    img.pack()
    return img


def uv_grid(size):
    u = (np.arange(size) + 0.5) / size
    return np.meshgrid(u, u)  # (uu, vv)，v 从下往上


def stamp_ellipses(px, count, colors, rx, ry, seed):
    """在贴图上随机盖椭圆（树叶、草纹），左右上下无缝平铺。"""
    rng = np.random.default_rng(seed)
    size = px.shape[0]
    yy, xx = np.mgrid[0:size, 0:size]
    for _ in range(count):
        cx, cy = rng.uniform(0, size, 2)
        a = rng.uniform(0, math.pi)
        r1, r2 = rng.uniform(*rx), rng.uniform(*ry)
        col = colors[rng.integers(len(colors))]
        for ox in (-size, 0, size):
            for oy in (-size, 0, size):
                dx, dy = xx - cx - ox, yy - cy - oy
                u = dx * math.cos(a) + dy * math.sin(a)
                v = -dx * math.sin(a) + dy * math.cos(a)
                px[(u / r1) ** 2 + (v / r2) ** 2 < 1] = col
    return px


def fuzz(px, amount, seed):
    """轻微的颜色噪点，模拟动森里毛线、布料那种柔软的颗粒感。"""
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amount, px.shape[:2])[..., None]
    px[..., :3] = px[..., :3] * (1 + n)
    return px


# ---------------------------------------------------------------------------
# 材质
# ---------------------------------------------------------------------------
_MATS = {}


def mat(name, hex_color, rough=0.8, image=None, sheen=0.0, metal=0.0, coat=0.0):
    """Principled BSDF 材质。动森的质感：粗糙度高、布料带一点绒光（sheen）。"""
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = srgb(hex_color)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if sheen:
        b.inputs["Sheen Weight"].default_value = sheen
        b.inputs["Sheen Roughness"].default_value = 0.6
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.25
    if image is not None:
        tex = m.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        m.node_tree.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    _MATS[name] = m
    return m


# ---------------------------------------------------------------------------
# 组装工具
# ---------------------------------------------------------------------------
def active():
    return bpy.context.view_layer.objects.active


def select_only(objs):
    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def facing(normal, spin=0.0):
    """旋转：让压扁物体的薄面（本地 -Y）贴着表面朝外，spin 是绕法线再转的角度。"""
    n = Vector(normal).normalized()
    return Quaternion(n, spin) @ Vector((0, -1, 0)).rotation_difference(n)


def along(direction):
    """旋转：让本地 +Z 指向 direction。"""
    return Vector((0, 0, 1)).rotation_difference(Vector(direction).normalized())


class Head:
    """椭球形的头。surface() 求正面某个 (x, z) 在表面上的点和法线，五官都靠它贴上去。"""

    def __init__(self, center, radii):
        self.c = Vector(center)
        self.r = Vector(radii)

    def surface(self, x, z, lift=0.0, grow=1.0, back=False):
        r = self.r * grow
        nx, nz = x / r.x, (z - self.c.z) / r.z
        ny = math.sqrt(max(0.0, 1 - nx * nx - nz * nz)) * (1 if back else -1)
        p = self.c + Vector((nx * r.x, ny * r.y, nz * r.z))
        n = Vector((nx / r.x, ny / r.y, nz / r.z)).normalized()
        return p + n * lift, n

    def dir_point(self, d, grow=1.0, lift=0.0):
        """沿方向 d（单位球上的方向）求表面点和法线，用来放头顶、脑后的东西。"""
        d = Vector(d).normalized()
        r = self.r * grow
        p = self.c + Vector((d.x * r.x, d.y * r.y, d.z * r.z))
        n = Vector((d.x / r.x, d.y / r.y, d.z / r.z)).normalized()
        return p + n * lift, n


class Part:
    """一个角色或一件道具：自己的集合 + 一个根节点，部件都挂在根节点下。
    先在原点、面朝 -Y 搭好，最后用 place() 整体摆到场景里。"""

    def __init__(self, name, parent_col):
        self.name = name
        self.col = bpy.data.collections.new(name)
        parent_col.children.link(self.col)
        self.root = bpy.data.objects.new(name, None)
        self.col.objects.link(self.root)

    # -- 收尾：命名、光滑、上材质、放进集合、挂到根节点 --
    def finish(self, obj, material, name, smooth=True):
        obj.name = f"{self.name}.{name}"
        if obj.type == "MESH":
            for p in obj.data.polygons:
                p.use_smooth = smooth
            if material is not None:
                obj.data.materials.clear()
                obj.data.materials.append(material)
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        self.col.objects.link(obj)
        obj.parent = self.root
        return obj

    def place(self, loc, turn_deg=0.0):
        self.root.location = loc
        self.root.rotation_euler = (0, 0, math.radians(turn_deg))

    # -- 积木 --
    def ellipsoid(self, name, material, loc, scale, rot=None, seg=32, rings=16):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=1, location=loc)
        o = active()
        o.scale = scale
        if rot is not None:
            o.rotation_mode = "QUATERNION"
            o.rotation_quaternion = rot if isinstance(rot, Quaternion) else Euler(rot).to_quaternion()
        return self.finish(o, material, name)

    def capsule(self, name, material, p, q, r, r_end=None):
        """胶囊体；r_end 给了就从 r 渐变到 r_end（上粗下细的手臂）。"""
        p, q = Vector(p), Vector(q)
        half = (q - p).length / 2
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=1, location=(p + q) / 2)
        o = active()
        me = o.data
        r_end = r if r_end is None else r_end
        for v in me.vertices:
            k = r_end if v.co.z > 0 else r
            if abs(v.co.z) < 1e-6:
                k = (r + r_end) / 2
            v.co.x *= k
            v.co.y *= k
            z = v.co.z * k
            v.co.z = z + half if v.co.z > 1e-6 else (z - half if v.co.z < -1e-6 else 0)
        uv = me.uv_layers.active.data
        lo = -half - r
        total = 2 * half + r + r_end
        for loop in me.loops:
            uv[loop.index].uv.y = (me.vertices[loop.vertex_index].co.z - lo) / total
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = along(q - p)
        return self.finish(o, material, name)

    def torus(self, name, material, loc, major, minor, axis=(0, 0, 1), half=False, seg=48):
        bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                         major_segments=seg, minor_segments=12)
        o = active()
        if half:  # 只留 +Y 半圈，再由 axis 决定朝向
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < -1e-4], context="VERTS")
            bm.to_mesh(o.data)
            bm.free()
        o.location = loc
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = along(axis)
        return self.finish(o, material, name)

    def tube(self, name, material, pts, radii, bevel):
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
        bpy.context.scene.collection.objects.link(o)
        select_only([o])
        bpy.ops.object.convert(target="MESH")
        return self.finish(active(), material, name)

    def box(self, name, material, loc, size, bevel=0.01, rot=None):
        """圆角方块。直接改顶点坐标来缩放，倒角才不会被拉歪。"""
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        o = active()
        for v in o.data.vertices:
            v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        if bevel:
            mod = o.modifiers.new("Round", "BEVEL")
            mod.width = bevel
            mod.segments = 3
        if rot is not None:
            o.rotation_euler = rot
        return self.finish(o, material, name, smooth=False)

    def cone(self, name, material, loc, r1, r2, depth, rot=None, verts=24, cap=True):
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=depth,
                                        end_fill_type="NGON" if cap else "NOTHING", location=loc)
        o = active()
        if rot is not None:
            o.rotation_euler = rot
        return self.finish(o, material, name, smooth=not cap)

    def text(self, name, material, body, loc, size, rot=(math.pi / 2, 0, 0), depth=0.004):
        """立体中文字（木牌上用），转成网格方便导出。"""
        cu = bpy.data.curves.new(name, "FONT")
        cu.body = body
        cu.size = size
        cu.extrude = depth
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        font_path = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
        if os.path.exists(font_path):
            cu.font = bpy.data.fonts.load(font_path)
        o = bpy.data.objects.new(name, cu)
        bpy.context.scene.collection.objects.link(o)
        o.location = loc
        o.rotation_euler = rot
        select_only([o])
        bpy.ops.object.convert(target="MESH")
        return self.finish(active(), material, name, smooth=False)

    def strawberry(self, name, loc, size, tip=(0, 0, -1), seeds=True, ripe=True):
        """球 -> 下半部收尖成草莓形，加籽、五片萼叶和小梗，合成一个物体。"""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=1)
        body = active()
        for v in body.data.vertices:
            x, y, z = v.co
            f = 1 + 0.5 * z if z < 0 else 1 - 0.15 * z * z
            v.co = (x * f, y * f, z * 1.15 if z < 0 else z * 0.9)
        for p in body.data.polygons:
            p.use_smooth = True
        body.data.materials.append(STRAW["red"] if ripe else STRAW["unripe"])
        parts = [body]

        if seeds:
            bm = bmesh.new()
            for i, v in enumerate(body.data.vertices):
                if i % 2 == 0 and -1.0 < v.co.z < 0.55:
                    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.06,
                                               matrix=Matrix.Translation(v.co * 1.01))
            me = bpy.data.meshes.new(name + "Seeds")
            bm.to_mesh(me)
            bm.free()
            so = bpy.data.objects.new(name + "Seeds", me)
            bpy.context.scene.collection.objects.link(so)
            me.materials.append(STRAW["seed"])
            parts.append(so)

        for k in range(5):
            a = k / 5 * math.tau
            bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=1,
                                                 location=(math.cos(a) * 0.32, math.sin(a) * 0.32, 0.9))
            leaf = active()
            leaf.scale = (0.16, 0.42, 0.06)
            leaf.rotation_euler = Euler((-0.35, 0, a - math.pi / 2))
            leaf.data.materials.append(STRAW["leaf"])
            parts.append(leaf)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6, radius=1, location=(0, 0, 1.02))
        stem = active()
        stem.scale = (0.06, 0.06, 0.18)
        stem.data.materials.append(STRAW["leaf"])
        parts.append(stem)

        select_only([body] + parts[1:])
        bpy.ops.object.join()
        body.location = loc
        body.scale = (size, size, size)
        body.rotation_mode = "QUATERNION"
        body.rotation_quaternion = Vector((0, 0, -1)).rotation_difference(Vector(tip).normalized())
        return self.finish(body, None, name, smooth=False)


STRAW = {}


def init_common_materials():
    STRAW["red"] = mat("Strawberry", "#e3342f", 0.3, coat=0.4)
    STRAW["unripe"] = mat("StrawberryUnripe", "#e9eec2", 0.4)
    STRAW["seed"] = mat("Seed", "#f5d66d", 0.5)
    STRAW["leaf"] = mat("StrawLeaf", "#4b9a3c", 0.7)
