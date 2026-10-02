# -*- coding: utf-8 -*-
"""S3 影刃 V4（军工级外观重构）
- 机身：菱边（chine）隐身截面放样——平底、外倾下壁、菱边小倒角（最宽点）、平顶幂律上表面；
- 鼻尖 r9 球钝化；腹部进气道楔（宽度随站位收敛，不越出机腹）+ 前端黑色进气口；
- 尾部 SERN 外膨胀斜面（宽度随机身收敛）+ 斜面深色板 + 尾端面排气槽；
- 翼根整流鼓包 ×2（覆盖顺流铰链翼根缝）；背部载荷舱门（贴面暗板）；
- 双外倾垂尾 40°；顺流铰链变构外翼（根弦 380 / 尖弦 140 / 展 300 / LE 后掠 65°）。
"""
import bpy
import math
from mathutils import Matrix, Vector

from builders.common import MB, to_object, boolean
from lib import params as P
from lib.profiles import interp
from .missile import mesh_from_mb


def _nose_g(x):
    if x >= P.YR_NOSE_BLEND:
        return 1.0
    return math.sqrt(max(0.0, 1.0 - ((P.YR_NOSE_BLEND - x) / P.YR_NOSE_BLEND) ** 2))


def _wh(xl):
    g = _nose_g(xl)
    return interp(P.YR_X, P.YR_S, xl) * g, interp(P.YR_X, P.YR_H, xl) * g


def _top_z(xl, y):
    """菱边截面上表面高度（含菱边折点以上的幂律）"""
    w, h = _wh(xl)
    ch = P.YR_CHINE_ZF * h
    t = min(abs(y) / w, 1.0) if w > 1e-9 else 0.0
    return h - (h - ch) * t ** P.YR_TOP_P


def _section(xl):
    """菱边隐身截面 2D [(y,z)]，28 点闭合环（顶中心→右下→底→左上）
    菱边=上翼幂律与外倾下壁的天然交点（折角约110°，35°平滑阈下棱线清晰）"""
    w, h = _wh(xl)
    if xl <= 1e-6:
        w = h = 0.35
    ch = P.YR_CHINE_ZF * h
    wb = P.YR_CHINE_WF * w
    right = [(0.0, h)]
    for i in range(1, 9):
        t = i / 9.0
        right.append((w * t, h - (h - ch) * t ** P.YR_TOP_P))
    right.append((w, ch))
    for i in range(1, 4):
        s = i / 4.0
        right.append((w + (wb - w) * s, ch * (1.0 - s)))
    right.append((wb, 0.0))
    right.append((0.0, 0.0))
    left = [(-y, z) for (y, z) in reversed(right[1:-1])]
    return right + left


def _ring(xl):
    return [(xl, y, z) for (y, z) in _section(xl)]


def _stations():
    xs = [0.0, 4.0, 10.0, 18.0, 30.0, 45.0, 62.0, 82.0, 105.0, 135.0, 170.0, 210.0, 255.0]
    x = 305.0
    while x < 1790.0:
        xs.append(x)
        x += 55.0
    xs.append(1800.0)
    return xs


def _mirror_mb(mb):
    m2 = MB()
    m2.verts = [(x, -y, z) for (x, y, z) in mb.verts]
    m2.faces = [list(reversed(f)) for f in mb.faces]
    return m2


def _paint_tps(body):
    """布尔后按面中心刷 TPS 材质（鼻尖球区 → 槽 1）"""
    me = body.data
    if len(me.materials) < 2:
        me.materials.append(bpy.data.materials.get("M_TPS"))
    for p in me.polygons:
        if (Vector(p.center) - Vector((P.YR_NOSE_R, 0, 0))).length < P.YR_NOSE_R + 3:
            p.material_index = 1
    me.update()


