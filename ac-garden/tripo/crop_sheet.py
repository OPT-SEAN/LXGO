"""从「小女孩全套素材参考」设定表里裁出三视图，作为 Tripo 多视图生成的输入。

    python crop_sheet.py <设定表图片> [输出目录]

设定表第一行「1. 全身三视图」从左到右是：正面、侧面、背面、四分之三。
下面的裁切框是按整张表的宽高比例量的（表的版式固定，分辨率不同也适用）。
裁出来后会把米色底统一铺成白色、四周留白补成正方形，生成效果更稳定。
"""
import os
import sys

from PIL import Image

# (左, 上, 右, 下)，占整张表宽/高的比例
BOXES = {
    "front": (0.085, 0.085, 0.250, 0.405),
    "side": (0.330, 0.085, 0.490, 0.405),
    "back": (0.520, 0.085, 0.690, 0.405),
    "three_quarter": (0.745, 0.085, 0.905, 0.405),
}


def to_square_white(img, pad=0.08):
    """米色底 -> 白底，再补成带留白的正方形。"""
    img = img.convert("RGB")
    px = img.load()
    w, h = img.size
    bg = px[2, 2]
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) < 36:
                px[x, y] = (255, 255, 255)
    side = int(max(w, h) * (1 + pad * 2))
    out = Image.new("RGB", (side, side), (255, 255, 255))
    out.paste(img, ((side - w) // 2, (side - h) // 2))
    return out.resize((1024, 1024), Image.LANCZOS)


def main():
    sheet = Image.open(sys.argv[1])
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "views"
    os.makedirs(out_dir, exist_ok=True)
    W, H = sheet.size
    for name, (l, t, r, b) in BOXES.items():
        crop = sheet.crop((int(l * W), int(t * H), int(r * W), int(b * H)))
        path = os.path.join(out_dir, f"{name}.png")
        to_square_white(crop).save(path)
        print("裁出:", path)


if __name__ == "__main__":
    main()
