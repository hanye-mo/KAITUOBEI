# -*- coding: utf-8 -*-
"""补丁：动画重定时 + 相机拉远 + 平滑着色 + 装配图相机/渲染

经 lib.patchutil.apply 执行：路径相对源码根目录（02_模型源码），与当前工作目录无关；
全部锚点命中且语法校验通过后一次性落盘，任一失败不写任何文件（无半修改状态）；
已应用过的锚点自动跳过，脚本可重复执行。
"""
from lib.patchutil import apply

JOBS = [
    # 1) build_scenes.py
    ("asm/build_scenes.py", [
        ("smooth anchor",
         """    build_world_and_lights(scene)
    return {"mats": mats, "rm": rm, "yr": yr, "fa": fa, "bo": bo,
            "brs": brs, "colls": colls}""",
         """    # 平滑着色（按 35° 角拆边：平底/甲板边缘保持硬边）
    for me in bpy.data.meshes:
        for p_ in me.polygons:
            p_.use_smooth = True
    try:
        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                with bpy.context.temp_override(active_object=ob, object=ob,
                                               selected_editable_objects=[ob], selected_objects=[ob]):
                    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
    except Exception as e:
        print("[SMOOTH] by-angle fallback:", e)

    build_world_and_lights(scene)
    return {"mats": mats, "rm": rm, "yr": yr, "fa": fa, "bo": bo,
            "brs": brs, "colls": colls}""", "shade_smooth_by_angle"),
        ("kf anchor",
         """    for ob, pv, d, rz in ((faL, pvL, dL, -P.K1_FA_ROT), (faR, pvR, dR, P.K1_FA_ROT)):
        ob.location = tuple(pv)
        ob.keyframe_insert("location", frame=K["K0"])
        ob.keyframe_insert("rotation_euler", frame=K["K0"])
        ob.location = tuple(pv)
        ob.keyframe_insert("location", frame=6)
        ob.location = tuple(pv + d)
        ob.rotation_euler = (0, 0, math.radians(rz))
        ob.keyframe_insert("location", frame=K["K1"])
        ob.keyframe_insert("rotation_euler", frame=K["K1"])
        ob.keyframe_insert("location", frame=K["END"])
        ob.keyframe_insert("rotation_euler", frame=K["END"])
    yr_base = Vector(P.YR_INSTALL)
    for f, d in ((K["K0"], None), (18, None), (K["K2"], P.K2_YR_D), (30, P.K2_YR_D),
                 (K["K3"], P.K3_YR_D), (42, P.K3_YR_D), (K["K4"], P.K4_YR_D), (K["END"], P.K4_YR_D)):
        rig_yr.location = tuple(yr_base + (Vector(d) if d else Vector((0, 0, 0))))
        rig_yr.keyframe_insert("location", frame=f)
    for w, sgn in ((wR, 1), (wL, -1)):
        for f, ang in ((K["K0"], P.YW_FOLD_STOW), (K["K2"], P.YW_FOLD_STOW),
                       (K["K3"], P.YW_FOLD_MID), (K["K4"], 0.0), (K["END"], 0.0)):
            w.rotation_euler = (math.radians(ang * sgn), 0, 0)
            w.keyframe_insert("rotation_euler", frame=f)
    for f, d in ((K["K0"], (0, 0, 0)), (54, (0, 0, 0)), (K["K5"], P.K5_RM_D), (K["END"], P.K5_RM_D)):
        rig_rm.location = d
        rig_rm.keyframe_insert("location", frame=f)""",
         """    HOLD1, HOLD2 = 24, 54                      # 各阶段保持帧
    for ob, pv, d, rz in ((faL, pvL, dL, -P.K1_FA_ROT), (faR, pvR, dR, P.K1_FA_ROT)):
        ob.location = tuple(pv); ob.rotation_euler = (0, 0, 0)
        ob.keyframe_insert("location", frame=0); ob.keyframe_insert("rotation_euler", frame=0)
        ob.keyframe_insert("location", frame=HOLD1); ob.keyframe_insert("rotation_euler", frame=HOLD1)
        ob.location = tuple(pv + d); ob.rotation_euler = (0, 0, math.radians(rz))
        ob.keyframe_insert("location", frame=K["K1"]); ob.keyframe_insert("rotation_euler", frame=K["K1"])
        ob.keyframe_insert("location", frame=K["END"]); ob.keyframe_insert("rotation_euler", frame=K["END"])
    yr_base = Vector(P.YR_INSTALL)
    for f, d in ((0, None), (HOLD2, None), (K["K2"], P.K2_YR_D), (72, P.K2_YR_D),
                 (K["K3"], P.K3_YR_D), (102, P.K3_YR_D), (K["K4"], P.K4_YR_D), (K["END"], P.K4_YR_D)):
        rig_yr.location = tuple(yr_base + (Vector(d) if d else Vector((0, 0, 0))))
        rig_yr.keyframe_insert("location", frame=f)
    for w, sgn in ((wR, 1), (wL, -1)):
        for f, ang in ((0, P.YW_FOLD_STOW), (66, P.YW_FOLD_STOW), (K["K3"], P.YW_FOLD_MID),
                       (K["K4"], 0.0), (K["END"], 0.0)):
            w.rotation_euler = (math.radians(ang * sgn), 0, 0)
            w.keyframe_insert("rotation_euler", frame=f)
    for f, d in ((0, (0, 0, 0)), (138, (0, 0, 0)), (K["K5"], P.K5_RM_D), (K["END"], P.K5_RM_D)):
        rig_rm.location = d
        rig_rm.keyframe_insert("location", frame=f)""", "HOLD2"),
        ("cam anchor",
         """    for ob in (faL, faR, rig_yr, rig_rm, wR, wL):
        _kf_lin(ob)""",
         """    for ob in (faL, faR, rig_yr, rig_rm, wR, wL):
        _kf_lin(ob)
    # 分离相机同步拉远（跟住逐渐扩大的两队）
    axo = bpy.data.objects.get("cam_sep_axo")
    if axo:
        axo.location = (500, -5000, 3000)
        axo.keyframe_insert("location", frame=0)
        axo.location = (900, -6200, 3600)
        axo.keyframe_insert("location", frame=K["K2"])
        axo.location = (-1500, -9500, 5200)
        axo.keyframe_insert("location", frame=K["K5"])
        axo.location = (-2600, -11500, 6200)
        axo.keyframe_insert("location", frame=K["END"])
        _kf_lin(axo)
    side = bpy.data.objects.get("cam_sep_side")
    if side and side.data.type == 'ORTHO':
        side.data.ortho_scale = 6200
        side.data.keyframe_insert("ortho_scale", frame=0)
        side.data.ortho_scale = 8200
        side.data.keyframe_insert("ortho_scale", frame=K["K4"])
        side.data.ortho_scale = 11500
        side.data.keyframe_insert("ortho_scale", frame=K["END"])""", "ortho_scale"),
        ("a2cam anchor",
         """    A2 = colls["SC_A2"]
    _camera(A2, "cam_a2_side", (2275, -16000, 560), (2275, 0, 560), ortho=5300)
    _camera(A2, "cam_a2_axo", (-2400, -5600, 3600), (2300, 0, 500), lens=50)""",
         """    A2 = colls["SC_A2"]
    _camera(A2, "cam_a2_side", (2275, -16000, 560), (2275, 0, 560), ortho=5300)
    _camera(A2, "cam_a2_axo", (-2400, -5600, 3600), (2300, 0, 500), lens=50)
    _camera(A2, "cam_a2_front", (-8000, 0, 560), (2275, 0, 560), ortho=3300)
    _camera(A2, "cam_a2_top", (2275, 0, 16000), (2275, 0, 0), ortho=5300)""", "cam_a2_top"),
    ]),
    # 2) build_all.py：装配图渲染
    ("build_all.py", [
        ("shots anchor",
         """    shots += [("SC_A2", 0, "cam_a2_side", "sc_a2_side"), ("SC_A2", 0, "cam_a2_axo", "sc_a2_axo")]""",
         """    shots += [("SC_A2", 0, "cam_a2_side", "sc_a2_side"), ("SC_A2", 0, "cam_a2_axo", "sc_a2_axo")]
    # 装配图（隐藏整流罩，三视图 + 轴测）
    for cam, fname in (("cam_a2_front", "assembly_front"), ("cam_a2_side", "assembly_side"),
                       ("cam_a2_top", "assembly_top"), ("cam_a2_axo", "assembly_axo")):
        shots.append(("SC_A2", 0, cam, fname))""", "assembly_front"),
        ("hide anchor",
         """    for cname, f, cam, fname in shots:
        coll = ctx["colls"][cname]
        for c in ctx["colls"].values():
            if c.name.startswith("SC_"):
                c.hide_render = (c.name != cname)
        scene.frame_set(f)""",
         """    for cname, f, cam, fname in shots:
        coll = ctx["colls"][cname]
        for c in ctx["colls"].values():
            if c.name.startswith("SC_"):
                c.hide_render = (c.name != cname)
        hide_fa = fname.startswith("assembly")
        for o in coll.objects:
            if o.name.startswith("FA_"):
                o.hide_render = hide_fa
        scene.frame_set(f)"""),
        ("unhide anchor",
         """        bpy.ops.render.render(write_still=True)
        REPORT["notes"].append(f"render {fname}: {time.time()-t0:.1f}s")
    for c in ctx["colls"].values():
        if c.name.startswith("SC_"):
            c.hide_render = False""",
         """        bpy.ops.render.render(write_still=True)
        REPORT["notes"].append(f"render {fname}: {time.time()-t0:.1f}s")
        for o in coll.objects:
            if o.name.startswith("FA_"):
                o.hide_render = False
    for c in ctx["colls"].values():
        if c.name.startswith("SC_"):
            c.hide_render = False"""),
    ]),
]

if __name__ == "__main__":
    changed = apply(JOBS, label="anim")
    print("[anim] 完成，本次改写：", changed or "无（均已应用过）")
