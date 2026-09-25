#!/bin/sh
# 下载动森（New Horizons）官方渲染图作建模参考（来源 Nookipedia，版权归任天堂，不提交进仓库）
cd "$(dirname "$0")"
UA="Mozilla/5.0"
for u in \
  https://dodo.ac/np/images/d/dd/Player_1_NH.png \
  https://dodo.ac/np/images/7/76/Player_2_NH.png \
  https://dodo.ac/np/images/e/e4/Player_4_NH.png \
  https://dodo.ac/np/images/1/17/Player_5_NH.png \
  https://dodo.ac/np/images/d/d6/NH_Eyes_Selection.jpg \
  https://dodo.ac/np/images/d/df/NH_Nose_Mouth_Selection.jpg \
  https://dodo.ac/np/images/f/f5/Isabelle_NH_Transparent.png \
  https://dodo.ac/np/images/a/a0/Isabelle_NH_Model.png \
  https://dodo.ac/np/images/e/e3/Tom_Nook_NH.png \
  https://dodo.ac/np/images/8/8c/Tom_Nook_NH_Model.png
do
  curl -sSL -A "$UA" -O "$u"
done
