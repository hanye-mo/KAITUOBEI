# -*- coding: utf-8 -*-
"""U5 解析水密网格导出（C1 弹身 + A′ 整流罩，闭合流形，供 CFD/3D 打印）
来源：lib 参数解析截面（非布尔网格，无残留面元）
验证：流形检查（每边恰 2 面）+ 散度定理体积 > 0
输出：export/mesh/ c1_body.{stl,obj} + fairing.{stl,obj} + 报告
"""
import os
import sys
import types
import struct
import math
import numpy as np

for nm in ("bpy", "bmesh", "mathutils"):
    stub = types.ModuleType(nm)
    stub.__getattr__ = lambda attr: None
    sys.modules.setdefault(nm, stub)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import params as P
from lib.profiles import interp, scaled_arch
from lib.paths import export_dir
from builders.missile import _nose_g
from builders import fairing as FA

OUT = export_dir("mesh")
os.makedirs(OUT, exist_ok=True)
MM = 1e-3


def rm_ring(x):
    s = interp(P.RM_X, P.RM_S, x) * _nose_g(x)
    h = interp(P.RM_X, P.RM_H, x) * _nose_g(x)
    if x <= 1e-6:
        s = h = 0.5
    return scaled_arch(s, h, P.RM_DECK_Z, p=P.RM_SE_P, q=P.RM_SE_Q, n=36)


def fan_cap(ring, x, at_start, tris):
    """端面扇形盖（法向外）"""
    c = np.array([x, 0.0, 0.0]) * MM if False else np.array([x, sum(p[0] for p in ring) / len(ring),
                                                             sum(p[1] for p in ring) / len(ring)]) * MM
    pts = [np.array([x, y, z]) * MM for (y, z) in ring]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        if at_start:                    # 头盖：绕序使法向 −x
            tris.append((pts[i], pts[j], c))
        else:                           # 尾盖：法向 +x
            tris.append((pts[i], c, pts[j]))


def _min_spacing(ring):
    n = len(ring)
    d = min(math.dist(ring[j], ring[(j + 1) % n]) for j in range(n))
    return d * MM


def build_c1():
    # 起始站：环最小点距 ≥0.3mm（避开鼻锥过渡段亚微米环的顶点坍缩），前端扇形盖=钝头
    x0 = 0.5
    while _min_spacing(rm_ring(x0)) < 3e-4:
        x0 += 5.0
    xs = np.arange(x0 + 30.0, 4500.0, 30.0).tolist() + [4500.0]
    xs = [x0] + xs
    rings = [rm_ring(x) for x in xs]
    tris = []
    for i in range(len(xs) - 1):
        ra, rb = rings[i], rings[i + 1]
        n = len(ra)
        for j in range(n):
            k = (j + 1) % n
            p0 = np.array([xs[i], *ra[j]]) * MM
            p1 = np.array([xs[i], *ra[k]]) * MM
            p2 = np.array([xs[i + 1], *rb[k]]) * MM
            p3 = np.array([xs[i + 1], *rb[j]]) * MM
            tris.append((p0, p1, p2))
            tris.append((p0, p2, p3))
    fan_cap(rings[0], xs[0], True, tris)
    fan_cap(rings[-1], xs[-1], False, tris)
    return np.array(tris)


def _fairing_full_ring(x):
    """整环截面：右半包络点 + 镜像 bump 点 → 全凸包 → 整体重采样（无镜像缝合边）"""
    from lib.profiles import (convex_offset, convex_hull, resample, rotate_to_anchor)
    arch = convex_offset(FA._rm_outline(x), P.FA_GAP_M)
    pts = list(arch)
    if x >= P.YR_INSTALL[0]:
        pts += convex_offset(FA._yr_outline(x), P.FA_GAP_U)
        if x >= P.YR_INSTALL[0] + P.YR_SERN_X0:
            xl = min(x - P.YR_INSTALL[0], 1800.0)
            wb = P.YR_CHINE_WF * interp(P.YR_X, P.YR_S, xl)
            zb = P.YR_INSTALL[2] - P.YR_SERN_D * min(1.0, (xl - P.YR_SERN_X0) /
                                                     (P.YR_SERN_X1 - P.YR_SERN_X0)) - 4.0
            pts += [(wb + P.FA_GAP_U, zb), (0.55 * wb, zb)]
    ss = lambda t: (min(max(t, 0.0), 1.0) ** 2) * (3 - 2 * min(max(t, 0.0), 1.0))
    m = P.FA_SOFT

    def soft(x0, x1):
        if x <= x0 - m or x >= x1 + m:
            return 0.0
        if x < x0:
            return ss(1 - (x0 - x) / m)
        if x > x1:
            return ss(1 - (x - x1) / m)
        return 1.0

    w_br = soft(2900.0, 4100.0)
    w_vt = soft(4010.0, 4360.0)
    w_wg = soft(3640.0, 4423.0)
    w_tw = soft(3800.0, 4330.0)

    def bump(a, t, w):
        return (a[0] + w * (t[0] - a[0]), a[1] + w * (t[1] - a[1]))

    if w_br > 0:
        pts += [bump((150, 640), (265, 690), w_br), bump((150, 640), (200, 685), w_br)]
    if w_vt > 0:
        pts += [bump((320, 655), (452, 996), w_vt), bump((320, 655), (385, 975), w_vt)]
    if w_wg > 0:
        pts += [bump((340, 700), (512, 1074), w_wg), bump((340, 700), (465, 1052), w_wg)]
    if w_tw > 0:
        pts += [bump((1100, 2), (1322, 302), w_tw), bump((1100, 2), (1190, 288), w_tw)]
    hz = convex_hull(pts)
    hz = [(y, min(max(z, -1.5), P.FA_ZMAX - 5.0)) for (y, z) in hz]
    return resample(rotate_to_anchor(hz, anchor=(1e6, 0.0)), 176)


