# -*- coding: utf-8 -*-
"""S4b 整流罩 V4（光顺包络重构）
层叠包络（锐矛+3 / 影刃+15 / 支架 / 垂尾 / 折叠翼 / 翼梢小翼）逐站凸包，
站距 25mm；凸起用"锚点收缩+smoothstep 软窗"消除逐站跳变；底缘锚点弧长重采样
保证站间顶点对应；纵向 Laplacian ×10；头部沿弹脊收缩、尾部 boat-tail 收至影刃尾舱。
[DEV#3] 顶线=包络+15，硬上限 FA_ZMAX。
"""
import math
from builders.common import MB, to_object, boolean, solidify
from lib import params as P
from lib.profiles import (interp, convex_offset, convex_hull, scaled_arch,
                          clip_halfplane, rotate_to_anchor, resample)


def _smoothstep(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def _soft(x, x0, x1, m=None):
    """软窗：[x0,x1] 内 1，两端 FA_SOFT 长度 smoothstep 过渡"""
    m = m or P.FA_SOFT
    if x <= x0 - m or x >= x1 + m:
        return 0.0
    if x < x0:
        return _smoothstep(1.0 - (x0 - x) / m)
    if x > x1:
        return _smoothstep(1.0 - (x - x1) / m)
    return 1.0


def _rm_outline(x):
    xx = min(x, 4500.0)
    return scaled_arch(interp(P.RM_X, P.RM_S, xx), interp(P.RM_X, P.RM_H, xx),
                       P.RM_DECK_Z, p=P.RM_SE_P, q=P.RM_SE_Q)


def _yr_outline(xg):
    """影刃菱边截面（CCW，全局 z 已加安装高度 680，供凸包偏移）"""
    from builders.uav import _section
    xl = min(max(xg - P.YR_INSTALL[0], 0.0), 1800.0)
    z0 = P.YR_INSTALL[2]
    return [(y, z + z0) for (y, z) in reversed(_section(xl))]


def _bump(anchor, target, w):
    """凸起贡献点：w=软窗权重，锚点收缩防逐站跳变"""
    return (anchor[0] + w * (target[0] - anchor[0]),
            anchor[1] + w * (target[1] - anchor[1]))


def _clip_y_band(poly, y_lo, y_hi):
    """凸多边形按 |y|∈[y_lo,y_hi] 裁剪（两次半平面 Sutherland–Hodgman）"""

    def clip(poly, val, keep_ge):
        out = []
        m = len(poly)
        for i in range(m):
            a, b = poly[i], poly[(i + 1) % m]
            ia = (a[0] >= val) if keep_ge else (a[0] <= val)
            ib = (b[0] >= val) if keep_ge else (b[0] <= val)
            if ia:
                out.append(a)
            if ia != ib:
                t = (val - a[0]) / (b[0] - a[0])
                out.append((val, a[1] + t * (b[1] - a[1])))
        return out

    return clip(clip(poly, y_hi, False), y_lo, True)


def _half(x):
    """右半截面点列（y>=0），凸包 + 裁剪 + 底缘锚点重采样"""
    arch = convex_offset(_rm_outline(x), P.FA_GAP_M)
    if x < 2150.0:
        # 头部：整流罩贴弹脊生长——导弹拱顶裁剪段（|y|≤y_e），无悬空收缩锥
        ymax = max(y for (y, _) in arch)
        t = _smoothstep((x - P.FA_X0B) / (2150.0 - P.FA_X0B))
        ye = max(t * ymax * 1.002, 6.0)
        half = clip_halfplane(_clip_y_band(arch, -ye, ye), keep_positive=True)
        return resample(rotate_to_anchor(half, anchor=(1e6, 0.0)), 88)

    pts = arch
    if x >= P.YR_INSTALL[0]:
        pts += convex_offset(_yr_outline(x), P.FA_GAP_U)
        # SERN 下探包络（尾部下壁斜切至 z=680−52，_section 不含此项）
        if x >= P.YR_INSTALL[0] + P.YR_SERN_X0:
            xl = min(x - P.YR_INSTALL[0], 1800.0)
            wb = P.YR_CHINE_WF * interp(P.YR_X, P.YR_S, xl)
            zb = P.YR_INSTALL[2] - P.YR_SERN_D * min(1.0, (xl - P.YR_SERN_X0) /
                                                     (P.YR_SERN_X1 - P.YR_SERN_X0)) - 4.0
            pts += [(wb + P.FA_GAP_U, zb), (0.55 * wb, zb)]

    def bump(anchor, target, w):
        return (anchor[0] + w * (target[0] - anchor[0]),
                anchor[1] + w * (target[1] - anchor[1]))

    w_br = _soft(x, 2900.0, 4100.0)                     # 捆绑支架拱顶
    w_vt = _soft(x, 4010.0, 4360.0, 200.0)              # 垂尾板
    w_wg = _soft(x, 3640.0, 4423.0, 260.0)              # 折叠外翼（缓升沿防台阶）
    w_tw = _soft(x, 3800.0, 4330.0)                     # 翼梢小翼
    if w_br > 0:
        pts += [_bump((150, 640), (265, 690), w_br), _bump((150, 640), (200, 685), w_br)]
    if w_vt > 0:
        pts += [_bump((320, 655), (452, 996), w_vt), _bump((320, 655), (385, 975), w_vt)]
    if w_wg > 0:
        pts += [_bump((340, 700), (512, 1074), w_wg), _bump((340, 700), (465, 1052), w_wg)]
    if w_tw > 0:
        pts += [_bump((1100, 2), (1322, 302), w_tw), _bump((1100, 2), (1190, 288), w_tw)]
    hz = convex_hull(pts)
    hz = [(y, min(max(z, -1.5), P.FA_ZMAX - 5.0)) for (y, z) in hz]
    half = clip_halfplane(hz, keep_positive=True)
    return resample(rotate_to_anchor(half, anchor=(1e6, 0.0)), 88)


def _tail_half():
    """4550 尾端截面：影刃尾舱包络"""
    pts = convex_offset(_yr_outline(4500), P.FA_GAP_U)
    hz = convex_hull(pts)
    hz = [(y, min(max(z, -1.5), P.FA_ZMAX - 5.0)) for (y, z) in hz]
    return resample(rotate_to_anchor(clip_halfplane(hz, True), anchor=(1e6, 0.0)), 88)


def _stations():
    xs = [P.FA_X0B + i * P.FA_DX for i in range(int((P.FA_X0 - P.FA_X0B) / P.FA_DX) + 1)]
    x = P.FA_X0 + P.FA_DX
    while x < 4450.0:
        xs.append(x)
        x += P.FA_DX
    xs += [4462.0, 4487.0, 4512.0, P.FA_X1]
    return xs


def _seam_snap(rings):
    """顶部分缝顶点（apex 邻域）y 归零对齐分缝线，消除重采样 y 向漂移。
    只动 y 不动 z（强拉 z 会在头部薄环制造尖刺，EXACT 布尔会返回空网格）。"""
    for ring in rings:
        zmax = max(z for (_, _, z) in ring)
        y_apex = min((abs(y) for (_, y, z) in ring if z > 0.98 * zmax), default=1e9)
        if y_apex > 60.0:
            continue                      # apex 不在分缝（鼓包主导），不动
        cands = [i for i, (_, y, z) in enumerate(ring) if abs(y) < 30.0 and z > 0.9 * zmax]
        if not cands:
            continue
        i0 = min(cands, key=lambda i: abs(ring[i][1]))
        px, _, z0 = ring[i0]
        ring[i0] = (px, 0.0, z0)
    return rings


def _snap_bottom(rings, z_gate=35.0):
    """把每站截面底缘顶点（z<z_gate）最近点吸附到导弹外形+3 轮廓上，
    消除重采样/平滑导致的底缘锯齿"""
    cache = {}

    def outline_at(x):
        key = round(x)
        if key not in cache:
            poly = convex_offset(_rm_outline(min(key, 4500)), P.FA_GAP_M)
            segs = []
            m = len(poly)
            for i in range(m):
                a, b = poly[i], poly[(i + 1) % m]
                segs.append((a, (b[0] - a[0], b[1] - a[1])))
            cache[key] = segs
        return cache[key]

    for ring in rings:
        segs = outline_at(ring[0][0])
        for k, (px, py, pz) in enumerate(ring):
            if pz >= z_gate:
                continue
            best, bd = None, 1e18
            for (a, d) in segs:
                L2 = d[0] * d[0] + d[1] * d[1]
                t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((py - a[0]) * d[0] + (pz - a[1]) * d[1]) / L2))
                qy, qz = a[0] + t * d[0], a[1] + t * d[1]
                dd = (py - qy) ** 2 + (pz - qz) ** 2
                if dd < bd:
                    bd, best = dd, (qy, qz)
            if best is not None:
                ring[k] = (px, best[0], best[1])
    return rings


