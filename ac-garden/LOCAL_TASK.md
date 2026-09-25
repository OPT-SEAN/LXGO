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

## 角色设定（最重要）

**脸和体型 = 动森（Animal Crossing: New Horizons）的玩家主角；发型、耳机、衣服 = 用户的设定表。**

- 脸（动森主角）：大圆脸、腮帮饱满；一双很大的圆眼睛，白眼白 + 深棕粗描边 + 大深棕虹膜 + 白色高光，
  外眼角两根小睫毛；鼻子是一个小小的三角凸起；嘴是一条细细的微笑线；两颊圆形腮红；两侧半圆形小耳朵。
- 体型（动森主角）：头约占身高 45%；脖子很细；躯干窄小，约为头宽一半；胳膊细，手是没有手指的圆拳头；
  腿细而直，鞋子相对大。
- 发型（设定表）：黑发中分、露出额头，乱一点的高马尾，脸两侧垂几缕碎发，粉色发夹。
- 耳机（设定表）：蓝粉配色的头戴式耳机。
- 衣服（设定表）：芥末黄针织毛衣，正面一只深棕色举手小熊剪影，两侧和袖子是奶油色竖向折线，罗纹领口袖口；
  黄色裤子带奶油色侧条；棕色护腿，上沿一圈奶油色毛边；浅蓝色运动鞋带彩色小斑点。小麦色皮肤。

如果 ComfyUI 装了 IP-Adapter 之类的参考图节点：运行 `ac-garden/refs/fetch_refs.sh` 下载动森官方图，
用 `Player_5_NH.png`（女孩）作为脸和体型的参考图；没有这类节点就只用文字提示词。

## 提示词

正向：
```
character turnaround sheet, front view, side view, back view, same character, full body, standing, arms slightly away from body,
Animal Crossing New Horizons player character, villager, 3D render, Nintendo style,
huge round head about half of body height, round face with full cheeks, very large round eyes with thick dark brown outline and white highlights,
tiny triangular nose, thin simple smile line, round pink blush, small round ears,
thin neck, small narrow torso, thin arms with round ball fists without fingers, thin straight legs, chunky shoes,
little girl, black hair center part showing forehead, high messy ponytail, loose strands framing face, pink hair clip,
blue and pink over-ear headphones,
mustard yellow knit sweater with big dark brown bear silhouette with raised arms on front, cream vertical zigzag stripes on sleeves and sides, ribbed cuffs,
yellow pants with cream side stripe, brown leg warmers with fluffy cream trim, light blue sneakers with colorful speckles, tan skin,
soft warm studio lighting, plain white background, clean 3D render, high detail
```

反向：
```
realistic, photo, realistic proportions, small eyes, detailed nose, fingers, anime, 2D, pixel art,
multiple characters, different outfits, cropped, cut off, text, watermark, extra limbs, blurry, dark background
```

分辨率建议横版（如 1536×768），三个视图并排放得下。
