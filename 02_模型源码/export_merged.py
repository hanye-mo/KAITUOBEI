# -*- coding: utf-8 -*-
"""导出合体态单一实体 STL：SC_A 全部 28 个部件做 EXACT 并集链 → sc_a_merged.stl
用法: blender --background --factory-startup --python export_merged.py
"""
import bpy
import sys
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from asm.build_scenes import build_everything
from builders.common import boolean, union_bbox


def island_count(obj):
    """连通块数（按顶点共边游走）"""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    seen = set()
    stacks = []
    for v in bm.verts:
        if v.index not in seen:
            stacks.append(0)
            stack = [v]
            seen.add(v.index)
            while stack:
                cv = stack.pop()
                stacks[-1] += 1
                for e in cv.link_edges:
                    ov = e.other_vert(cv)
                    if ov.index not in seen:
                        seen.add(ov.index)
                        stack.append(ov)
    bm.free()
    return len(stacks)


def main():
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.001
    scene.unit_settings.length_unit = 'MILLIMETERS'
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    ctx = build_everything(scene)
    coll = ctx["colls"]["SC_A"]
    meshes = [o for o in coll.objects if o.type == 'MESH']
    print(f"[MERGE] SC_A mesh objects: {len(meshes)}")
    # SC_A 是链接副本（多用户数据），布尔前先转为单用户副本
    for ob in meshes:
        ob.data = ob.data.copy()

    # 并集顺序：机体打底 → 大部件 → 小件（降低 EXACT 失败概率）
    def key(ob):
        n = ob.name
        for i, pre in enumerate(("RM_Body", "BO_Body", "BO_Trans", "BO_Skirt", "FA_",
                                 "YR_Body", "YW_", "YR_VT", "YR_Inlet", "BR_", "RM_")):
            if n.startswith(pre):
                return (i, n)
        return (99, n)
    meshes.sort(key=key)

    # 纯拼接合并（零布尔）：部件间为对接/贴合关系，布尔并集会在对接壳处触发
    # EXACT 回退削掉几何（曾致裙尾丢失 41mm）；拼接保持所有壳的精确外形。
    import bmesh
    from builders.common import bbox_of
    t0 = time.time()
    bm = bmesh.new()
    for ob in meshes:
        mn, mx = bbox_of(ob)
        print(f"[MERGE] {ob.name:24s} verts={len(ob.data.vertices):6d} "
              f"x[{mn[0]:8.1f},{mx[0]:8.1f}] mw={tuple(round(v,1) for v in ob.matrix_world.translation)}")
        tmp = bmesh.new()
        tmp.from_mesh(ob.data)
        bmesh.ops.transform(tmp, matrix=ob.matrix_world.copy(), verts=tmp.verts)
        me2 = bpy.data.meshes.new("tmp_join")
        tmp.to_mesh(me2)
        tmp.free()
        if len(me2.vertices) == 0:
            print(f"[MERGE] !! EMPTY after transform: {ob.name}")
        bm.from_mesh(me2)
        bpy.data.meshes.remove(me2)
    me = bpy.data.meshes.new("STACK_MERGED")
    bm.to_mesh(me)
    bm.free()
    result = bpy.data.objects.new("STACK_MERGED", me)
    bpy.context.scene.collection.objects.link(result)
    result.name = "STACK_MERGED"
    bpy.context.view_layer.update()

    mn, mx = union_bbox([result])
    tris = sum(len(p.vertices) - 2 for p in result.data.polygons)
    print(f"[MERGE] bbox  min={tuple(round(v,1) for v in mn)}")
    print(f"[MERGE] bbox  max={tuple(round(v,1) for v in mx)}")
    print(f"[MERGE] tris={tris}  islands={island_count(result)}  time={time.time()-t0:.0f}s")

    out = os.path.join(HERE, "export", "stl", "sc_a_merged.stl")
    bpy.ops.object.select_all(action='DESELECT')
    result.select_set(True)
    bpy.context.view_layer.objects.active = result
    bpy.ops.wm.stl_export(filepath=out, export_selected_objects=True, apply_modifiers=True)
    print("[MERGE] saved:", out, os.path.getsize(out), "bytes")


main()
