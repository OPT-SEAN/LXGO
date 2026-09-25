"""只搭主人公，在中性灰背景下渲染正面和 3/4 侧面，方便和 refs/ 里的官方图对照。

    python portrait.py <输出目录> [--quick]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Euler  # noqa: E402

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

import girl  # noqa: E402

col = bpy.data.collections.new("Portrait")
scene.collection.children.link(col)
girl.build(col)

world = bpy.data.worlds.new("Studio")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = helpers.srgb("#b4b4b4")
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
scene.world = world

key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "SUN"))
key.data.energy = 2.6
key.data.angle = math.radians(25)
key.data.color = (1.0, 0.96, 0.9)
key.rotation_euler = Euler((math.radians(40), 0, math.radians(-25)))
scene.collection.objects.link(key)

target = bpy.data.objects.new("Target", None)
target.location = (0, 0, 0.52)
scene.collection.objects.link(target)
cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
cam.data.lens = 70
scene.collection.objects.link(cam)
tr = cam.constraints.new("TRACK_TO")
tr.target = target
tr.track_axis = "TRACK_NEGATIVE_Z"
tr.up_axis = "UP_Y"
scene.camera = cam

scene.view_settings.view_transform = "Standard"
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
quick = "--quick" in flags
scene.cycles.samples = 24 if quick else 96
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = (500, 800) if quick else (900, 1400)

for name, az in (("portrait_front", 0), ("portrait_34", 30)):
    a = math.radians(az)
    cam.location = (3.2 * math.sin(a), -3.2 * math.cos(a), 0.75)
    scene.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print("渲染:", scene.render.filepath)