def build_fairing():
    st = FA._stations()
    rings = [_fairing_full_ring(x) for x in st]
    # 起始站：环最小点距 ≥0.3mm（头部 6mm 细缝环扇形盖会退化），弃用更早的细站
    i0 = 0
    while _min_spacing(rings[i0]) < 3e-4 and i0 < len(st) - 2:
        i0 += 1
    st, rings = st[i0:], rings[i0:]
    tris = []
    for i in range(len(st) - 1):
        ra, rb = rings[i], rings[i + 1]
        n = len(ra)
        for j in range(n):
            k = (j + 1) % n
            p0 = np.array([st[i], *ra[j]]) * MM
            p1 = np.array([st[i], *ra[k]]) * MM
            p2 = np.array([st[i + 1], *rb[k]]) * MM
            p3 = np.array([st[i + 1], *rb[j]]) * MM
            tris.append((p0, p1, p2))
            tris.append((p0, p2, p3))
    fan_cap(rings[0], st[0], True, tris)
    fan_cap(rings[-1], st[-1], False, tris)
    return np.array(tris)


def orient_global(tris):
    """BFS 绕向传播：共享边同向的邻面翻转至全一致；体积为负则整体翻转"""
    key = lambda p: (round(p[0], 6), round(p[1], 6), round(p[2], 6))
    faces = [[key(p) for p in t] for t in tris]
    edge_map = {}
    for fi, f in enumerate(faces):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            e = tuple(sorted((f[a], f[b])))
            edge_map.setdefault(e, []).append(fi)
    flipped = [False] * len(faces)
    seen = set()
    from collections import deque
    for seed in range(len(faces)):
        if seed in seen:
            continue
        seen.add(seed)
        q = deque([seed])
        while q:
            fi = q.popleft()
            f = faces[fi]
            for a, b in ((0, 1), (1, 2), (2, 0)):
                e = tuple(sorted((f[a], f[b])))
                for fj in edge_map[e]:
                    if fj == fi or fj in seen:
                        continue
                    g = faces[fj]
                    d_e = (f[a], f[b])
                    d_g = None
                    for x, y in ((0, 1), (1, 2), (2, 0)):
                        if (g[x], g[y]) == d_e:
                            d_g = (g[x], g[y])
                    if d_g is not None:      # 同向 → 翻转邻面
                        faces[fj] = [g[2], g[1], g[0]]
                        flipped[fj] = not flipped[fj]
                    seen.add(fj)
                    q.append(fj)
    out = np.array([[list(p) for p in f] for f in faces], float)
    vol = sum(np.dot(t[0], np.cross(t[1], t[2])) for t in out) / 6.0
    if vol < 0:
        out = out[:, ::-1, :]
        vol = -vol
    return out, vol


def check_manifold(tris):
    """每条边恰出现 2 次；体积=散度定理"""
    edges = {}
    for t in tris:
        for a, b in ((0, 1), (1, 2), (2, 0)):
            va = tuple(np.round(t[a], 6))
            vb = tuple(np.round(t[b], 6))
            e = tuple(sorted((va, vb)))
            edges[e] = edges.get(e, 0) + 1
    bad = sum(1 for v in edges.values() if v != 2)
    vol = sum(np.dot(t[0], np.cross(t[1], t[2])) for t in tris) / 6.0
    return bad, vol, len(edges)


def write_stl(tris, path):
    with open(path, "wb") as f:
        f.write(b"watertight analytic".ljust(80, b"\0"))
        f.write(struct.pack("<I", len(tris)))
        for t in tris:
            nv = np.cross(t[1] - t[0], t[2] - t[0])
            nv /= np.linalg.norm(nv)
            f.write(struct.pack("<3f", *nv))
            for p in t:
                f.write(struct.pack("<3f", *p))
            f.write(struct.pack("<H", 0))


def write_obj(tris, path):
    with open(path, "w") as f:
        f.write("# watertight analytic mesh (mm->m)\n")
        for t in tris:
            for p in t:
                f.write(f"v {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
    with open(path, "a") as f:
        for i in range(len(tris)):
            f.write(f"f {3*i+1} {3*i+2} {3*i+3}\n")


if __name__ == "__main__":
    for tag, builder in (("c1_body", build_c1), ("fairing", build_fairing)):
        tris0 = builder()
        tris, vol = orient_global(tris0)
        bad, vol2, ne = check_manifold(tris)
        print(f"[{tag}] 三角形 {len(tris)} | 非流形边 {bad} | 体积 {vol*1000:.1f} L "
              f"({'闭合OK' if bad == 0 and vol > 0 else 'OPEN!'})")
        write_stl(tris, os.path.join(OUT, tag + ".stl"))
        write_obj(tris, os.path.join(OUT, tag + ".obj"))
    print("[输出] export/mesh/")
