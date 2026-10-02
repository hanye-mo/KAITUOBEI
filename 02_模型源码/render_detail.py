# -*- coding: utf-8 -*-
"""V5 细节特写预览：临时相机拍特写
用法: blender --background thunder.blend --python render_detail.py -- <shot>...
"""
import bpy
import sys
import os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
try:
    scene.eevee.shadow_pool_size = 8192
except Exception:
    pass

# (名称, 状态集合, 相机位置, 目标, 镜头)
SHOTS = {
    # 锐矛：尾部喷口+襟副翼+整流罩（C1）
    "c1_tail":   ("SC_C1", (5600, -2200, 1300), (4350, 0, 200), 55),
    "c1_midtop": ("SC_C1", (2050, -1900, 1250), (1150, 120, 350), 55),   # 检修口盖+紧固件
    "c1_nose":   ("SC_C1", (-200, -800, 650), (300, 0, 80), 50),        # 鼻尖TPS+RCS+工艺缝
    "c1_bottom": ("SC_C1", (3600, -1400, -1400), (3600, 0, 0), 50),     # 底部喷口+纵缝+滚转RCS
    # 影刃：背部细节（C2 展开态，安装位 2700-4500）
    "c2_topdet": ("SC_C2", (3050, -1500, 1450), (3350, 0, 930), 50),   # 锯齿舱门+传感器窗+RCS+格栅
    "c2_tail":   ("SC_C2", (5200, -1000, 1500), (4350, 0, 870), 50),   # 排气槽+SERN+垂尾根罩+副翼
    "c2_belly":  ("SC_C2", (3000, -1300, 150), (3480, 0, 660), 45),    # 进气道+隔道
    "c2_nose":   ("SC_C2", (2450, -800, 950), (2900, 0, 820), 50),     # 鼻尖+空速管
    "c1_over":   ("SC_C1", (3300, -5200, 2200), (1800, 0, 200), 50),   # C1 中段整体
}
out = os.path.join(HERE, "export", "detail")
os.makedirs(out, exist_ok=True)

for arg in argv:
    cname, loc, tgt, lens = SHOTS[arg]
    for c in bpy.data.collections:
        if c.name.startswith("SC_"):
            c.hide_render = (c.name != cname)
    cam = bpy.data.cameras.new("tmp_" + arg)
    cam.lens = lens
    cam.clip_start = 10.0
    cam.clip_end = 100000.0
    co = bpy.data.objects.new("tmp_" + arg, cam)
    scene.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = co
    scene.render.filepath = os.path.join(out, arg + ".png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(co, do_unlink=True)
    print("[DETAIL OK]", arg)
