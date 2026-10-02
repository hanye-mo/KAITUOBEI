# -*- coding: utf-8 -*-
"""S4a 捆绑支架：八角断面(60×40 R8)沿拱形路径放样 + 锁止凸台×2"""
from builders.common import MB, to_object
from lib import params as P
from lib.profiles import octagon, arch_z_at


def build(x, coll, mats):
    # 底脚落在等峰拱面上（嵌入 2mm），拱顶仍托影刃腹部界面 555
    za = arch_z_at(x, P.BR_FOOTY, P.RM_X, P.RM_S, P.RM_H, P.RM_DECK_Z,
                   P.RM_SE_P, P.RM_SE_Q) - 2.0
    zc = P.BR_CROWN_Z                                  # 拱顶中心线固定（顶面 675 托无人机腹 680）
    zm = (za + zc) / 2 + 4.0
    path = [(-P.BR_FOOTY, za + P.BR_SEC_Z / 2), (-170.0, zm), (0.0, zc),
            (170.0, zm), (P.BR_FOOTY, za + P.BR_SEC_Z / 2)]
    sec = octagon(P.BR_SEC_X, P.BR_SEC_Z, P.BR_CORNER)     # XZ 平面八角
    rings = [[(x + dx, py, pz + dz) for (dx, dz) in sec] for (py, pz) in path]
    mb = MB().loft(rings, cap_start=True, cap_end=True)
    ob = to_object(mb, f"BR_{int(x)}", coll, mats["BR"])
    bx, by, bz = P.BR_BOSS
    for side in (1, -1):
        boss = MB()
        boss.box(0, 0, 0, bx, by, bz)
        boss.verts = [(vx + x, vy + side * 180.0, vz + P.BR_CROWN_Z + P.BR_SEC_Z / 2 + bz / 2 - 2)
                      for (vx, vy, vz) in boss.verts]
        to_object(boss, f"BR_{int(x)}_boss_{side}", coll, mats["BR"])
    return ob
