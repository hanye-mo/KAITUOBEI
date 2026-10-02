# -*- coding: utf-8 -*-
"""S5 助推器：过渡段(锐矛尾截面→φ900) + 机体φ900 + 尾裙 + 双喷管(内缩) + 栅格舵×4"""
import math
from mathutils import Matrix, Vector

from builders.common import MB, to_object, boolean
from lib import params as P
from lib.profiles import arch_pts, circle_like, scaled_arch


def _circle_ring(x, r, seg=24):
    return [(x, r * math.cos(2 * math.pi * i / (2 * seg)), P.BO_AXIS_Z + r * math.sin(2 * math.pi * i / (2 * seg)))
            for i in range(2 * seg)]


def build(coll, mats):
    out = {}
    # --- 过渡段 4502→4850：锐矛尾截面 morph φ900（极角配准防扭转）---
    sec_rm = scaled_arch(1300, 850, P.RM_DECK_Z, p=P.RM_SE_P, q=P.RM_SE_Q)
    ring_a = [(4502.0, y, z) for (y, z) in sec_rm]
    ring_b = [(4850.0, y, z) for (y, z) in circle_like(sec_rm, P.BO_R, P.BO_AXIS_Z)]
    tran = to_object(MB().loft([ring_a, ring_b], cap_start=True, cap_end=True),
                     "BO_Trans", coll, mats["BO"])
    out["tran"] = tran

    # --- 机体 / 尾裙（两个独立闭合壳对象； butt 接缝在 x=7950）---
    body = to_object(MB().cyl((P.BO_BODY_X0, 0, P.BO_AXIS_Z), (P.BO_BODY_X1, 0, P.BO_AXIS_Z),
                              P.BO_R, caps=True), "BO_Body", coll, mats["BO"])
    ring_s0 = _circle_ring(P.BO_SKIRT_X0, P.BO_R)
    ring_s1 = _circle_ring(P.BO_SKIRT_X1, P.BO_SKIRT_R1)
    skirt = to_object(MB().loft([ring_s0, ring_s1], cap_start=True, cap_end=True),
                      "BO_Skirt", coll, mats["BO"])

    # --- 双喷管内缩孔（EXACT 差集；出口 φ336 [DEV#4]；逐壳横向裁剪）---
    for side in (1, -1):
        cant = math.tan(math.radians(P.BO_NOZ_CANT)) * side
        d = Vector((1.0, cant, 0.0)).normalized()
        c = Vector((P.BO_SKIRT_X1 - P.BO_NOZ_DEPTH, side * P.BO_NOZ_Y, P.BO_AXIS_Z))
        p0 = c - 60 * d
        p1 = c + 80 * d
        for tgt, nm in ((skirt, "skirt"), (body, "body")):
            tool = MB().cyl(tuple(p0), tuple(p1), P.BO_NOZ_EXIT_R)
            boolean(tgt, to_object(tool, f"BO_bore{side}_{nm}", coll), 'DIFFERENCE')
    frame = body
    # 深色喷管锥（喉 r140 → 出口 r162）
    for side in (1, -1):
        cant = math.tan(math.radians(P.BO_NOZ_CANT)) * side
        d = Vector((1.0, cant, 0.0)).normalized()
        c = Vector((P.BO_SKIRT_X1 - P.BO_NOZ_DEPTH, side * P.BO_NOZ_Y, P.BO_AXIS_Z))
        cone = MB()
        r0, r1 = 140.0, P.BO_NOZ_EXIT_R - 6
        qa = c - 55 * d
        qb = c + 65 * d
        ring_q0, ring_q1 = [], []
        for i in range(P.SEG):
            a = 2 * math.pi * i / P.SEG
            ring_q0.append(tuple(qa + r0 * Vector((0, math.cos(a), math.sin(a)))))
            ring_q1.append(tuple(qb + r1 * Vector((0, math.cos(a), math.sin(a)))))
        cone.loft([ring_q0, ring_q1], cap_start=False, cap_end=True)
        to_object(cone, f"BO_Nozzle{side}", coll, mats["NOZ"])
    out["frame"] = frame
    out["skirt"] = skirt

    # --- 栅格舵 ×4（外框+纵肋4+横肋3，X 布置 45/135/225/315°）---
    def fin_mb():
        f = MB()
        w = P.BO_GF_WALL
        L, H, T = P.BO_GF_CHORD, P.BO_GF_HEIGHT, P.BO_GF_T
        f.box(0, -H / 2 + w / 2, 0, L, w, T)            # 根部板
        f.box(0, H / 2 - w / 2, 0, L, w, T)             # 端板
        f.box(-L / 2 + w / 2, 0, 0, w, H, T)            # 前缘梁
        f.box(L / 2 - w / 2, 0, 0, w, H, T)             # 后缘梁
        for xx in (-L * 0.3, 0.0, L * 0.3):             # 纵肋 ×3
            f.box(xx, 0, 0, 3, H - 2 * w, T)
        for yy in (-H * 0.25, 0.0, H * 0.25):           # 横肋 ×3
            f.box(0, yy, 0, L - 2 * w, 3, T)
        return f

    fin_me = None
    for k in range(4):
        phi = math.radians(45 + 90 * k)
        R = Matrix(((1, 0, 0),
                    (0, math.cos(phi), -math.sin(phi)),
                    (0, math.sin(phi), math.cos(phi)))).to_4x4()
        pos = Vector((P.BO_GF_X0 + P.BO_GF_CHORD / 2,
                      (P.BO_GF_R0 + P.BO_GF_R1) / 2 * math.cos(phi),
                      P.BO_AXIS_Z + (P.BO_GF_R0 + P.BO_GF_R1) / 2 * math.sin(phi)))
        if fin_me is None:
            fin_me = to_object(fin_mb(), f"BO_GridFin{k}", coll, mats["BO"])
            ob = fin_me
        else:
            ob = fin_me.copy()
            ob.data = fin_me.data
            coll.objects.link(ob)
        ob.matrix_world = Matrix.Translation(pos) @ R
        out.setdefault("fins", []).append(ob)
    return out