def build(coll, mats):
    out = {}
    stations = _stations()
    tail = _tail_half()
    rings_r = []
    for x in stations:
        if x >= P.FA_X1 - 1e-6:
            r = tail
        elif x >= 4512.0:
            t = (x - 4512.0) / (P.FA_X1 - 4512.0)
            a = [(py, pz) for (_, py, pz) in rings_r[-1]]
            r = [(ay + (by - ay) * t, az + (bz - az) * t) for ((ay, az), (by, bz)) in zip(a, tail)]
        else:
            r = _half(x)
        rings_r.append([(float(x), y, z) for (y, z) in r])

    # 纵向 Laplacian 平滑（跳过头/尾各 3 站；底缘与分缝低区顶点固定——
    # 它们本就是精确的导弹轮廓/分缝线，平滑会制造锯齿，吸附会制造退化面）
    def _smooth(rs, i0, i1, passes, pin_z=35.0):
        n = len(rs)
        pin = [[z < pin_z for (_, _, z) in r] for r in rs]
        for _ in range(passes):
            nxt = [list(r) for r in rs]
            for i in range(max(1, i0), min(n - 1, i1)):
                for j in range(len(rs[i])):
                    if pin[i][j]:
                        continue
                    py, pz = rs[i - 1][j][1], rs[i - 1][j][2]
                    cy, cz = rs[i][j][1], rs[i][j][2]
                    ny, nz = rs[i + 1][j][1], rs[i + 1][j][2]
                    nxt[i][j] = (rs[i][j][0], 0.25 * py + 0.5 * cy + 0.25 * ny,
                                 0.25 * pz + 0.5 * cz + 0.25 * nz)
            rs = nxt
        return rs
    rings_r = _smooth(rings_r, 3, len(rings_r) - 4, P.FA_SMOOTH_P)
    rings_r = _seam_snap(rings_r)
    rings_r = [[(px, py + 1.2, max(pz, -1.5)) for (px, py, pz) in r] for r in rings_r]
    rings_l = [[(px, -py - 1.2, max(pz, -1.5)) for (px, py, pz) in reversed(r)] for r in rings_r]

    for tag, rings, pv in (("FA_R", rings_r, (3275.0, 550.0, 600.0)),
                           ("FA_L", rings_l, (3275.0, -550.0, 600.0))):
        mb = MB()
        mb.loft([[(px - pv[0], py - pv[1], pz - pv[2]) for (px, py, pz) in ring] for ring in rings],
                cap_start=True, cap_end=True)
        ob = to_object(mb, tag, coll, mats["FA"])
        ob.location = pv
        try:
            solidify(ob, P.FA_WALL)
            out.setdefault("notes", []).append(f"{tag}: solidify {P.FA_WALL}mm OK")
        except Exception as e:
            out.setdefault("notes", []).append(f"{tag}: solidify FAIL -> solid ({e})")
        out[tag.lower()] = ob

    # 泄压孔 Φ20（孔轴绕 Y 后倾 30°）：右瓣 x={3000,4000}，左瓣 x={2500,3500}
    for tag, xs_h, side in (("fa_r", P.FA_PORT_XR, 1), ("fa_l", P.FA_PORT_XL, -1)):
        ob = out[tag]
        for xh in xs_h:
            s = interp(P.RM_X, P.RM_S, xh)
            h = interp(P.RM_X, P.RM_H, xh)
            y150 = s * (1.0 - (P.FA_PORT_Z / h) ** (4.0 / 3.0)) ** (1.0 / 2.2) + P.FA_GAP_M + 2
            cx, cy, cz = xh, side * y150, P.FA_PORT_Z
            d = (-math.cos(math.radians(P.FA_PORT_TILT)), 0.0,
                 math.sin(math.radians(P.FA_PORT_TILT)))
            tool = MB().cyl((cx - 80 * d[0], cy, cz - 80 * d[2]),
                            (cx + 80 * d[0], cy, cz + 80 * d[2]), P.FA_PORT_R)
            boolean(ob, to_object(tool, f"{tag}_port{xh}", coll), 'DIFFERENCE')
            out.setdefault("ports", []).append((tag, xh))
    return out
