"""用 MiniMax 海螺（Hailuo）按分镜生成草莓园演示视频的各段镜头。

    export MINIMAX_API_KEY=...            # 在云环境设置里配置，不要写进代码
    export MINIMAX_BASE=https://api.minimax.io     # 国内账号用 https://api.minimaxi.com
    python make_video.py [镜头编号 ...] [--model MiniMax-H3] [--dry-run]

每个镜头：角色参考图（refs/front.png 等，按官方文档用 reference_image 传入）+ 分镜文字
-> POST /v2/video_generation -> 轮询 GET /v2/query/video_generation/{task_id}
-> 成功后下载到 clips/<编号>.mp4，task_id 记在 clips/tasks.json。
图片以 data:image/png;base64 的形式传；如果接口不收 data URL，需要改成公网可访问的图片地址。
"""
import base64
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("MINIMAX_BASE", "https://api.minimax.io").rstrip("/")
KEY = os.environ.get("MINIMAX_API_KEY", "")

STYLE = ("Animal Crossing New Horizons style 3D animation, Nintendo, cute rounded chunky shapes, "
         "soft warm sunlight, pastel saturated colors, gentle camera, high quality. "
         "The same little girl as in the reference images: huge round head, big blue eyes, black hair with center part "
         "and a high messy ponytail, blue and pink headphones, mustard yellow knit sweater with a brown bear "
         "silhouette on the front, yellow pants, brown fluffy leg warmers, light blue sneakers.")

# 分镜：编号、时长（秒）、画面描述
SHOTS = [
    ("01_open", 6, "Wide establishing shot of a cozy strawberry garden on a sunny island: wooden raised planter boxes "
                   "full of strawberry plants with red berries, a white picket fence, round fluffy trees, flowers, "
                   "stepping-stone path. The camera slowly glides forward. The girl walks in along the path, happy."),
    ("02_pick", 6, "Medium shot: the girl crouches beside a wooden planter box and carefully picks a ripe red "
                   "strawberry, holds it up and smiles, then puts it into a small wicker basket with a red gingham cloth."),
    ("03_look", 5, "Close-up: the girl holds a strawberry, looks left and right to check nobody is watching, "
                   "with a sneaky little grin."),
    ("04_eat", 5, "Close-up: the girl quickly takes a big bite of the strawberry, cheeks puffed, eyes closed in delight."),
    ("05_caught", 5, "The girl freezes, a red exclamation mark pops above her head, she jumps in surprise with both "
                     "arms up, then hides the strawberry behind her back and smiles innocently."),
    ("06_end", 6, "Wide shot at golden hour: the girl walks away along the path carrying the basket of strawberries, "
                  "the camera slowly rises above the strawberry garden."),
]


def data_url(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def api(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "MiniMax-H3"
    if "--model" in sys.argv:
        args.remove(model)
    dry = "--dry-run" in sys.argv
    shots = [s for s in SHOTS if not args or s[0] in args or s[0][:2] in args]
    refs = [os.path.join(HERE, "refs", n) for n in ("front.png", "side.png", "back.png")]
    out_dir = os.path.join(HERE, "clips")
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "tasks.json")
    log = json.load(open(log_path)) if os.path.exists(log_path) else {}

    if not KEY and not dry:
        raise SystemExit("缺少环境变量 MINIMAX_API_KEY")
    for name, dur, desc in shots:
        body = {
            "model": model,
            "content": [{"type": "text", "text": f"{STYLE} {desc}"}] +
                       [{"type": "image_url", "image_url": {"url": data_url(p)}, "role": "reference_image"} for p in refs],
            "duration": dur,
            "resolution": "768P",
        }
        if dry:
            print(name, json.dumps({**body, "content": [c if c["type"] == "text" else "<图片>" for c in body["content"]]},
                                   ensure_ascii=False)[:400])
            continue
        task = api("POST", "/v2/video_generation", body)
        tid = task.get("task_id") or task.get("id")
        print(name, "提交:", tid, "" if tid else task)
        log[name] = {"task_id": tid, "model": model}
        json.dump(log, open(log_path, "w"), indent=2, ensure_ascii=False)

    for name, _, _ in ([] if dry else shots):
        tid = log[name]["task_id"]
        while True:
            t = api("GET", f"/v2/query/video_generation/{tid}")
            status = t.get("status")
            if status in ("succeeded", "failed", "cancelled"):
                break
            time.sleep(15)
        print(name, status)
        if status == "succeeded":
            url = (t.get("content") or {}).get("url")
            urllib.request.urlretrieve(url, os.path.join(out_dir, f"{name}.mp4"))
            print("  下载:", os.path.join(out_dir, f"{name}.mp4"))
        else:
            print("  返回:", json.dumps(t, ensure_ascii=False)[:500])


if __name__ == "__main__":
    main()
