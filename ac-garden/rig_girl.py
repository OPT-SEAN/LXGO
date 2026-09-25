"""给 AI 生成的女孩模型（单个网格）自动绑骨骼、做动画，导出带动画的 glb。

    python rig_girl.py <输入.glb> <输出.glb> [--turn 度数] [--preview 目录]

流程：
1. 导入 -> 合并成一个网格 -> 缩放到身高 1、脚底落在地面、居中；--turn 用来修正朝向（要求面朝 -Y）
2. 从顶点分布自动找关键位置：脖子（头和身体之间最细处）、胯（两腿分开处）、肩、手、脚
3. 按比例搭一副简单的人形骨架
4. 蒙皮：每个顶点按到骨头的距离分配权重，再按部位限制（头只跟头骨、左手只跟左臂……）；
   AI 生成的网格常有破洞和自交，Blender 自带的自动权重容易失败，这种办法更稳
5. 做四段动画：Idle 待机、Walk 走路、Pick 蹲下采摘、Eat 偷吃，导出 glb
"""
import math
import os
import sys

import bpy  # 必须先于 mathutils 导入
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]


def opt(name, default=None):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


TURN = float(opt("--turn", "0"))
PREVIEW = opt("--preview")
SRC, DST = argv[0], argv[1]
FPS = 30


# ---------------------------------------------------------------------------
# 1. 导入并规范化
# ---------------------------------------------------------------------------
def load_mesh(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    # 去掉父级（导入时可能挂在空物体下），把变换应用到顶点上
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in list(bpy.context.scene.objects):
        if o is not obj:
            bpy.data.objects.remove(o, do_unlink=True)

    co = np.array([v.co[:] for v in obj.data.vertices])
    if TURN:
        a = math.radians(TURN)
        rot = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
        co = co @ rot.T
    lo, hi = co.min(0), co.max(0)
    height = hi[2] - lo[2]
    co = (co - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])) / height
    obj.data.vertices.foreach_set("co", co.astype(np.float32).ravel())
    obj.data.update()
    obj.name = "Girl"
    return obj, co


# ---------------------------------------------------------------------------
# 2. 找关键位置
# ---------------------------------------------------------------------------
def landmarks(co):
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    zs = np.linspace(0, 1, 101)

    def width_at(z0, band=0.012, core=None):
        m = np.abs(z - z0) < band
        if core is not None:
            m &= np.abs(x) < core
        return (x[m].max() - x[m].min()) if m.sum() > 5 else 0.0

    # 脖子：0.35~0.75 高度之间，整个身体横向最窄的地方（头和耳机在上面、肩膀和手臂在下面都更宽）
    cand = [(width_at(h), h) for h in zs if 0.35 <= h <= 0.75]
    neck = min(c for c in cand if c[0] > 0)[1]

    # 胯：0.1~0.45 高度里，从上往下第一个 x≈0 附近没有顶点的高度（两腿分开处）
    crotch = 0.3
    for h in np.linspace(0.45, 0.08, 75):
        m = (np.abs(z - h) < 0.01) & (np.abs(x) < 0.012)
        if m.sum() == 0:
            crotch = h
            break

    # 肩宽：脖子下方一点的躯干半宽
    sh_z = neck - 0.04
    body = (np.abs(z - (neck - 0.1)) < 0.02) & (np.abs(x) < 0.2)
    torso_half = np.percentile(np.abs(x[body]), 90) if body.sum() > 10 else 0.1

    # 手：在胯和脖子之间、离中心最远的点群（左右各一），取最外侧 3% 顶点的平均
    hands = {}
    for s in (-1, 1):
        m = (z > crotch - 0.08) & (z < neck - 0.03) & (x * s > torso_half * 0.9)
        if m.sum() < 20:
            hands[s] = np.array([s * (torso_half + 0.12), 0.0, crotch + 0.02])
            continue
        xs = x[m] * s
        far = m.copy()
        far[m] = xs >= np.percentile(xs, 97)
        hands[s] = co[far].mean(0)

    # 腿：胯以下左右两侧的中心
    legs = {}
    for s in (-1, 1):
        m = (z < crotch) & (z > 0.05) & (x * s > 0) & (np.abs(x) < torso_half)
        legs[s] = abs(np.median(x[m])) if m.sum() > 10 else 0.05
    head_top = z.max()
    front = np.percentile(y[z < 0.05], 5) if (z < 0.05).sum() else -0.05
    L = dict(neck=neck, crotch=crotch, sh_z=sh_z, torso_half=torso_half,
             hands=hands, legs=legs, head_top=head_top, toe_y=front)
    print("关键位置:", {k: (np.round(v, 3).tolist() if isinstance(v, np.ndarray) else
                           ({kk: np.round(vv, 3).tolist() for kk, vv in v.items()} if isinstance(v, dict) else round(float(v), 3)))
                       for k, v in L.items()})
    return L


