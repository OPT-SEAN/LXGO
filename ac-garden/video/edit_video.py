"""把 clips/ 里的 5 段镜头剪成成片 strawberry_demo.mp4。

    pip install pillow imageio-ffmpeg
    python edit_video.py

每段：按 CUTS 截取 -> 叠加片名 / 动森风对话框字幕（Pillow 画成透明 PNG，淡入淡出）
-> 段与段之间 0.5 秒交叉淡化 -> 结尾淡出到黑。
字体：fonts/ZCOOLKuaiLe-Regular.ttf（站酷快乐体，OFL 协议）。
"""
import os
import subprocess

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
CLIPS = os.path.join(HERE, "clips")
WORK = os.path.join(CLIPS, "_edit")
OUT = os.path.join(HERE, "strawberry_demo.mp4")
FONT = os.path.join(HERE, "fonts", "ZCOOLKuaiLe-Regular.ttf")
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 1344, 768, 24
XF = 0.5  # 交叉淡化秒数

# 镜头：文件名、截取区间（秒）、叠加文字 [(类型, 文字, 开始, 结束)]，时间相对于截取后的片段
# 03_look 原片 2.6~5.65 秒镜头往下扫到脚上又扫回来，剪掉；05_caught 按用户要求不用
SHOTS = [
    ("01_open", [(0, 10.13)], [("title", "草莓园的小秘密", 0.8, 5.0)]),
    ("02_pick", [(0, 10.13)], [("say", "找到啦，最红的一颗！", 3.0, 8.0)]),
    ("03_look", [(0, 2.6), (5.65, 10.13)], [("say", "……应该没人看见吧？", 1.0, 6.2)]),
    ("04_eat", [(0, 10.13)], [("say", "嗯～好甜！", 2.2, 7.5)]),
    ("06_end", [(0, 10.13)], [("end", "完", 6.8, 10.13)]),
]

BROWN = (110, 74, 42, 255)
CREAM = (255, 248, 222, 255)


def font(size):
    return ImageFont.truetype(FONT, size)


def centered(draw, y, text, f, **kw):
    w = draw.textbbox((0, 0), text, font=f, **{k: v for k, v in kw.items() if k == "stroke_width"})[2]
    draw.text(((W - w) / 2, y), text, font=f, **kw)


def overlay_png(kind, text, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if kind == "title":
        centered(d, 150, text, font(96), fill=CREAM, stroke_width=8, stroke_fill=BROWN)
    elif kind == "end":
        centered(d, 40, text, font(150), fill=CREAM, stroke_width=10, stroke_fill=BROWN)
        centered(d, 225, "草莓园的小秘密", font(48), fill=CREAM, stroke_width=5, stroke_fill=BROWN)
    else:  # 动森风对话框：奶油色圆角框 + 棕色字，底部居中
        f = font(46)
        tw = d.textbbox((0, 0), text, font=f)[2]
        bw, bh = max(tw + 120, 560), 116
        x0, y0 = (W - bw) // 2, H - bh - 46
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((x0 + 4, y0 + 7, x0 + bw + 4, y0 + bh + 7), 58, fill=(60, 40, 20, 70))
        img.alpha_composite(shadow)
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 58, fill=CREAM)
        d.text(((W - tw) / 2, y0 + 30), text, font=f, fill=BROWN)
    img.save(path)


def run(args):
    subprocess.run([FF, "-v", "error", "-y", *args], check=True)


def main():
    os.makedirs(WORK, exist_ok=True)
    parts = []
    for name, cuts, texts in SHOTS:
        src = os.path.join(CLIPS, f"{name}.mp4")
        # 1) 截取（多段则直接拼接成硬切）
        trims = "".join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[c{i}];" for i, (a, b) in enumerate(cuts))
        chain = trims + "".join(f"[c{i}]" for i in range(len(cuts))) + f"concat=n={len(cuts)}:v=1:a=0[base];"
        # 2) 叠加文字，alpha 淡入淡出
        inputs, last = ["-i", src], "base"
        for j, (kind, text, t0, t1) in enumerate(texts):
            png = os.path.join(WORK, f"{name}_{j}.png")
            overlay_png(kind, text, png)
            inputs += ["-loop", "1", "-framerate", str(FPS), "-t", str(t1), "-i", png]
            chain += (f"[{j + 1}:v]format=rgba,fade=in:st={t0}:d=0.4:alpha=1,"
                      f"fade=out:st={t1 - 0.4}:d=0.4:alpha=1[t{j}];"
                      f"[{last}][t{j}]overlay=0:0:eof_action=pass[o{j}];")
            last = f"o{j}"
        chain += f"[{last}]fps={FPS},format=yuv420p[v]"
        part = os.path.join(WORK, f"{name}.mp4")
        run([*inputs, "-filter_complex", chain, "-map", "[v]", "-c:v", "libx264", "-crf", "14", "-preset", "slow", part])
        dur = sum(b - a for a, b in cuts)
        parts.append((part, dur))

    # 3) 交叉淡化串起来，结尾淡出到黑
    inputs, chain, last, offset = [], "", "0:v", 0.0
    for i, (p, _) in enumerate(parts):
        inputs += ["-i", p]
    for i in range(1, len(parts)):
        offset += parts[i - 1][1] - XF
        chain += f"[{last}][{i}:v]xfade=transition=fade:duration={XF}:offset={offset:.3f}[x{i}];"
        last = f"x{i}"
    total = offset + parts[-1][1]
    chain += f"[{last}]fade=in:st=0:d=0.8,fade=out:st={total - 1.2:.3f}:d=1.2,format=yuv420p[v]"
    run([*inputs, "-filter_complex", chain, "-map", "[v]", "-c:v", "libx264", "-crf", "18", "-preset", "slow",
         "-movflags", "+faststart", OUT])
    print(f"成片：{OUT}  约 {total:.1f} 秒")


if __name__ == "__main__":
    main()
