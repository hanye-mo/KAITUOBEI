# -*- coding: utf-8 -*-
"""S6 场景装配：Collection 实例化 + SC_SEP 分离关键帧动画 + 相机/灯光/世界"""
import bpy
import math
from mathutils import Matrix, Vector

from lib import params as P
from asm.materials import build_all as build_mats
from builders import missile, uav, bracket, fairing, booster


def _empty(name, loc=(0, 0, 0)):
    ob = bpy.data.objects.new(name, None)
    ob.location = loc
    return ob


def _inst(src, coll, parent=None, name=None):
    ob = src.copy()
    ob.name = name or (src.name + "_i")
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
    return ob


def _camera(coll, name, loc, target, ortho=None, lens=50.0):
    cd = bpy.data.cameras.new(name)
    cd.clip_start = 10.0
    cd.clip_end = 500000.0
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
    ob = bpy.data.objects.new(name, cd)
    coll.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob


def _kf_lin(ob):
    if ob.animation_data and ob.animation_data.action:
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def build_world_and_lights(scene):
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.949, 0.953, 0.961, 1.0)
        bg.inputs[1].default_value = 0.45
    root = scene.collection
    sun = bpy.data.lights.new("SunKey", 'SUN')
    sun.energy = 1.05                     # V4：无 probe_sun 后的全局重校
    sun.angle = math.radians(5)
    so = bpy.data.objects.new("SunKey", sun)
    root.objects.link(so)
    so.rotation_euler = Vector((-0.45, -0.8, 1.0)).to_track_quat('Z', 'Y').to_euler()
    sun2 = bpy.data.lights.new("SunFill", 'SUN')
    sun2.energy = 0.40
    so2 = bpy.data.objects.new("SunFill", sun2)
    root.objects.link(so2)
    so2.rotation_euler = Vector((0.6, -0.5, 0.7)).to_track_quat('Z', 'Y').to_euler()
    sun3 = bpy.data.lights.new("SunRim", 'SUN')
    sun3.energy = 0.5
    so3 = bpy.data.objects.new("SunRim", sun3)
    root.objects.link(so3)
    so3.rotation_euler = Vector((0.15, 0.9, 0.8)).to_track_quat('Z', 'Y').to_euler()


