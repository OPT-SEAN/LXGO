# 用 Tripo 生成草莓园女孩的 3D 模型

手工拼几何体的角色达不到动森的精致度，改用 Tripo 的图生 3D：
输入设定表里的三视图，输出带贴图、自动绑好骨骼、带待机和走路动画的 `.glb`。

## 准备（只需一次）

1. 在 Tripo 开发者平台（developers.tripo3d.ai）生成 API Key（以 `tsk_` 开头）。
2. 在云环境设置里加环境变量 `TRIPO_API_KEY=tsk_...`。**不要写进代码或提交到仓库。**
   新会话才能读到这个变量。
3. 安装依赖：`pip install tripo3d pillow`

## 步骤

```sh
cd ac-garden/tripo
# 1. 从设定表裁出正面/侧面/背面（设定表原图由用户提供，不入库）
python crop_sheet.py <设定表图片> views
# 2. 先看一眼 views/ 里裁得对不对，再生成（约 60~100 积分：生成 + 绑骨 + 动画）
python generate.py --front views/front.png --left views/side.png --back views/back.png \
                   --out out/girl --anims idle walk
```

产物在 `out/girl/`：`model/`（静态模型）、`rig/`（带骨骼）、`animated/`（带动画），
每一步的 task_id 记在 `out/girl/tasks.json`。

## 注意

- 设定表只有一张侧面图。Tripo 的视角顺序是 [正面, 左, 背面, 右]，先当 `--left` 试；
  生成结果左右颠倒就改用 `--right`。
- 设定表每个视图只有两三百像素宽，分辨率偏低。效果不理想时，请用户提供更高清的三视图。
- 生成结果的画风跟着输入图走：设定表是偏写实的 2D 风格，输出不会自动变成动森风。
- 接下来要做的：把 `animated/` 里的 glb 放进 `ac-garden` 的草莓园场景和 Three.js 查看器，
  替换手工拼的女孩（`girl.py`）。
