# -*- coding: utf-8 -*-
"""S2 锐矛 V4（军工级外观重构）
- 机身：密集站位（鼻部加密+50mm 站距）放样等峰拱顶乘波体，平底 z=0；
- TPS 分色：鼻尖球 r18 + 两侧前缘圆柱链 r18 用深色碳陶材质，布尔并入后与钛灰机身自动分色；
- 蒙皮工艺缝：4 道环向 V 缝（外偏 1.3 深 6 宽）环绕全截面（含前缘）；
- 尾端面发动机端口 φ300 深 60 + 深色内锥/喉道（C1 状态可见，SC_A 被过渡段遮蔽）；
- 底部喷口凹位 φ260×20（方案 §3.2.4）+ 深色底板；
- 襟副翼：底面刻槽（深 26）后铰装贴板，周圈 2mm 缝隙，C1 绕铰链偏 -8°；
- 翼梢小翼 ×2：六边形剖面，沿前缘线外倾 35°。
"""
import bpy
import math
from mathutils import Vector, Matrix

from builders.common import MB, to_object, boolean
from lib import params as P
from lib.profiles import interp, scaled_arch, convex_offset


def mesh_from_mb(mb, name):
    me = bpy.data.meshes.new(name)
    me.from_pydata(mb.verts, [], mb.faces)
    me.validate()
    me.update()
    return me


def _nose_g(x):
    if x >= P.RM_NOSE_BLEND:
        return 1.0
    return math.sqrt(max(0.0, 1.0 - ((P.RM_NOSE_BLEND - x) / P.RM_NOSE_BLEND) ** 2))


def _flat(x, n=24):
    """等峰拱顶 2D 截面 [(y,z)]（z=0 平底，峰值 RM_DECK_Z）"""
    s = interp(P.RM_X, P.RM_S, x) * _nose_g(x)
    h = interp(P.RM_X, P.RM_H, x) * _nose_g(x)
    if x <= 1e-6:
        s = h = 0.5
    return scaled_arch(s, h, P.RM_DECK_Z, p=P.RM_SE_P, q=P.RM_SE_Q, n=n)


def _ring(x, n=24):
    return [(x, y, z) for (y, z) in _flat(x, n)]


def _stations():
    xs = [0.0, 6.0, 14.0, 24.0, 38.0, 55.0, 78.0, 105.0, 140.0,
          180.0, 225.0, 280.0, 340.0, 395.0, 450.0]
    x = 480.0
    while x < 4480.0:
        xs.append(x)
        x += 30.0
    xs.append(4500.0)
    return xs


def _pipe(pts, r, seg=24, start_scale=0.35):
    """折线路径圆柱链（单次放样闭合流形，首环缩径收进鼻尖球）"""
    n = len(pts)
    dirs = []
    for i in range(n):
        if i == 0:
            d = Vector(pts[1]) - Vector(pts[0])
        elif i == n - 1:
            d = Vector(pts[-1]) - Vector(pts[-2])
        else:
            d = Vector(pts[i + 1]) - Vector(pts[i - 1])
        dirs.append(d.normalized())
    rings = []
    for i, (pt, d) in enumerate(zip(pts, dirs)):
        xax = d.cross(Vector((0, 0, 1)))
        if xax.length < 1e-6:
            xax = Vector((0, 1, 0))
        xax.normalize()
        yax = d.cross(xax).normalized()
        k = 1.0 if i > 0 else start_scale
        rings.append([tuple(Vector(pt) + k * r * (xax * math.cos(2 * math.pi * j / seg) +
                                                   yax * math.sin(2 * math.pi * j / seg)))
                      for j in range(seg)])
    return MB().loft(rings, cap_start=True, cap_end=True)


def _paint_tps(body):
    """布尔后按面中心刷 TPS 材质（EXACT 布尔不传递工具材质槽）：
    鼻尖球区 + 两侧前缘圆柱链区 → 槽 1（TPS）"""
    me = body.data
    if len(me.materials) < 2:
        me.materials.append(bpy.data.materials.get("M_TPS"))
    tps_idx = 1
    for p in me.polygons:
        c = p.center
        hit = False
        if c.x < 40.0 and (Vector(c) - Vector((P.RM_NOSE_R, 0, 0))).length < P.RM_NOSE_R + 4:
            hit = True
        elif c.z < P.RM_LE_R + 8.0 and c.x > 30.0:
            s = interp(P.RM_X, P.RM_S, c.x)
            if abs(abs(c.y) - s) < P.RM_LE_R + 4.0:
                hit = True
        if hit:
            p.material_index = tps_idx
    me.update()


