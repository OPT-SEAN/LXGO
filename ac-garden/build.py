"""动森风草莓园：搭场景、导出模型、渲染合照。

运行（需要 Blender 4.2，或 pip 安装的 bpy==4.2.*）：
    python build.py <输出目录>               # 全部：建模 + 导出 + 渲染
    python build.py <输出目录> --no-render    # 只建模和导出
    python build.py <输出目录> --quick        # 低采样快速预览

产物：
    ac_garden.blend       整个场景的 Blender 工程
    girl.glb / isabelle.glb / nook.glb   三个角色，各自以脚底中心为原点
    garden.glb            草莓园环境（不含角色）
    render_group.png      合照渲染
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import helpers  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
flags = {a for a in argv if a.startswith("--")}
args = [a for a in argv if not a.startswith("--")]
OUT = os.path.abspath(args[0] if args else ".")
os.makedirs(OUT, exist_ok=True)
helpers.TEX_DIR = os.path.join(OUT, "textures")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
helpers.init_common_materials()

import garden  # noqa: E402
import girl  # noqa: E402
import isabelle  # noqa: E402
import nook  # noqa: E402

world_col = bpy.data.collections.new("ACGarden")
scene.collection.children.link(world_col)

parts = {
    "girl": girl.build(world_col),
    "isabelle": isabelle.build(world_col),
    "nook": nook.build(world_col),
}
land = garden.build(world_col)

# 摆位：女孩站在小路上，西施惠在左、狸克在右，都微微侧身朝向她
parts["girl"].place((0.0, -0.55, 0.0), 0)
parts["isabelle"].place((-0.78, -0.95, 0.0), 28)
parts["nook"].place((0.8, -0.85, 0.0), -28)


def export(objs, path):
    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    for ob in objs:
        ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True)
    print("导出:", path, f"{os.path.getsize(path) / 1e6:.1f} MB")


# 单个角色：临时挪回原点再导出，方便以后在游戏里自由摆放
for key, part in parts.items():
    loc, rot = part.root.location.copy(), part.root.rotation_euler.copy()
    part.place((0, 0, 0), 0)
    bpy.context.view_layer.update()
    export(list(part.col.all_objects), os.path.join(OUT, f"{key}.glb"))
    part.root.location, part.root.rotation_euler = loc, rot
bpy.context.view_layer.update()
export(list(land.col.all_objects), os.path.join(OUT, "garden.glb"))  # 只含环境，角色另存

# ---------------- 灯光与相机：动森式的明亮阳光 + 俯视 + 浅景深 ----------------
world = bpy.data.worlds.new("Sky")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = helpers.srgb("#9fd3fb")
bg.inputs["Strength"].default_value = 0.9
scene.world = world

sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 2.8
sun.data.angle = math.radians(10)
sun.data.color = (1.0, 0.95, 0.86)
sun.rotation_euler = Euler((math.radians(48), 0, math.radians(-32)))
scene.collection.objects.link(sun)

focus = bpy.data.objects.new("Focus", None)
focus.location = (0, -0.65, 0.42)
scene.collection.objects.link(focus)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 46
cam.data.dof.use_dof = True
cam.data.dof.focus_object = focus
cam.data.dof.aperture_fstop = 2.0
cam.location = (0, -4.3, 2.15)
scene.collection.objects.link(cam)
track = cam.constraints.new("TRACK_TO")
track.target = focus
track.track_axis = "TRACK_NEGATIVE_Z"
track.up_axis = "UP_Y"
scene.camera = cam

# 动森的颜色明亮饱满，用 Standard 映射保留原色（AgX 会把饱和色压灰）
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.view_settings.exposure = 0.0

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "ac_garden.blend"))
backup = os.path.join(OUT, "ac_garden.blend1")
if os.path.exists(backup):
    os.remove(backup)

if "--no-render" not in flags:
    quick = "--quick" in flags
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24 if quick else 128
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = (800, 500) if quick else (1600, 1000)
    scene.render.filepath = os.path.join(OUT, "render_group.png")
    bpy.ops.render.render(write_still=True)
    print("渲染:", scene.render.filepath)
