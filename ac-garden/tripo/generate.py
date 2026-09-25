"""用 Tripo API 把三视图变成带贴图、带骨骼动画的 3D 角色。

流程：多视图生成模型 -> 检查能否绑骨 -> 自动绑骨 -> 套预设动画（待机、走路…）-> 下载 glb。
API Key 从环境变量 TRIPO_API_KEY 读取（在云环境设置里配置，不要写进代码或贴到聊天里）。

    pip install tripo3d
    python generate.py --front views/front.png --left views/side.png --back views/back.png \
                       --out out/girl --anims idle walk

说明：
- Tripo 的四个视角顺序是 [正面, 左, 背面, 右]，正面必填，至少两张。
  设定表只有一张侧面（人物朝画面左边，看到的是她的右侧），先当作 --left 试；
  如果生成出来左右颠倒，改用 --right 再跑一次。
- 每一步的 task_id 记在 <out>/tasks.json 里，下载链接 5 分钟就过期，脚本会立刻下载。
"""
import argparse
import asyncio
import json
import os

from tripo3d import TaskStatus, TripoClient

MODEL_VERSION = "v3.1-20260211"   # 文档里多视图生成的最新版本
ANIMS = {"idle": "preset:idle", "walk": "preset:walk", "run": "preset:run",
         "jump": "preset:jump", "turn": "preset:turn", "hurt": "preset:hurt"}


async def run_task(client, task_id, label, out_dir, log):
    log[label] = task_id
    print(f"[{label}] task_id = {task_id}")
    task = await client.wait_for_task(task_id, verbose=True)
    if task.status != TaskStatus.SUCCESS:
        raise SystemExit(f"[{label}] 失败，状态 {task.status}，task_id {task_id}")
    files = await client.download_task_models(task, os.path.join(out_dir, label))
    for kind, path in (files or {}).items():
        print(f"[{label}] 下载 {kind}: {path}")
    return task


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--front", required=True)
    ap.add_argument("--left")
    ap.add_argument("--back")
    ap.add_argument("--right")
    ap.add_argument("--out", default="out")
    ap.add_argument("--face-limit", type=int, default=40000, help="面数上限，游戏里用 2~5 万足够")
    ap.add_argument("--detailed", action="store_true", help="高清贴图 + 高精度几何（多花约 30 积分）")
    ap.add_argument("--anims", nargs="*", default=["idle", "walk"], choices=list(ANIMS))
    ap.add_argument("--no-rig", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    log = {}
    async with TripoClient() as client:
        balance = await client.get_balance()
        print("当前积分:", balance)

        images = [args.front, args.left, args.back, args.right]
        quality = "detailed" if args.detailed else "standard"
        tid = await client.multiview_to_model(
            images=images, model_version=MODEL_VERSION, face_limit=args.face_limit,
            texture=True, pbr=True, texture_quality=quality, geometry_quality=quality,
            orientation="align_image",
        )
        await run_task(client, tid, "model", args.out, log)

        if not args.no_rig:
            check = await client.check_riggable(tid)
            await run_task(client, check, "rigcheck", args.out, log)
            rig = await client.rig_model(tid, model_version="v2.0-20250506")
            await run_task(client, rig, "rig", args.out, log)
            if args.anims:
                anim = await client.retarget_animation(
                    rig, animation=[ANIMS[a] for a in args.anims],
                    export_with_geometry=True, animate_in_place=True)
                await run_task(client, anim, "animated", args.out, log)

    with open(os.path.join(args.out, "tasks.json"), "w") as f:
        json.dump(log, f, indent=2)
    print("完成，task_id 记录在", os.path.join(args.out, "tasks.json"))


if __name__ == "__main__":
    asyncio.run(main())
