# -*- coding: utf-8 -*-
"""V3 动画补丁：大幅化抛离动作 + 尾焰特效 + 相机编排 + 300 帧时序"""
import io
import ast

# 1) params.py: V3 时序与抛离幅度
p = "lib/params.py"
s = io.open(p, encoding="utf-8").read()
old = """# [V2 可信时序] 分离瞬间不变形：抛罩→推离→收拢清场→缓慢展开→脉冲脱离
K_FRAMES = {"K0": 0, "K1": 30, "K2": 60, "K3": 100, "K4": 150, "K5": 190, "END": 240}"""
new = """# [V3 时序 300帧@24fps=12.5s] 分离瞬间不变形：抛罩(36-66)→推离(84-120)→清场(168)→
# 缓慢展开(168-228)→导弹脉冲(240-270)→编队(300)；尾焰 f210/240 点燃
K_FRAMES = {"K0": 0, "K1": 66, "K2": 120, "K3": 168, "K4": 228, "K5": 270, "END": 300}"""
assert old in s; s = s.replace(old, new)
old = """K1_FA_DY, K1_FA_DZ, K1_FA_DX, K1_FA_ROT = 300.0, 120.0, -450.0, 18.0
K2_YR_D = (0.0, 120.0, 180.0)
K3_YR_D = (0.0, 240.0, 360.0)
K4_YR_D = (-600.0, 900.0, 400.0)
K5_RM_D = (-2500.0, 0.0, 0.0)"""
new = """K1_FA_DY, K1_FA_DZ, K1_FA_DX, K1_FA_ROT = 1600.0, 500.0, -1200.0, 50.0
K1_FA_DRIFT, K1_FA_ROT2 = (-3200.0, 2800.0, 1000.0), 80.0   # 后续气动漂移（翻滚加大）
K2_YR_D = (0.0, 150.0, 260.0)
K3_YR_D = (-500.0, 600.0, 500.0)
K4_YR_D = (-1800.0, 1200.0, 750.0)
K5_RM_D = (-3500.0, 0.0, 0.0)
PLUME_MS = dict(x0=4520.0, z0=325.0, L=2600.0, r0=170.0, r1=430.0)   # 导弹脉冲尾焰
PLUME_YR = dict(x0=1800.0, z0=124.0, L=1500.0, r0=90.0, r1=230.0)   # 影刃超燃尾焰（局部系）
PLUME_FIRE_MS, PLUME_FIRE_YR = 214.0, 244.0                          # 点燃帧"""
assert old in s; s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)

# 2) materials.py: 尾焰材质（发光半透明）
p = "asm/materials.py"
s = io.open(p, encoding="utf-8").read()
old = """        "FLOW":     _mat("M_FLOW",     0x7FA8D9, 0.30, 0.00, alpha=0.25),
    }"""
new = """        "FLOW":     _mat("M_FLOW",     0x7FA8D9, 0.30, 0.00, alpha=0.25),
        "PLUME":    _plume("M_PLUME"),
    }"""
assert old in s; s = s.replace(old, new)
old = """def build_all():"""
new = """def _plume(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (1.0, 0.62, 0.25, 1.0)
        bsdf.inputs["Alpha"].default_value = 0.30
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (1.0, 0.55, 0.18, 1.0)
            bsdf.inputs["Emission Strength"].default_value = 9.0
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (1.0, 0.55, 0.18, 1.0)
    m.blend_method = 'BLEND'
    m.diffuse_color = (1.0, 0.6, 0.25, 0.30)
    return m


def build_all():"""
assert old in s; s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)

# 3) build_scenes.py: V3 关键帧 + 尾焰 + 相机编排
p = "asm/build_scenes.py"
s = io.open(p, encoding="utf-8").read()

old = """    HOLD1, HOLD2 = 24, 54                      # 各阶段保持帧
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
        rig_rm.keyframe_insert("location", frame=f)"""