def build(coll, mats):
    out = {}
    # ---------- 机身放样 ----------
    body = to_object(MB().loft([_ring(x) for x in _stations()], cap_start=True, cap_end=True),
                     "YR_Body", coll, mats["YR"])

    # 鼻尖钝化 + 底面裁平
    nose = MB().sphere((P.YR_NOSE_R, 0, 0), P.YR_NOSE_R, nu=32, nv=16)
    nose_ob = to_object(nose, "YR_nose", coll, mats["TPS"])
    trim = MB().box(1200, 0, -1502, 5000, 4000, 3000)
    boolean(nose_ob, to_object(trim, "YR_trim", coll), 'DIFFERENCE')
    boolean(body, nose_ob, 'UNION')

    # ---------- 腹部进气道楔（宽度随站位收敛）+ 前端进气口 ----------
    def _inl_hw(xl):
        if xl <= 740.0:
            t = (xl - P.YR_INL_X0) / (740.0 - P.YR_INL_X0)
            return 234.0 + t * 26.0
        return 262.0

    rings = []
    for xl in (P.YR_INL_X0, 710.0, 745.0, P.YR_INL_X1):
        hw = _inl_hw(xl)
        rings.append([(xl, -hw, 1.0), (xl, hw, 1.0), (xl, hw, -P.YR_INL_D), (xl, -hw, -P.YR_INL_D)])
    boolean(body, to_object(MB().loft(rings, cap_start=True, cap_end=True),
                            "YR_inlet", coll), 'UNION')
    cut = MB().box(P.YR_INL_X0 + 11, 0, -23.0, 26.0, 452.0, 36.0)      # 进气口空腔
    boolean(body, to_object(cut, "YR_inlcut", coll), 'DIFFERENCE')
    lip = MB().box(P.YR_INL_X0 + 13, 0, -23.0, 18.0, 440.0, 28.0)      # 深色进气口（内缩 4）
    out["intakelip"] = to_object(lip, "YR_InletLip", coll, mats["CAVITY"])

    # ---------- SERN 外膨胀斜面（宽度收敛）+ 深色膨胀面 + 尾端面排气槽 ----------
    rings = []
    for xl in (P.YR_SERN_X0, P.YR_SERN_X1):
        hw = P.YR_CHINE_WF * interp(P.YR_X, P.YR_S, xl) - 6.0
        zb = -P.YR_SERN_D * (xl - P.YR_SERN_X0) / (P.YR_SERN_X1 - P.YR_SERN_X0)
        rings.append([(xl, -hw, 1.0), (xl, hw, 1.0), (xl, hw, zb), (xl, -hw, zb)])
    boolean(body, to_object(MB().loft(rings, cap_start=True, cap_end=True),
                            "YR_sern", coll), 'UNION')
    ramp = MB()
    rp = []
    for xl in (P.YR_SERN_X0 + 90.0, P.YR_SERN_X1 - 5.0):
        hw = P.YR_CHINE_WF * interp(P.YR_X, P.YR_S, xl) - 16.0
        zb = -P.YR_SERN_D * (xl - P.YR_SERN_X0) / (P.YR_SERN_X1 - P.YR_SERN_X0)
        rp.append([(xl, -hw, zb + 2.0), (xl, hw, zb + 2.0), (xl, hw, zb - 6.0), (xl, -hw, zb - 6.0)])
    ramp.loft(rp, cap_start=True, cap_end=True)
    out["sernramp"] = to_object(ramp, "YR_SernRamp", coll, mats["CAVITY"])

    exh = MB().box((P.YR_EXH_X0 + 1800.0) / 2, 0, (P.YR_EXH_Z0 + P.YR_EXH_Z1) / 2,
                   1800.0 - P.YR_EXH_X0 + 24.0, 2 * P.YR_EXH_W, P.YR_EXH_Z1 - P.YR_EXH_Z0)
    boolean(body, to_object(exh, "YR_exhcut", coll), 'DIFFERENCE')
    ins = MB().box(P.YR_EXH_X0 + 9, 0, (P.YR_EXH_Z0 + P.YR_EXH_Z1) / 2,
                   12.0, 2 * P.YR_EXH_W - 12.0, P.YR_EXH_Z1 - P.YR_EXH_Z0 - 12.0)
    out["exhinsert"] = to_object(ins, "YR_ExhInsert", coll, mats["CAVITY"])

    # ---------- 翼根整流鼓包（左右一体，外缘 500 < 罩包络 505）----------
    bl_r = [(360, 45), (480, 30), (500, 70), (480, 110), (360, 95)]
    ring_pts = bl_r + [(-y, z) for (y, z) in reversed(bl_r[1:-1])]
    rings = [[(xl, y, z) for (y, z) in ring_pts] for xl in (900.0, 1360.0)]
    out["blister"] = to_object(MB().loft(rings, cap_start=True, cap_end=True),
                               "YR_Blister", coll, mats["YR"])

    # ---------- 背部载荷舱门（隐身锯齿边缘，随形暗板，Proud 1.5 / 埋入 8）----------
    door = MB()
    dr = []
    xst = list(range(int(P.YR_DOOR_X[0]), int(P.YR_DOOR_X[1]) + 1, 40))
    if xst[-1] != int(P.YR_DOOR_X[1]):
        xst.append(int(P.YR_DOOR_X[1]))
    for k, xi in enumerate(xst):
        xl = float(xi)
        hw = P.YR_DOOR_Y - (P.YR_DOOR_TOOTH_D if k % 2 else 0.0)
        ys = (-hw, -hw / 2, 0.0, hw / 2, hw)
        top = [(y, _top_z(xl, y) + 1.5) for y in ys]
        bot = [(y, _top_z(xl, y) - 8.0) for y in reversed(ys)]
        dr.append([(xl, y, z) for (y, z) in top + bot])
    door.loft(dr, cap_start=True, cap_end=True)
    out["door"] = to_object(door, "YR_Door", coll, mats["CAVITY"])

    # ---------- 双外倾垂尾（板厚 11，根弦沿 X 于 y=±322、z=150，外倾 40°）----------
    prof = [(0, 0), (P.YR_VT_LEOFF, P.YR_VT_SPAN),
            (P.YR_VT_LEOFF + P.YR_VT_TIPC, P.YR_VT_SPAN), (P.YR_VT_ROOTC, 0)]
    vt_mb = MB().prism_xz(prof, -P.YR_VT_T / 2, P.YR_VT_T / 2)
    for side in (1, -1):
        ob = to_object(vt_mb, f"YR_VT_{'R' if side > 0 else 'L'}", coll, mats["CTRL"])
        ob.location = (P.YR_VT_X0, side * P.YR_VT_ROOTY, P.YR_VT_ROOTZ)
        ob.rotation_euler = (math.radians(-P.YR_VT_CANT * side), 0, 0)
        out[f"vt_{'r' if side > 0 else 'l'}"] = ob

    # ---------- 变构外翼 ×2（六边形翼型，铰点=根前缘=铰链）----------
    tip_dx = P.YW_SPAN * math.tan(math.radians(P.YW_LE_SWEEP))

    def rib(c, t):
        return [(0, 0), (0.15 * c, t / 2), (0.55 * c, t / 2),
                (c, 0), (0.55 * c, -t / 2), (0.15 * c, -t / 2)]

    rib_root = [(x, 0.0, z) for (x, z) in rib(P.YW_ROOTC, P.YW_T)]
    rib_tip = [(tip_dx + x, P.YW_SPAN, z) for (x, z) in rib(P.YW_TIPC, P.YW_T)]
    wme_r = mesh_from_mb(MB().loft([rib_root, rib_tip], cap_start=True, cap_end=True), "YR_WingMeshR")
    wme_l = mesh_from_mb(_mirror_mb(MB().loft([rib_root, rib_tip], cap_start=True, cap_end=True)),
                         "YR_WingMeshL")
    for me in (wme_r, wme_l):
        me.materials.append(mats["YR"])
    for side in (1, -1):
        ob = bpy.data.objects.new(f"YW_{'R' if side > 0 else 'L'}", wme_r if side > 0 else wme_l)
        coll.objects.link(ob)
        ob.location = (P.YW_ROOTLE, side * P.YW_ROOTY, P.YW_HINGEZ)
        ob.rotation_euler = (math.radians(P.YW_FOLD_STOW * side), 0, 0)   # 收拢 90°
        out[f"wing_{'r' if side > 0 else 'l'}"] = ob

    # ---------- 外翼升降副翼 ×2（弦 90 / 展 260 / 缝 2，§3.3.2；烘焙 −10° C2 展示位）----------
    def _te_x(yw):
        return P.YW_ROOTC + (tip_dx + P.YW_TIPC - P.YW_ROOTC) * (yw / P.YW_SPAN)

    el_t = P.YR_EL_T
    z0e = -(P.YW_T / 2 + 8.0)                     # 下挂面（与翼下表面留 2mm 缝）
    mb_el = MB()
    y0w, y1w = 15.0, 15.0 + P.YR_EL_SPAN
    rings = []
    for yw in (y0w, y1w):
        xf = _te_x(yw) - P.YR_EL_CHORD - P.YR_EL_GAP
        prof = [(xf, 0.0), (xf + 0.3 * P.YR_EL_CHORD, el_t / 2),
                (xf + 0.85 * P.YR_EL_CHORD, el_t / 2), (xf + P.YR_EL_CHORD, 0.0),
                (xf + 0.85 * P.YR_EL_CHORD, -el_t / 2), (xf + 0.3 * P.YR_EL_CHORD, -el_t / 2)]
        rings.append([(xw, yw, z0e + zw) for (xw, zw) in prof])
    mb_el.loft(rings, cap_start=True, cap_end=True)
    hd = Vector((_te_x(P.YW_SPAN) - _te_x(0.0), float(P.YW_SPAN), 0.0)).normalized()
    Rd = Matrix.Rotation(math.radians(P.YR_EL_DEFLECT), 4, hd)
    vt2 = []
    for v in mb_el.verts:
        H = Vector((_te_x(v[1]) - P.YR_EL_GAP, v[1], z0e))
        vt2.append(tuple(H + Rd @ (Vector(v) - H)))
    mb_el.verts = vt2
    wme_el = mesh_from_mb(mb_el, "YR_ElevonMeshR")
    wme_el_l = mesh_from_mb(_mirror_mb(mb_el), "YR_ElevonMeshL")
    for me_e in (wme_el, wme_el_l):
        me_e.materials.append(mats["CTRL"])
    for side in (1, -1):
        me_s = wme_el if side > 0 else wme_el_l
        ob = bpy.data.objects.new(f"YW_El{'R' if side > 0 else 'L'}", me_s)
        coll.objects.link(ob)
        ob.location = (P.YW_ROOTLE, side * P.YW_ROOTY, P.YW_HINGEZ)
        ob.rotation_mode = 'ZYX'                  # 欧拉序 ZYX：先偏转后折叠
        ob.rotation_euler = (math.radians(P.YW_FOLD_STOW * side), 0.0, 0.0)
        out[f"el_{'r' if side > 0 else 'l'}"] = ob

    # ---------- 附件：RCS 口盖 / 辅助格栅 / 传感器窗 / 隔道 / 垂尾根罩 / 折叠铰链带 / 空速管 ----------
    rcs = MB()
    for (xr, yr_) in P.YR_RCS_COVERS:
        zs = _top_z(xr, abs(yr_))
        rcs.cyl((xr, yr_, zs - 3.0), (xr, yr_, zs + 0.8), 14.0)
    out["rcs"] = to_object(rcs, "YR_RCS", coll, mats["CTRL"])

    aux = MB()
    x0a, x1a, y0a, y1a = P.YR_AUX_DOOR
    ringa = []
    for xa in (x0a, x1a):
        ringa.append([(xa, y0a, _top_z(xa, y0a) + 0.4), (xa, y1a, _top_z(xa, y1a) + 0.4),
                      (xa, y1a, _top_z(xa, y1a) - 3.5), (xa, y0a, _top_z(xa, y0a) - 3.5)])
    aux.loft(ringa, cap_start=True, cap_end=True)
    for xr in (x0a + 30.0, (x0a + x1a) / 2, x1a - 30.0):
        aux.box(xr, (y0a + y1a) / 2, _top_z(xr, (y0a + y1a) / 2) + 1.2, 4.0,
                y1a - y0a - 8.0, 2.0)
    x0w, x1w, y0w2, y1w2 = P.YR_SENSOR_WIN
    ringw = []
    for xa in (x0w, x1w):
        ringw.append([(xa, y0w2, _top_z(xa, y0w2) + 0.4), (xa, y1w2, _top_z(xa, y1w2) + 0.4),
                      (xa, y1w2, _top_z(xa, y1w2) - 4.0), (xa, y0w2, _top_z(xa, y0w2) - 4.0)])
    aux.loft(ringw, cap_start=True, cap_end=True)
    out["aux"] = to_object(aux, "YR_AuxDoor", coll, mats["CAVITY"])

    bld = MB()
    for s_ in (1, -1):                          # 进气口两侧边界层隔道斜楔
        bld.prism_xz([(P.YR_INL_X0 - 60.0, -2.0), (P.YR_INL_X0, -2.0),
                      (P.YR_INL_X0, -26.0)], s_ * 250.0, s_ * 282.0)
    out["bld"] = to_object(bld, "YR_BLD", coll, mats["CAVITY"])

    vf = MB()
    for s_ in (1, -1):
        zb0 = _top_z(1460.0, s_ * P.YR_VT_ROOTY)
        sec_v = [(-P.YR_VTFAIR[2], 0.0), (-P.YR_VTFAIR[2] * 0.6, P.YR_VTFAIR[3]),
                 (P.YR_VTFAIR[2] * 0.6, P.YR_VTFAIR[3]), (P.YR_VTFAIR[2], 0.0)]
        rings = [[(xa, s_ * P.YR_VT_ROOTY + dy, zb0 - 4.0 + dz) for (dy, dz) in sec_v]
                 for xa in (P.YR_VTFAIR[0], P.YR_VTFAIR[1])]
        vf.loft(rings, cap_start=True, cap_end=True)
    out["vtfair"] = to_object(vf, "YR_VTFair", coll, mats["CTRL"])

    hs = MB()
    for s_ in (1, -1):
        hs.box(1130.0, s_ * 490.0, 92.0, 430.0, 9.0, 18.0)
    out["hingestrip"] = to_object(hs, "YR_FoldStrip", coll, mats["CAVITY"])

    pt = MB()
    for s_ in (1, -1):
        (bx, by, bz), (tx, ty, tz) = P.YR_PITOT
        zb = _top_z(bx, s_ * by) - 2.0          # 基点贴表面
        dz = tz - bz
        pt.cyl((bx, s_ * by, zb), (tx, s_ * ty, zb + dz), 4.0)
        pt.cyl((tx, s_ * ty, zb + dz), (tx - 22.0, s_ * (ty + 2.5), zb + dz + 3.0), 1.6)
    out["pitot"] = to_object(pt, "YR_Pitot", coll, mats["CTRL"])

    _paint_tps(body)
    out["body"] = body
    return out