def build_everything(scene):
    mats = build_mats()
    root = scene.collection

    colls = {}
    for nm in ("PARTS", "SC_A", "SC_A2", "SC_SEP", "SC_C1", "SC_C2"):
        c = bpy.data.collections.new(nm)
        root.children.link(c)
        colls[nm] = c
    colls["PARTS"].hide_render = True
    PARTS = colls["PARTS"]

    # ---------- 部件网格（建在 PARTS）----------
    rm = missile.build(PARTS, mats)
    yr = uav.build(PARTS, mats)
    br1 = bracket.build(P.BR_X1, PARTS, mats)
    br2 = bracket.build(P.BR_X2, PARTS, mats)
    brs = [br1, br2] + [o for o in PARTS.objects if o.name.startswith("BR_") and "boss" in o.name]
    fa = fairing.build(PARTS, mats)
    bo = booster.build(PARTS, mats)

    rm_parts = [o for o in (rm["body"], rm.get("engcone"), rm.get("nozcone"), rm["elevons"],
                            rm.get("fairings"), rm.get("panels"), rm.get("dots"), rm.get("rcs"),
                            rm.get("lebeads"),
                            rm.get("tipwing_r"), rm.get("tipwing_l")) if o]
    yr_parts = [o for o in (yr["body"], yr.get("intakelip"), yr.get("sernramp"),
                            yr.get("exhinsert"), yr.get("door"), yr.get("blister"),
                            yr.get("rcs"), yr.get("aux"), yr.get("bld"), yr.get("vtfair"),
                            yr.get("hingestrip"), yr.get("pitot"),
                            yr["vt_r"], yr["vt_l"], yr["wing_r"], yr["wing_l"],
                            yr.get("el_r"), yr.get("el_l")) if o]
    bo_parts = [bo["tran"], bo["frame"], bo["skirt"]] + bo.get("fins", []) + \
               [o for o in PARTS.objects if o.name.startswith("BO_Nozzle")]

    def make_state(nm, with_bo, fa_motion=False):
        c = colls[nm]
        rig_rm = _empty("RM_Rig_" + nm)
        c.objects.link(rig_rm)
        for o in rm_parts:
            _inst(o, c, parent=rig_rm)
        rig_yr = _empty("YR_Rig_" + nm, P.YR_INSTALL)
        c.objects.link(rig_yr)
        for o in yr_parts:
            _inst(o, c, parent=rig_yr)
        for o in brs:
            _inst(o, c)
        for key in ("fa_l", "fa_r"):
            _inst(fa[key], c)
        if with_bo:
            for o in bo_parts:
                _inst(o, c)
        return rig_rm, rig_yr

    # SC_A / SC_A2（静置）
    make_state("SC_A", True)
    make_state("SC_A2", False)

    # SC_SEP：K0–K5 关键帧
    rig_rm, rig_yr = make_state("SC_SEP", False)
    faL = [o for o in colls["SC_SEP"].objects if o.name.startswith("FA_L")][0]
    faR = [o for o in colls["SC_SEP"].objects if o.name.startswith("FA_R")][0]
    wR = [o for o in colls["SC_SEP"].objects if o.name.startswith("YW_R")][0]
    wL = [o for o in colls["SC_SEP"].objects if o.name.startswith("YW_L")][0]
    elR = [o for o in colls["SC_SEP"].objects if o.name.startswith("YW_ElR")][0]
    elL = [o for o in colls["SC_SEP"].objects if o.name.startswith("YW_ElL")][0]
    K = P.K_FRAMES
    pvL, pvR = Vector((3275.0, -550.0, 600.0)), Vector((3275.0, 550.0, 600.0))
    dL = Vector((P.K1_FA_DX, -P.K1_FA_DY, P.K1_FA_DZ))
    dR = Vector((P.K1_FA_DX, P.K1_FA_DY, P.K1_FA_DZ))
    HOLD1, HOLD2 = 36, 84                      # 抛罩前/解锁前保持帧
    # 罩瓣：36-66 大行程抛离（外+上+后甩，翻滚 50°），66-168 气动漂移远去（翻滚 80°）
    for ob, pv, d, rz in ((faL, pvL, dL, -P.K1_FA_ROT), (faR, pvR, dR, P.K1_FA_ROT)):
        ob.location = tuple(pv); ob.rotation_euler = (0, 0, 0)
        for fr in (0, HOLD1):
            ob.keyframe_insert("location", frame=fr); ob.keyframe_insert("rotation_euler", frame=fr)
        ob.location = tuple(pv + d); ob.rotation_euler = (0, 0, math.radians(rz))
        ob.keyframe_insert("location", frame=K["K1"]); ob.keyframe_insert("rotation_euler", frame=K["K1"])
        dr = Vector(P.K1_FA_DRIFT)
        ob.location = tuple(pv + Vector((P.K1_FA_DX * 0.4, 0, 0)) + dr)
        ob.rotation_euler = (math.radians(P.K1_FA_ROT2 * 0.4), 0, math.radians(rz * 1.6))
        ob.keyframe_insert("location", frame=K["K3"]); ob.keyframe_insert("rotation_euler", frame=K["K3"])
        ob.location = tuple(pv + Vector((P.K1_FA_DX * 0.4, 0, 0)) + dr * 1.35)
        ob.keyframe_insert("location", frame=K["END"])
    yr_base = Vector(P.YR_INSTALL)
    for f, d in ((0, None), (HOLD2, None), (K["K2"], P.K2_YR_D), (138, P.K2_YR_D),
                 (K["K3"], P.K3_YR_D), (K["K4"], P.K4_YR_D), (K["END"], P.K4_YR_D)):
        rig_yr.location = tuple(yr_base + (Vector(d) if d else Vector((0, 0, 0))))
        rig_yr.keyframe_insert("location", frame=f)
    # 翼面：分离全程收拢（0-168），清场后 168-228 缓慢展开（60帧=2.5s）；升降副翼同步折叠
    for w, sgn in ((wR, 1), (wL, -1), (elR, 1), (elL, -1)):
        for f, ang in ((0, P.YW_FOLD_STOW), (K["K3"], P.YW_FOLD_STOW), (198, P.YW_FOLD_MID),
                       (K["K4"], 0.0), (K["END"], 0.0)):
            w.rotation_euler = (math.radians(ang * sgn), 0, 0)
            w.keyframe_insert("rotation_euler", frame=f)
    for f, d in ((0, (0, 0, 0)), (210, (0, 0, 0)), (K["K5"], P.K5_RM_D), (K["END"], P.K5_RM_D)):
        rig_rm.location = d
        rig_rm.keyframe_insert("location", frame=f)
    for ob in (faL, faR, rig_yr, rig_rm, wR, wL, elR, elL):
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
    _kf_lin(py)
    # 分离相机编排：近景开场 → 跟抛罩 → 跟无人机展开 → 大远景收尾
    axo = bpy.data.objects.get("cam_sep_axo")
    if axo:
        for f, loc, tgt in ((0, (3400, -11500, 3400), (4000, 0, 500)),
                            (K["K1"] - 30, (2900, -7800, 3000), (3300, 0, 600)),
                            (K["K1"], (2400, -5600, 2600), (3200, 0, 700)),
                            (K["K2"], (1700, -6800, 3600), (3100, 100, 800)),
                            (K["K3"], (600, -8200, 4400), (2900, 200, 950)),
                            (K["K4"], (-900, -10300, 5500), (2400, 300, 1000)),
                            (K["K5"], (-1600, -11800, 6100), (1500, 200, 950)),
                            (K["END"], (-2200, -13200, 6600), (500, 100, 900))):
            axo.location = loc
            axo.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
            axo.keyframe_insert("location", frame=f)
            axo.keyframe_insert("rotation_euler", frame=f)
        _kf_lin(axo)
    side = bpy.data.objects.get("cam_sep_side")
    if side and side.data.type == 'ORTHO':
        side.data.ortho_scale = 6200
        side.data.keyframe_insert("ortho_scale", frame=0)
        side.data.ortho_scale = 8200
        side.data.keyframe_insert("ortho_scale", frame=K["K4"])
        side.data.ortho_scale = 11500
        side.data.keyframe_insert("ortho_scale", frame=K["END"])

    # SC_C1 / SC_C2
    c1 = colls["SC_C1"]
    rig1 = _empty("RM_Rig_C1")
    c1.objects.link(rig1)
    rig1.rotation_euler = (0, math.radians(-6), 0)
    for o in rm_parts:
        inst = _inst(o, c1, parent=rig1)
        if o.name == "RM_Elevons":
            inst.rotation_euler = (0, math.radians(8), 0)   # 襟副翼 -8°（TE down）
    c2 = colls["SC_C2"]
    rig2 = _empty("YR_Rig_C2", P.YR_INSTALL)
    c2.objects.link(rig2)
    rig2.rotation_euler = (0, math.radians(-9), 0)
    for o in yr_parts:
        inst = _inst(o, c2, parent=rig2)
        if o.name.startswith("YW_El"):
            inst.rotation_euler = (0, math.radians(P.YR_EL_DEFLECT), 0)   # 升降副翼 −10°（§3.6）
        elif o.name.startswith("YW_"):
            inst.rotation_euler = (0, 0, 0)                 # 外翼展开

    # ---------- 相机 ----------
    A = colls["SC_A"]
    _camera(A, "cam_a_front", (-12000, 0, 560), (4025, 0, 560), ortho=3300)
    _camera(A, "cam_a_side", (4025, -22000, 560), (4025, 0, 560), ortho=8800)
    _camera(A, "cam_a_top", (4025, 0, 22000), (4025, 0, 0), ortho=8800)
    _camera(A, "cam_a_axo1", (-2500, -7000, 4300), (4025, 0, 500), lens=50)
    _camera(A, "cam_a_axo2", (10600, -6200, 2700), (4600, 0, 500), lens=50)
    A2 = colls["SC_A2"]
    _camera(A2, "cam_a2_side", (2275, -16000, 560), (2275, 0, 560), ortho=5300)
    _camera(A2, "cam_a2_axo", (-2400, -5600, 3600), (2300, 0, 500), lens=50)
    _camera(A2, "cam_a2_front", (-8000, 0, 560), (2275, 0, 560), ortho=3300)
    _camera(A2, "cam_a2_top", (2275, 0, 16000), (2275, 0, 0), ortho=5300)
    S = colls["SC_SEP"]
    _camera(S, "cam_sep_side", (3000, -18000, 800), (3000, 300, 750), ortho=6000)
    _camera(S, "cam_sep_axo", (300, -6200, 3500), (3100, 300, 750), lens=45)
    C1 = colls["SC_C1"]
    _camera(C1, "cam_c1_front", (-10000, 0, 300), (2250, 0, 300), ortho=3200)
    _camera(C1, "cam_c1_side", (2250, -14000, 300), (2250, 0, 300), ortho=5200)
    _camera(C1, "cam_c1_top", (2250, 0, 14000), (2250, 0, 0), ortho=5200)
    _camera(C1, "cam_c1_axo", (7600, -4800, 2700), (2500, 0, 420), lens=55)   # 尾右上：示尾端面喷口/襟副翼/小翼
    C2 = colls["SC_C2"]
    _camera(C2, "cam_c2_front", (3300 - 7600, 0, 800), (3300, 0, 800), ortho=2400)
    _camera(C2, "cam_c2_side", (3300, -9600, 800), (3300, 0, 800), ortho=2600)
    _camera(C2, "cam_c2_top", (3300, 0, 9600), (3300, 0, 760), ortho=2600)
    _camera(C2, "cam_c2_axo", (2450, -3500, 1800), (3680, 0, 800), lens=50)

    # 平滑着色（按 35° 角拆边：平底/甲板边缘保持硬边）
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
            "brs": brs, "colls": colls}