new = """    HOLD1, HOLD2 = 36, 84                      # 抛罩前/解锁前保持帧
    # 罩瓣：36-66 大行程抛离（外+上+后甩，翻滚 50°），66-168 气动漂移远去（翻滚 80°）
    for ob, pv, d, rz in ((faL, pvL, dL, -P.K1_FA_ROT), (faR, pvR, dR, P.K1_FA_ROT)):
        ob.location = tuple(pv); ob.rotation_euler = (0, 0, 0)
        for fr in (0, HOLD1):
            ob.keyframe_insert("location", frame=fr); ob.keyframe_insert("rotation_euler", frame=fr)
        ob.location = tuple(pv + d); ob.rotation_euler = (0, 0, math.radians(rz))
        ob.keyframe_insert("location", frame=K["K1"]); ob.keyframe_insert("rotation_euler", frame=K["K1"])
        dr = Vector(P.K1_FA_DRIFT)
        ob.location = tuple(pv + Vector(P.K1_FA_DX * 0.4, 0, 0) + dr)
        ob.rotation_euler = (math.radians(P.K1_FA_ROT2 * 0.4), 0, math.radians(rz * 1.6))
        ob.keyframe_insert("location", frame=K["K3"]); ob.keyframe_insert("rotation_euler", frame=K["K3"])
        ob.location = tuple(pv + Vector(P.K1_FA_DX * 0.4, 0, 0) + dr * 1.35)
        ob.keyframe_insert("location", frame=K["END"])
    yr_base = Vector(P.YR_INSTALL)
    for f, d in ((0, None), (HOLD2, None), (K["K2"], P.K2_YR_D), (138, P.K2_YR_D),
                 (K["K3"], P.K3_YR_D), (K["K4"], P.K4_YR_D), (K["END"], P.K4_YR_D)):
        rig_yr.location = tuple(yr_base + (Vector(d) if d else Vector((0, 0, 0))))
        rig_yr.keyframe_insert("location", frame=f)
    # 翼面：分离全程收拢（0-168），清场后 168-228 缓慢展开（60帧=2.5s）
    for w, sgn in ((wR, 1), (wL, -1)):
        for f, ang in ((0, P.YW_FOLD_STOW), (K["K3"], P.YW_FOLD_STOW), (198, P.YW_FOLD_MID),
                       (K["K4"], 0.0), (K["END"], 0.0)):
            w.rotation_euler = (math.radians(ang * sgn), 0, 0)
            w.keyframe_insert("rotation_euler", frame=f)
    for f, d in ((0, (0, 0, 0)), (210, (0, 0, 0)), (K["K5"], P.K5_RM_D), (K["END"], P.K5_RM_D)):
        rig_rm.location = d
        rig_rm.keyframe_insert("location", frame=f)"""
assert old in s, "kf v3"
s = s.replace(old, new)

# 尾焰（SC_SEP 内建，跟随各自刚体）
old = """    for ob in (faL, faR, rig_yr, rig_rm, wR, wL):
        _kf_lin(ob)"""
new = """    for ob in (faL, faR, rig_yr, rig_rm, wR, wL):
        _kf_lin(ob)

    # ---- 尾焰特效（半透明发光锥，点火帧缩放展开）----
    from builders.common import MB, to_object as _to
    def plume(spec, name, local, parent):
        mb = MB()
        x0, z0, L, r0, r1 = spec["x0"], spec["z0"], spec["L"], spec["r0"], spec["r1"]
        rings = []
        for k in range(9):
            t = k / 8.0
            rr = r0 + (r1 - r0) * t
            rings.append([(x0 + L * t, rr * math.cos(2 * math.pi * j / 24.0),
                           z0 + rr * math.sin(2 * math.pi * j / 24.0)) for j in range(24)])
        mb.loft([rings[0], rings[-1]], cap_start=True, cap_end=False)
        ob = _to(mb, name, colls["SC_SEP"], mats["PLUME"])
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.scale = (0.001, 0.001, 0.001)
        ob.keyframe_insert("scale", frame=0)
        ob.scale = (1.0, 1.0, 1.0)
        return ob
    pm = plume(P.PLUME_MS, "PLUME_MS", False, rig_rm)
    pm.keyframe_insert("scale", frame=P.PLUME_FIRE_MS - 6)
    pm.keyframe_insert("scale", frame=P.PLUME_FIRE_MS)
    pm.keyframe_insert("scale", frame=K["END"])
    _kf_lin(pm)
    py = plume(P.PLUME_YR, "PLUME_YR", True, rig_yr)
    py.keyframe_insert("scale", frame=P.PLUME_FIRE_YR - 6)
    py.keyframe_insert("scale", frame=P.PLUME_FIRE_YR)
    py.keyframe_insert("scale", frame=K["END"])
    _kf_lin(py)"""
assert old in s, "plume v3"
s = s.replace(old, new)

# 相机编排：跟踪+后撤
old = """    # 分离相机同步拉远（跟住逐渐扩大的两队）
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
        _kf_lin(axo)"""
new = """    # 分离相机编排：近景开场 → 跟抛罩 → 跟无人机展开 → 大远景收尾
    axo = bpy.data.objects.get("cam_sep_axo")
    if axo:
        tgt = Vector((3400, 0, 650))
        for f, loc in ((0, (2200, -4600, 2300)), (K["K1"], (2600, -5600, 2900)),
                       (K["K2"], (1600, -6800, 3600)), (K["K3"], (600, -8200, 4400)),
                       (K["K4"], (-800, -10200, 5400)), (K["END"], (-2200, -13200, 6600))):
            axo.location = loc
            axo.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
            axo.keyframe_insert("location", frame=f)
            axo.keyframe_insert("rotation_euler", frame=f)
        _kf_lin(axo)"""
assert old in s, "cam v3"
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)

# 4) build_all.py: MP4 帧范围走 params END
p = "build_all.py"
s = io.open(p, encoding="utf-8").read()
old = "    scene.frame_start, scene.frame_end = 0, P.K_FRAMES[\"END\"]"
assert old in s
print("v3 patch ok")
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(io.open(p, encoding="utf-8").read())
