# 本地会话任务：用 ComfyUI 生成女孩的三视图

给在用户本地电脑（有显卡和 ComfyUI）上运行的 Claude Code 会话看。
云端会话负责后面的 3D 生成和场景搭建；本地会话只负责出图并推送。

## 要做的

1. 确认在分支 `claude/zealous-pascal-0qyy1e` 上，先 `git pull`。
2. 用本机的 ComfyUI 生成角色三视图（正面、侧面、背面，同一个角色、同一套衣服），
   白色纯色背景，全身，站姿，手臂自然下垂略张开。提示词见下方。
   每组参数多出几张，挑三个视图最一致、最干净的一张。
3. 把挑中的图放到 `ac-garden/tripo/inputs/`，文件名：
   - `turnaround.png`：三视图拼在一张图里的原图
   - 如果模型是分开出图的，就用 `front.png`、`side.png`、`back.png`
4. 逐个 `git add` 这些图片（不要 `git add -A`），提交并推送到 `claude/zealous-pascal-0qyy1e`。
5. 告诉用户已推送，云端会话会接着做。

## 角色设定（以用户的「小女孩全套素材参考」为准）

黑发中分、乱一点的高马尾、粉色发夹；蓝粉配色头戴式耳机；
芥末黄针织毛衣，正面一只深棕色举手小熊剪影，两侧和袖子是奶油色竖向折线，罗纹领口袖口；
黄色裤子带奶油色侧条；棕色护腿，上沿一圈奶油色毛边；浅蓝色运动鞋带彩色小斑点；小麦色皮肤，深棕色眼睛。
画风：动森（Animal Crossing: New Horizons）那种 3D Q 版，大圆头，干净柔和的渲染。

## 提示词

正向：
```
character turnaround sheet, front view, side view, back view, same character, full body, standing, arms slightly away from body,
chibi little girl in Animal Crossing New Horizons 3D style, big round head, large simple eyes, small nose, rosy cheeks,
black hair center part, high messy ponytail, pink hair clip, blue and pink over-ear headphones,
mustard yellow knit sweater with big dark brown bear silhouette on front, cream zigzag stripes on sleeves and sides,
yellow pants with cream side stripe, brown leg warmers with fluffy cream trim, light blue sneakers with colorful speckles,
soft studio lighting, plain white background, clean 3D render, high detail
```

反向：
```
realistic, photo, multiple characters, different outfits, cropped, cut off, text, watermark, extra limbs, blurry, dark background
```

分辨率建议横版（如 1536×768），三个视图并排放得下。
