# -*- coding: utf-8 -*-
"""验证导出结果：重导入合体 STL 渲染三视角 + SC_A2 无罩内部装配图"""
import bpy, sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from asm.build_scenes import build_everything
from mathutils import Vector

scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 0.001
scene.view_settings.view_transform = 'Standard'
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

png = os.path.join(HERE, "export", "png")

def setup_render(res=(1920, 1080)):
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x, scene.render.resolution_y = res
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.949, 0.953, 0.961, 1.0)
    bg.inputs[1].default_value = 0.7
    sun = bpy.data.lights.new("S", 'SUN'); sun.energy = 2.5
    so = bpy.data.objects.new("S", sun); scene.collection.objects.link(so)
    so.rotation_euler = Vector((-0.45, -0.65, 1.0)).to_track_quat('Z', 'Y').to_euler()

def aim(cam, loc, target, ortho=None, lens=50):
    cd = bpy.data.cameras.new("c"); cd.clip_start = 5; cd.clip_end = 1e6
    if ortho: cd.type = 'ORTHO'; cd.ortho_scale = ortho
    else: cd.lens = lens
    cam.data = cd
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

def shoot(cam_ob, fname):
    scene.camera = cam_ob
    scene.render.filepath = os.path.join(png, fname)
    bpy.ops.render.render(write_still=True)
    print("[VERIFY] saved", fname)

# ---- 1) 重导入合体 STL（查看器等效视角）----
setup_render()
bpy.ops.wm.stl_import(filepath=os.path.join(HERE, "export", "stl", "sc_a_merged.stl"))
ob = [o for o in bpy.data.objects if o.type == 'MESH'][0]
ob.data.materials.append(bpy.data.materials.new("M"))
ob.data.materials[0].use_nodes = True
ob.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.24, 0.27, 0.31, 1)
def make_cam(name, loc, target, ortho=None, lens=50):
    cd = bpy.data.cameras.new(name); cd.clip_start = 5; cd.clip_end = 1e6
    if ortho: cd.type = 'ORTHO'; cd.ortho_scale = ortho
    else: cd.lens = lens
    c = bpy.data.objects.new(name, cd); scene.collection.objects.link(c)
    c.location = loc
    c.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return c

cam = make_cam("vcam_side", (4000, -22000, 560), (4000, 0, 560), ortho=8800)
shoot(cam, "verify_merged_side.png")
cam = make_cam("vcam_top", (4000, 0, 22000), (4000, 0, 0), ortho=8800)
shoot(cam, "verify_merged_top.png")
cam = make_cam("vcam_axo", (-2600, -7500, 4600), (4100, 0, 450), lens=50)
shoot(cam, "verify_merged_axo.png")
bpy.data.objects.remove(ob, do_unlink=True)

# ---- 2) SC_A2 隐藏整流罩：内部装配（无人机骑乘位）----
ctx = build_everything(scene)
for cname in ("SC_A", "SC_SEP", "SC_C1", "SC_C2"):
    ctx["colls"][cname].hide_render = True
for o in bpy.data.objects:
    if o.name.startswith("FA_"):
        o.hide_render = True
cam2 = bpy.data.objects.get("cam_a2_axo")
scene.camera = cam2
scene.render.filepath = os.path.join(png, "verify_assembly_nofairing_axo.png")
bpy.ops.render.render(write_still=True)
print("[VERIFY] saved verify_assembly_nofairing_axo.png")
cam3 = bpy.data.objects.get("cam_a2_side")
scene.camera = cam3
scene.render.filepath = os.path.join(png, "verify_assembly_nofairing_side.png")
bpy.ops.render.render(write_still=True)
print("[VERIFY] done all")