def _surf_z(x, y, surf):
    """机体上/下表面在 (x,y) 处的高度（等峰拱顶）"""
    s = interp(P.RM_X, P.RM_S, x) * _nose_g(x)
    h = interp(P.RM_X, P.RM_H, x) * _nose_g(x)
    if surf == 'bot':
        return 0.0
    z = h * (1.0 - (abs(y) / s) ** P.RM_SE_P) ** P.RM_SE_Q if s > 1e-9 and abs(y) < s else 0.0
    if h > 1e-9 and h > P.RM_DECK_Z:
        z *= P.RM_DECK_Z / h
    return z


def build(coll, mats):
    out = {}
    # ---------- 机身放样 ----------
    rings = [_ring(x) for x in _stations()]
    body = to_object(MB().loft(rings, cap_start=True, cap_end=True),
                     "RM_Body", coll, mats["RM_BODY"])

    # ---------- 鼻尖球 + 前缘圆柱链（TPS 深色，并入后分色）----------
    uu = 1.0 / math.hypot(450, 130)
    t0 = 34.6                                   # 鼻尖球面与前缘线交点
    trim_mb = MB().box(2250, 0, -1502, 9000, 6000, 3000)   # 顶面 z=-2 截管/球（避赤道相切退化）

    sph = to_object(MB().sphere((P.RM_NOSE_R, 0, 0), P.RM_NOSE_R, nu=32, nv=16),
                    "RM_nose", coll, mats["TPS"])
    boolean(sph, to_object(trim_mb, "RM_trim1", coll), 'DIFFERENCE')
    for side in (1, -1):
        pts = [(t0 * 450 * uu, side * t0 * 130 * uu, 0.0)] + \
              [(float(x), side * float(interp(P.RM_X, P.RM_S, x)), 0.0) for x in P.RM_X[1:-1]] + \
              [(4494.2, side * 1298.3, 0.0)]     # 尾端回退 6mm，避免端帽越出尾端面
        pob = to_object(_pipe(pts, P.RM_LE_R), f"RM_le_{side}", coll, mats["TPS"])
        boolean(pob, to_object(trim_mb, "RM_trim2", coll), 'DIFFERENCE')
        boolean(body, pob, 'UNION')
    boolean(body, sph, 'UNION')

    # ---------- 前缘鼻段节点珠（TPS 连续珠串，覆盖蒙皮折线与直管的过渡区）----------
    beads = MB()
    xb = 30.0                                  # 首珠前缘 30−21=9>0，不越鼻尖
    while xb <= 1000.0:
        sb = interp(P.RM_X, P.RM_S, xb) * _nose_g(xb)
        for side in (1, -1):
            beads.sphere((xb, side * sb, 0.0), P.RM_LE_R + 3.0, nu=16, nv=8)
        xb += 15.0
    out["lebeads"] = to_object(beads, "RM_LEBeads", coll, mats["TPS"])

    # ---------- 蒙皮环向工艺缝（含前缘 bead 一并切过）----------
    grooves = MB()
    for xg in P.RM_GROOVE_X:
        x0, x1 = xg - P.RM_GROOVE_W / 2, xg + P.RM_GROOVE_W / 2
        r0 = convex_offset(_flat(x0), P.RM_GROOVE_D)
        r1 = convex_offset(_flat(x1), P.RM_GROOVE_D)
        grooves.loft([[(x0, y, z) for (y, z) in r0], [(x1, y, z) for (y, z) in r1]],
                     cap_start=True, cap_end=True)
    boolean(body, to_object(grooves, "RM_grooves", coll), 'DIFFERENCE')

    # ---------- 尾端面发动机端口 φ300×60 + 深色内锥 ----------
    port = MB().cyl((P.RM_ENG_X + 10, 0, P.RM_ENG_Z),
                    (P.RM_ENG_X - P.RM_ENG_D, 0, P.RM_ENG_Z), P.RM_ENG_R)
    boolean(body, to_object(port, "RM_engport", coll), 'DIFFERENCE')
    cone = MB()
    r_lip = P.RM_ENG_R - 4.0
    ring_a = [(P.RM_ENG_X - 1.0, r_lip * math.cos(a), P.RM_ENG_Z + r_lip * math.sin(a))
              for a in (2 * math.pi * i / P.SEG for i in range(P.SEG))]
    ring_b = [(P.RM_ENG_X - P.RM_ENG_D + 6, P.RM_ENG_THROAT_R * math.cos(a),
               P.RM_ENG_Z + P.RM_ENG_THROAT_R * math.sin(a))
              for a in (2 * math.pi * i / P.SEG for i in range(P.SEG))]
    cone.loft([ring_a, ring_b], cap_start=False, cap_end=True)
    out["engcone"] = to_object(cone, "RM_EngCone", coll, mats["CAVITY"])

    # ---------- 底部喷口凹位 φ260×20 + 内锥喷口（方案 §3.2.4）----------
    rec = MB().cyl((P.RM_NOZC_X, 0, -10), (P.RM_NOZC_X, 0, P.RM_NOZC_D), P.RM_NOZC_R)
    boolean(body, to_object(rec, "RM_nozc", coll), 'DIFFERENCE')
    nc = MB()
    rA, rB = P.RM_NOZC_R - 4.0, 58.0
    ringA = [(P.RM_NOZC_X, rA * math.cos(a), P.RM_NOZC_D - 2 + rA * math.sin(a))
             for a in (2 * math.pi * i / P.SEG for i in range(P.SEG))]
    ringB = [(P.RM_NOZC_X, rB * math.cos(a), -16.0 + rB * math.sin(a))
             for a in (2 * math.pi * i / P.SEG for i in range(P.SEG))]
    nc.loft([ringA, ringB], cap_start=False, cap_end=True)
    out["nozcone"] = to_object(nc, "RM_NozCone", coll, mats["CAVITY"])

    # ---------- 底部发动机舱纵缝（z=0 平底刻缝）----------
    seam = MB().box((P.RM_SEAM_BOT[0] + P.RM_SEAM_BOT[1]) / 2, 0, -0.65,
                    P.RM_SEAM_BOT[1] - P.RM_SEAM_BOT[0], 6.0, 1.4)
    boolean(body, to_object(seam, "RM_botseam", coll), 'DIFFERENCE')

    # ---------- RCS 口盖 ×6（φ50 沉孔 + 深色盖板，方案 §3.2.4 D2）----------
    for i, (px, py, sf) in enumerate(P.RM_RCS_PORTS):
        zs = _surf_z(px, py, sf)
        if sf == 'top':
            z0, z1 = zs - 2.0, zs + 2.5
        else:
            z0, z1 = zs - 2.5, zs + 2.0
        cut = MB().cyl((px, py, z0), (px, py, z1), P.RM_RCS_PORT_R)
        boolean(body, to_object(cut, f"RM_rcs{i}", coll), 'DIFFERENCE')
    rcs = MB()
    for (px, py, sf) in P.RM_RCS_PORTS:
        zs = _surf_z(px, py, sf)
        if sf == 'top':
            rcs.cyl((px, py, zs - 1.5), (px, py, zs - 0.5), P.RM_RCS_PORT_R - 1.5)
        else:
            rcs.cyl((px, py, zs + 0.5), (px, py, zs + 1.5), P.RM_RCS_PORT_R - 1.5)
    out["rcs"] = to_object(rcs, "RM_RCS", coll, mats["CTRL"])

    # ---------- 检修口盖 ×3（随形凸板）+ 紧固件珠 ----------
    def _panel_mb(x0, x1, y0, y1, proud, depth):
        rings = []
        for i in range(6):
            x = x0 + (x1 - x0) * i / 5.0
            ring = [(y0, _surf_z(x, y0, 'top') - depth), (y1, _surf_z(x, y1, 'top') - depth),
                    (y1, _surf_z(x, y1, 'top') + proud), (y0, _surf_z(x, y0, 'top') + proud)]
            rings.append([(x, yy, zz) for (yy, zz) in ring])
        return rings

    pnl = MB()
    for (x0, x1, y0, y1) in P.RM_PANELS:
        pnl.loft(_panel_mb(x0, x1, y0, y1, P.RM_PANEL_P, 4.0), cap_start=True, cap_end=True)
    out["panels"] = to_object(pnl, "RM_Panels", coll, mats["CTRL"])

    dots = MB()
    for (x0, x1, y0, y1) in P.RM_PANELS:
        rim = []
        for i in range(7):
            x = x0 + (x1 - x0) * i / 6.0
            rim += [(x, y0 - 8.0), (x, y1 + 8.0)]
        for j in range(1, 3):
            y = y0 + (y1 - y0) * j / 3.0
            rim += [(x0 - 8.0, y), (x1 + 8.0, y)]
        for (x, y) in rim:
            dots.sphere((x, y, _surf_z(x, y, 'top') - 0.6), P.RM_DOT_R, nu=10, nv=6)
    out["dots"] = to_object(dots, "RM_Dots", coll, mats["CTRL"])
    _paint_tps(body)
    out["body"] = body

    # ---------- 襟副翼：底面刻槽 + 铰装贴板（铰链 x=4200, z=13）----------
    for side in (1, -1):
        y0, y1 = sorted((side * P.RM_ELEV_Y, side * P.RM_ELEV_Y1))
        cut = MB().box((P.RM_ELEV_X0 + P.RM_ELEV_X1) / 2, (y0 + y1) / 2, 10.5,
                       P.RM_ELEV_X1 - P.RM_ELEV_X0, y1 - y0, 31.0)
        boolean(body, to_object(cut, f"RM_elevcut_{side}", coll), 'DIFFERENCE')
    ev = MB()
    for side in (1, -1):
        y0, y1 = sorted((side * P.RM_ELEV_Y, side * P.RM_ELEV_Y1))
        ev.box(150, (y0 + y1) / 2, 0, 296, y1 - y0, P.RM_ELEV_T)
    ev_ob = to_object(ev, "RM_Elevons", coll, mats["CTRL"])
    ev_ob.location = (P.RM_ELEV_X0, 0, 13.0)
    out["elevons"] = ev_ob

    # ---------- 翼梢小翼 ×2：六边形剖面放样，根弦沿前缘线，外倾 35° ----------
    def rib(c):
        return [(0, 0), (0.15 * c, P.RM_TW_T / 2), (0.55 * c, P.RM_TW_T / 2),
                (c, 0), (0.55 * c, -P.RM_TW_T / 2), (0.15 * c, -P.RM_TW_T / 2)]

    rib_root = [(x, 0.0, z) for (x, z) in rib(P.RM_TW_ROOTC)]
    rib_tip = [(P.RM_TW_LEOFF + x, P.RM_TW_SPAN, z) for (x, z) in rib(P.RM_TW_TIPC)]
    wme = mesh_from_mb(MB().loft([rib_root, rib_tip], cap_start=True, cap_end=True),
                       "RM_TipWingMesh")

    ang = math.atan2(1300, 4500)                     # 前缘线水平角 ≈16.05°
    Xv = Vector((math.cos(ang), math.sin(ang), 0))
    for side in (1, -1):
        sfx = 'R' if side > 0 else 'L'
        Yv = Vector((-math.sin(ang) * side, math.cos(ang) * side, 0))
        Zv = Xv.cross(Yv)
        basis = Matrix(((Xv.x, Yv.x, Zv.x), (Xv.y, Yv.y, Zv.y), (Xv.z, Yv.z, Zv.z))).to_4x4()
        # 外倾 35° = 翼面与铅垂面夹角（方案 §3.2.4）：小翼沿 +Yv 水平生成后绕前缘轴转 55°
        cant = Matrix.Rotation(math.radians(90.0 - P.RM_TW_CANT) * side, 4, 'X')
        pos = Vector((P.RM_TW_X0, side * (interp(P.RM_X, P.RM_S, P.RM_TW_X0) + 2), 10))
        ob = bpy.data.objects.new(f"RM_TipWing_{sfx}", wme)
        coll.objects.link(ob)
        if not wme.materials:
            wme.materials.append(mats["CTRL"])
        ob.matrix_world = Matrix.Translation(pos) @ basis @ cant
        out[f"tipwing_{'r' if side > 0 else 'l'}"] = ob

    # ---------- 整流罩细节：襟副翼铰链罩 + 小翼根部罩（一件式，CTRL）----------
    fr = MB()
    sec_h = [(-P.RM_ELEVH_HALF, 0.0), (-P.RM_ELEVH_HALF * 0.6, -P.RM_ELEVH_D),
             (P.RM_ELEVH_HALF * 0.6, -P.RM_ELEVH_D), (P.RM_ELEVH_HALF, 0.0)]
    for side in (1, -1):
        ya = side * P.RM_ELEVH_Y
        yb = side * (P.RM_ELEV_Y1 + 20.0)
        rings = [[(P.RM_ELEVH_X + dx, yy, dz) for (dx, dz) in sec_h] for yy in (ya, yb)]
        fr.loft(rings, cap_start=True, cap_end=True)
    fw, fl, fh = P.RM_TWFAIR
    for side in (1, -1):
        Yv = Vector((-math.sin(ang) * side, math.cos(ang) * side, 0))
        base = Vector((P.RM_TW_X0 - 40.0, side * (interp(P.RM_X, P.RM_S, P.RM_TW_X0) - 2.0), 8.0))
        sec_w = [(-fl / 2, 2.0), (-fl * 0.32, fh), (fl * 0.32, fh), (fl / 2, 2.0)]
        rings = [[tuple(base + Xv * dx + Yv * u + Vector((0, 0, dz))) for (dx, dz) in sec_w]
                 for u in (-fw / 2, fw / 2)]
        fr.loft(rings, cap_start=True, cap_end=True)
    out["fairings"] = to_object(fr, "RM_Fairings", coll, mats["CTRL"])
    return out
