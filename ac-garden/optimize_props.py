"""把混元 3D 生成的场景道具压缩成网页能用的大小。

    python optimize_props.py <输入目录> <输出目录> [--faces 8000] [--tex 1024]

每件道具：合并成一个网格 -> 平滑着色 -> 减面到目标面数 -> 贴图缩到 tex 边长 -> 以 JPEG 贴图导出 glb。
尺寸和朝向不改，摆放时在游戏里按包围盒缩放。
"""
import os
import sys

import bpy  # 必须先于 mathutils 导入

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]


def opt(name, default):
    if name in argv:
        i = argv.index(name)
        v = argv[i + 1]
        del argv[i:i + 2]
        return v
    return default


FACES = int(opt("--faces", "8000"))
TEX = int(opt("--tex", "1024"))
SRC, DST = argv[0], argv[1]
os.makedirs(DST, exist_ok=True)

for name in sorted(os.listdir(SRC)):
    if not name.endswith(".glb"):
        continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, name))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    before = len(obj.data.polygons)
    obj.data.polygons.foreach_set("use_smooth", [True] * before)
    if before > FACES:
        dec = obj.modifiers.new("Decimate", "DECIMATE")
        dec.ratio = FACES / before
        bpy.ops.object.modifier_apply(modifier="Decimate")
    for img in bpy.data.images:
        if img.size[0] > TEX:
            img.scale(TEX, int(img.size[1] * TEX / img.size[0]))
    out = os.path.join(DST, name)
    for o in bpy.context.scene.objects:
        o.select_set(o.type == "MESH")
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True,
                              export_image_format="JPEG", export_image_quality=85)
    print(f"{name}: {before} -> {len(obj.data.polygons)} 面, {os.path.getsize(out) / 1e6:.2f} MB")