# ---------------------------------------------------------------------------
# 3. 骨架
# ---------------------------------------------------------------------------
def build_armature(L):
    arm_data = bpy.data.armatures.new("Rig")
    rig = bpy.data.objects.new("Rig", arm_data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones

    def bone(name, head, tail, parent=None, connect=False):
        b = eb.new(name)
        b.head, b.tail = Vector(head), Vector(tail)
        b.roll = 0
        if parent:
            b.parent = eb[parent]
            b.use_connect = connect
        return b

    c, n = L["crotch"], L["neck"]
    hips_z = c + 0.03
    bone("Hips", (0, 0, hips_z), (0, 0, hips_z + (n - hips_z) * 0.35))
    bone("Spine", (0, 0, hips_z + (n - hips_z) * 0.35), (0, 0, n - 0.02), "Hips", True)
    bone("Neck", (0, 0, n - 0.02), (0, 0, n + 0.03), "Spine", True)
    bone("Head", (0, 0, n + 0.03), (0, 0, L["head_top"]), "Neck", True)
    for s, side in ((-1, "R"), (1, "L")):
        sh = Vector((s * L["torso_half"] * 0.85, 0, L["sh_z"]))
        hand = Vector(L["hands"][s])
        wrist = sh + (hand - sh) * 0.85
        elbow = sh + (wrist - sh) * 0.5 + Vector((0, 0.01, 0))
        bone(f"UpperArm.{side}", sh, elbow, "Spine")
        bone(f"LowerArm.{side}", elbow, wrist, f"UpperArm.{side}", True)
        bone(f"Hand.{side}", wrist, hand + (hand - wrist) * 0.3, f"LowerArm.{side}", True)
        hip = Vector((s * L["legs"][s], 0, c))
        ankle = Vector((s * L["legs"][s], 0, 0.06))
        knee = (hip + ankle) / 2 + Vector((0, -0.01, 0))
        bone(f"UpperLeg.{side}", hip, knee, "Hips")
        bone(f"LowerLeg.{side}", knee, ankle, f"UpperLeg.{side}", True)
        bone(f"Foot.{side}", ankle, (ankle.x, L["toe_y"], 0.02), f"LowerLeg.{side}", True)
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


# ---------------------------------------------------------------------------
# 4. 蒙皮：距离权重 + 部位限制
# ---------------------------------------------------------------------------
def seg_dist(p, a, b):
    ab = b - a
    t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


def skin(obj, rig, L, co):
    bones = {b.name: (np.array(b.head_local[:]), np.array(b.tail_local[:])) for b in rig.data.bones}
    names = list(bones)
    D = np.stack([seg_dist(co, *bones[n]) for n in names], axis=1)
    x, z = co[:, 0], co[:, 2]
    allowed = np.ones_like(D, dtype=bool)

    def only(mask, groups):
        cols = [i for i, n in enumerate(names) if n in groups]
        allowed[mask] = False
        for i in cols:
            allowed[mask, i] = True

    neck, c = L["neck"], L["crotch"]
    th = L["torso_half"]
    only(z > neck + 0.02, {"Head", "Neck"})
    for s, side in ((-1, "R"), (1, "L")):
        only((x * s > th * 0.95) & (z > c) & (z < neck), {f"UpperArm.{side}", f"LowerArm.{side}", f"Hand.{side}", "Spine"})
        only((z < c - 0.02) & (x * s > 0), {f"UpperLeg.{side}", f"LowerLeg.{side}", f"Foot.{side}", "Hips"})
    only((np.abs(x) <= th * 0.95) & (z > c - 0.02) & (z <= neck + 0.02), {"Hips", "Spine", "Neck", "UpperLeg.R", "UpperLeg.L"})

    W = np.where(allowed, 1.0 / (D + 0.01) ** 4, 0.0)
    top2 = np.argsort(-W, axis=1)[:, :2]
    keep = np.zeros_like(W, dtype=bool)
    np.put_along_axis(keep, top2, True, axis=1)
    W = np.where(keep, W, 0.0)
    W /= W.sum(1, keepdims=True) + 1e-12

    for i, n in enumerate(names):
        vg = obj.vertex_groups.new(name=n)
        idx = np.nonzero(W[:, i] > 0.01)[0]
        for vi in idx:
            vg.add([int(vi)], float(W[vi, i]), "REPLACE")
    obj.parent = rig
    mod = obj.modifiers.new("Rig", "ARMATURE")
    mod.object = rig


# ---------------------------------------------------------------------------
# 5. 动画：用「绕世界轴旋转」来写，再换算成骨骼自己的局部旋转
# ---------------------------------------------------------------------------
def world_rot(pb, axis, deg):
    rest = pb.bone.matrix_local.to_quaternion()
    q = Quaternion(Vector(axis), math.radians(deg))
    return rest.inverted() @ q @ rest


def make_action(rig, name, frames, keys):
    """keys: {帧号: {骨骼名: [(轴, 角度), ...] 或 ('loc', (x,y,z))}}"""
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = act
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
    for f, pose in sorted(keys.items()):
        for pb in rig.pose.bones:
            pb.rotation_quaternion = Quaternion()
            pb.location = Vector()
        aims = []
        for bname, spec in pose.items():
            pb = rig.pose.bones[bname]
            if spec and spec[0] == "loc":
                pb.location = pb.bone.matrix_local.to_3x3().inverted() @ Vector(spec[1])
                continue
            if spec and spec[0] == "aim":
                aims.append((pb, Vector(spec[1]).normalized()))
                continue
            q = Quaternion()
            for axis, deg in spec:
                q = world_rot(pb, axis, deg) @ q
            pb.rotation_quaternion = q
        # 「指向」类：按父子顺序，让骨头在骨架空间里指向给定方向（父骨头先摆好，子骨头再算）
        aims.sort(key=lambda a: len(a[0].parent_recursive))
        for pb, target in aims:
            bpy.context.view_layer.update()
            cur = pb.matrix.to_quaternion()
            dir_now = (pb.matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
            qw = dir_now.rotation_difference(target)
            pb.rotation_quaternion = pb.rotation_quaternion @ (cur.inverted() @ qw @ cur)
        for pb in rig.pose.bones:
            pb.keyframe_insert("rotation_quaternion", frame=f)
            pb.keyframe_insert("location", frame=f)
    act.frame_range = (0, frames)
    return act


X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)


def animations(rig):
    acts = []
    # 待机：轻微呼吸、头左右歪一点、手臂微摆（2 秒循环）
    k = {}
    for f, t in ((0, 0), (15, 1), (30, 0), (45, -1), (60, 0)):
        k[f] = {"Spine": [(X, 1.5 * abs(t))], "Head": [(Y, 3 * t)],
                "UpperArm.L": [(Y, 2 * t)], "UpperArm.R": [(Y, 2 * t)],
                "Hips": ("loc", (0, 0, -0.004 * abs(t)))}
    acts.append(make_action(rig, "Idle", 60, k))

    # 走路：腿前后摆、膝盖弯、手臂反向摆、身体上下起伏（1 秒循环）
    k = {}
    for f in range(0, 31, 5):
        ph = f / 30 * math.tau
        sw = math.sin(ph)
        k[f] = {"UpperLeg.L": [(X, 28 * sw)], "UpperLeg.R": [(X, -28 * sw)],
                "LowerLeg.L": [(X, -25 * max(0, -sw))], "LowerLeg.R": [(X, -25 * max(0, sw))],
                "UpperArm.L": [(X, -22 * sw)], "UpperArm.R": [(X, 22 * sw)],
                "LowerArm.L": [(X, -15)], "LowerArm.R": [(X, -15)],
                "Spine": [(Z, 4 * sw)], "Head": [(Z, -3 * sw)],
                "Hips": ("loc", (0, 0, 0.012 * abs(math.cos(ph))))}
    acts.append(make_action(rig, "Walk", 30, k))

    # 采摘：蹲下、身体前倾、右手往前下方伸、再站起来（2 秒）
    k = {}
    for f, t in ((0, 0), (15, 1), (30, 1), (40, 1), (60, 0)):
        reach = 1 if f in (30,) else (0.5 if f in (15, 40) else 0)
        k[f] = {"Hips": ("loc", (0, 0, -0.16 * t)),
                "UpperLeg.L": [(X, -75 * t)], "UpperLeg.R": [(X, -75 * t)],
                "LowerLeg.L": [(X, 120 * t)], "LowerLeg.R": [(X, 120 * t)],
                "Foot.L": [(X, -45 * t)], "Foot.R": [(X, -45 * t)],
                "Spine": [(X, 20 * t)], "Head": [(X, 10 * t)],   # 正角度 = 往前倾
                "UpperArm.L": [(X, -25 * t)]}
        if t:  # 右手往前下方伸向草莓，伸到最远时再低一点
            k[f]["UpperArm.R"] = ("aim", (0.1, -0.55 - 0.1 * reach, -0.8))
            k[f]["LowerArm.R"] = ("aim", (0.05, -0.45 - 0.15 * reach, -0.88))
    acts.append(make_action(rig, "Pick", 60, k))

    # 偷吃：右手把草莓送到嘴边，头往前点两下（2 秒）
    k = {}
    for f, t, nod in ((0, 0, 0), (15, 1, 0), (25, 1, 1), (35, 1, 0), (45, 1, 1), (60, 0, 0)):
        k[f] = {"Head": [(X, 8 * nod)], "Spine": [(X, 3 * t)]}
        if t:
            k[f]["UpperArm.R"] = ("aim", (0.25, -0.75, -0.6))
            k[f]["LowerArm.R"] = ("aim", (0.28, -0.55, 0.79))
    acts.append(make_action(rig, "Eat", 60, k))
    rig.animation_data.action = acts[0]
    return acts


def preview(rig, obj, out_dir):
    """每段动画截几帧，快速目测蒙皮有没有撕裂。"""
    os.makedirs(out_dir, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"  # 无显示器环境跑不了 Workbench/EEVEE，用低采样 Cycles
    scene.cycles.samples = 8
    scene.cycles.device = "CPU"
    world = bpy.data.worlds.new("W")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.5
    scene.world = world
    scene.render.resolution_x, scene.render.resolution_y = 360, 480
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    cam.location = (1.6, -2.6, 0.9)
    cam.rotation_euler = Euler((math.radians(80), 0, math.radians(31)))
    scene.camera = cam
    for act in bpy.data.actions:
        rig.animation_data.action = act
        for f in (0, int(act.frame_range[1] // (4 if act.name == "Walk" else 2))):
            scene.frame_set(f)
            for bn in ("UpperArm.R", "LowerArm.R", "UpperLeg.R"):
                pb = rig.pose.bones[bn]
                print(f"  {act.name}@{f} {bn}: 头 {tuple(round(c, 2) for c in pb.head)} -> 尾 {tuple(round(c, 2) for c in pb.tail)}")
            scene.render.filepath = os.path.join(out_dir, f"{act.name}_{f:02d}.png")
            bpy.ops.render.render(write_still=True)


def main():
    obj, co = load_mesh(SRC)
    L = landmarks(co)
    rig = build_armature(L)
    skin(obj, rig, L, co)
    animations(rig)
    bpy.context.scene.render.fps = FPS
    if PREVIEW:
        preview(rig, obj, PREVIEW)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    rig.select_set(True)
    obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=DST, export_format="GLB", use_selection=True,
                              export_animation_mode="ACTIONS", export_force_sampling=True)
    print("导出:", DST, f"{os.path.getsize(DST) / 1e6:.1f} MB")


main()
