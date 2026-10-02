# -*- coding: utf-8 -*-
"""T2 气动估算 V2b：解析表面牛顿面元法（不经 STL，规避布尔残留；法向全部解析给定）
对象：C1 锐矛单机 / A′ 捆绑滑翔态
方法：牛顿流 Cp=2(n̂·v̂)²（迎风面）+ 摩阻 Cd_f=0.002·S_wet/A_ref + 底阻 Cd_b=0.12·S_base/A_ref
法向来源：机身/罩=剖面折线外法向（棱柱近似），前缘管=管面向径，舵面=定向平板
标定：二维楔 牛顿 vs 精确斜激波（θ-β-M 牛顿迭代）
输出：export/aero/ aero_polar.png aero_ld.csv + 设计点对照
局限：牛顿法为 0 阶高频近似（楔标定 ±40% 量级）、无粘无升力面理论前缘吸力——结果为量级校核
运行：python aero_analytic.py
"""
import os
import sys
import types
import math
import numpy as np

for nm in ("bpy", "bmesh", "mathutils"):
    stub = types.ModuleType(nm)
    stub.__getattr__ = lambda attr: None
    sys.modules.setdefault(nm, stub)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

from lib import params as P
from lib.profiles import interp, scaled_arch
from lib.paths import export_dir
from builders.missile import _nose_g
from builders import fairing as FA

OUT = export_dir("aero")
os.makedirs(OUT, exist_ok=True)
A_REF = 5.85
ALPHAS = np.arange(0.0, 20.01, 0.5)
MM = 1e-3


def _ring2d(x):
    s = interp(P.RM_X, P.RM_S, x) * _nose_g(x)
    h = interp(P.RM_X, P.RM_H, x) * _nose_g(x)
    if x <= 1e-6:
        s = h = 0.5
    return scaled_arch(s, h, P.RM_DECK_Z, p=P.RM_SE_P, q=P.RM_SE_Q, n=36)


def _outward_normals(ring):
    """闭合 CCW 剖面折线每点的外法向（2D）"""
    n = len(ring)
    out = []
    for i in range(n):
        p0, p2 = ring[(i - 1) % n], ring[(i + 1) % n]
        t = np.array([p2[0] - p0[0], p2[1] - p0[1]], float)
        L = np.linalg.norm(t)
        t = t / L if L > 1e-12 else np.array([1.0, 0.0])
        out.append((t[1], -t[0]))                      # CCW 外法向
    return out


def strip_grid(ring_a, ring_b, xa, xb, mask=None):
    """两剖面间条带面元；法向=剖面外法向（棱柱近似，锥度忽略）。
    mask(nz)->bool 过滤（如只要 z<0 平底或只要上拱）"""
    na, nb = _outward_normals(ring_a), _outward_normals(ring_b)
    cen, nrm, are = [], [], []
    n = len(ring_a)
    for j in range(n):
        k = (j + 1) % n
        if mask is not None and not (mask(ring_a[j][1], ring_a[k][1])):
            continue
        p0 = np.array([xa, *ring_a[j]]) * MM
        p1 = np.array([xa, *ring_a[k]]) * MM
        p2 = np.array([xb, *ring_b[k]]) * MM
        p3 = np.array([xb, *ring_b[j]]) * MM
        a = 0.5 * (np.linalg.norm(np.cross(p1 - p0, p3 - p0)) +
                   np.linalg.norm(np.cross(p1 - p3, p2 - p3)))
        if a < 1e-10:
            continue
        nv = np.array([0.0, (na[j][0] + na[k][0]) / 2, (na[j][1] + na[k][1]) / 2])
        nv /= np.linalg.norm(nv)
        cen.append((p0 + p1 + p2 + p3) / 4)
        nrm.append(nv)
        are.append(a)
    if not cen:
        e = np.zeros((0, 3))
        return e, e.copy(), np.zeros(0)
    return np.array(cen), np.array(nrm), np.array(are)


def body_strips(x0, x1, dx=30.0, belly=False, upper=False):
    xs = np.arange(x0, x1 + 1e-6, dx)
    cen, nrm, are = [], [], []
    for i in range(len(xs) - 1):
        ra, rb = _ring2d(xs[i]), _ring2d(xs[i + 1])
        m = None
        if belly and not upper:
            m = lambda za, zb: za < -1e-9 and zb < -1e-9
        elif upper and not belly:
            m = lambda za, zb: za > -1e-9 and zb > -1e-9
        c, nn, aa = strip_grid(ra, rb, xs[i], xs[i + 1], m)
        cen.append(c); nrm.append(nn); are.append(aa)
    return (np.concatenate(cen), np.concatenate(nrm), np.concatenate(are))


def le_tubes(x0=34.6, x1=1950.0, nseg=30, nring=12, full=False):
    """前缘钝化管（双侧，r18），法向=管面向径"""
    if full:
        x1 = 4494.0
    cen, nrm, are = [], [], []
    for side in (1, -1):
        xs = np.linspace(x0, x1, nseg)
        cs = np.array([[x, side * interp(P.RM_X, P.RM_S, x), 0.0] for x in xs]) * MM
        for i in range(nseg - 1):
            for t in range(nring):
                t2 = (t + 1) % nring
                ang = [2 * math.pi * tt / nring for tt in (t, t2)]
                # 局部标架（路径切向 d，副法向 u≈z 叉乘）
                d = cs[min(i + 1, nseg - 1)] - cs[max(i - 1, 0)]
                d /= np.linalg.norm(d)
                u = np.cross(d, (0, 0, 1.0))
                if np.linalg.norm(u) < 1e-9:
                    u = np.array([0.0, 1.0, 0.0])
                u /= np.linalg.norm(u)
                w = np.cross(d, u)
                r = P.RM_LE_R * MM

                def pt(ii, a):
                    return cs[ii] + r * (u * math.cos(a) + w * math.sin(a))

                p0, p1 = pt(i, ang[0]), pt(i, ang[1])
                p2, p3 = pt(i + 1, ang[1]), pt(i + 1, ang[0])
                a0 = 0.5 * (np.linalg.norm(np.cross(p1 - p0, p3 - p0)) +
                            np.linalg.norm(np.cross(p1 - p3, p2 - p3)))
                if a0 < 1e-10:
                    continue
                cc = (p0 + p1 + p2 + p3) / 4
                nv = cc - (cs[i] + cs[i + 1]) / 2
                nv /= np.linalg.norm(nv)
                cen.append(cc); nrm.append(nv); are.append(a0)
    return np.array(cen), np.array(nrm), np.array(are)


def flat_plate(pts, normal_sign):
    p = np.asarray(pts, float) * MM
    c0 = np.cross(p[1] - p[0], p[2] - p[0])
    a = 0.5 * np.linalg.norm(c0)
    nv = c0 / (2 * a) * normal_sign
    return p.mean(axis=0), nv, a * 2


def assemble(cfg):
    parts = []
    if cfg.startswith("C1"):
        parts.append(body_strips(0, 4500))                       # 全机身（含平底+上拱）
        parts.append(le_tubes(full=True))
        ang = math.atan2(1300, 4500)
        xv = np.array([math.cos(ang), math.sin(ang), 0.0])
        for side in (1, -1):
            yv = np.array([-math.sin(ang) * side, math.cos(ang) * side, 0.0])
            base = np.array([P.RM_TW_X0, side * (interp(P.RM_X, P.RM_S, P.RM_TW_X0) + 2), 10.0]) * MM
            # 小翼平面：根弦沿前缘线，外倾 35°（与铅垂面夹角）
            span_v = yv * math.cos(math.radians(P.RM_TW_CANT)) + np.array([0, 0, 1.0]) * \
                math.sin(math.radians(P.RM_TW_CANT))
            r0, r1 = P.RM_TW_ROOTC, P.RM_TW_TIPC
            q = [base, base + xv * r0,
                 base + xv * (P.RM_TW_LEOFF + r1) + span_v * P.RM_TW_SPAN,
                 base + xv * P.RM_TW_LEOFF + span_v * P.RM_TW_SPAN]
            c, n, a = flat_plate(q, side)
            parts.append((c[None], n[None], np.array([a])))
        for side in (1, -1):
            y0 = min(side * P.RM_ELEV_Y, side * P.RM_ELEV_Y1)
            y1 = max(side * P.RM_ELEV_Y, side * P.RM_ELEV_Y1)
            q = [[P.RM_ELEV_X0, y0, 0], [P.RM_ELEV_X1, y0, 0],
                 [P.RM_ELEV_X1, y1, 0], [P.RM_ELEV_X0, y1, 0]]
            c, n, a = flat_plate(q, -1)
            parts.append((c[None], n[None], np.array([a])))
    else:
        parts.append(body_strips(0, 4500, belly=True))           # 弹平底
        parts.append(body_strips(0, 1950, upper=True))           # 罩外露鼻段上拱
        parts.append(le_tubes(x1=1950.0))
        st = FA._stations()
        cen, nrm, are = [], [], []
        prev = None
        for x in st:
            half = FA._half(x) if x < 4512 else FA._half(4475)
            ring = [(y, z) for (y, z) in half] + [(-y, z) for (y, z) in reversed(half[:-1])]
            if prev is not None:
                c, n, a = strip_grid(prev, ring, prev_x, x)
                cen.append(c); nrm.append(n); are.append(a)
            prev, prev_x = ring, x
        parts.append((np.concatenate(cen), np.concatenate(nrm), np.concatenate(are)))
    cen = np.concatenate([p[0] for p in parts])
    nrm = np.concatenate([p[1] for p in parts])
    are = np.concatenate([p[2] for p in parts])
    return cen, nrm, are, are.sum()


def forces(cen, nrm, are, alpha_deg):
    """流向系分解：D=F·v̂（阻力），L=F·l̂（升力，l̂=(-sinα,0,cosα)）"""
    a = math.radians(alpha_deg)
    v = np.array([math.cos(a), 0.0, math.sin(a)])
    l = np.array([-math.sin(a), 0.0, math.cos(a)])
    ndv = nrm @ v
    lit = ndv < 0
    cp = 2 * ndv[lit] ** 2 * are[lit]
    F = -(cp[:, None] * nrm[lit]).sum(axis=0)
    return F @ l / A_REF, F @ v / A_REF


def oblique_shock_cp(M, delta):
    g = 1.4
    d = math.radians(delta)
    b = math.asin(1.0 / M) + 0.5 * d
    for _ in range(100):
        def F(bb):
            sb, cb = math.sin(bb), math.cos(bb)
            t = 2 / math.tan(bb) * (M * M * sb * sb - 1) / (M * M * (g + math.cos(2 * bb)) + 2)
            return math.atan(t) - d
        f, h = F(b), 1e-7
        f2 = F(b + h)
        b -= f * h / (f2 - f)
        b = max(b, math.asin(1.0 / M) + 1e-6)
    p2 = 1 + 2 * g / (g + 1) * (M * M * math.sin(b) ** 2 - 1)
    return 2 / (g * M * M) * (p2 - 1)


def main():
    print("== 标定：牛顿 Cp=2sin²δ vs 精确斜激波 ==")
    for M in (6.0, 8.0):
        for d in (10, 15, 20):
            n_ = 2 * math.sin(math.radians(d)) ** 2
            e_ = oblique_shock_cp(M, d)
            print(f"  M{M:.0f} δ{d:2d}°: 牛顿 {n_:.3f} vs 精确 {e_:.3f} ({100*(n_-e_)/e_:+.0f}%)")

    res = {}
    for cfg, (claim, a_des) in {"C1 锐矛单机": ((2.6, 2.8), 5.0),
                                 "A′ 捆绑滑翔": ((2.2, 2.4), 7.0)}.items():
        cen, nrm, are, swet = assemble(cfg)
        cd_f = 0.002 * swet / A_REF
        cd_b = 0.12 * 1.23 / A_REF
        rows = []
        for al in ALPHAS:
            cl, cdp = forces(cen, nrm, are, al)
            cd = cdp + cd_f + cd_b
            rows.append((al, cl, cdp, cd_f, cd_b, cl / cd if cd > 1e-9 else np.nan))
        res[cfg] = np.array(rows)
        ld = res[cfg][:, 5]
        imax = np.nanargmax(ld)
        i_des = np.argmin(np.abs(ALPHAS - a_des))
        r = res[cfg][i_des]
        print(f"\n[{cfg}] 面元 {len(cen)}  S_wet={swet:.1f} m²  Cd_f={cd_f:.4f}  Cd_b={cd_b:.4f}")
        print(f"  设计点 α={a_des}°: CL={r[1]:.3f} CD={r[2]+r[3]+r[4]:.3f} L/D={r[5]:.2f}"
              f"  | 方案断言 {claim[0]}~{claim[1]}")
        print(f"  最优: L/D={ld[imax]:.2f} @ α={ALPHAS[imax]:.0f}°（CL={res[cfg][imax,1]:.3f}）")

    fig, axs = plt.subplots(1, 2, figsize=(12, 5))
    cols = {"C1 锐矛单机": "#2471a3", "A′ 捆绑滑翔": "#c0392b"}
    csv = ["config,alpha_deg,CL,CDp,CDf,CDb,LD"]
    for cfg, rows in res.items():
        axs[0].plot(rows[:, 0], rows[:, 1], color=cols[cfg], lw=1.4, label=cfg)
        axs[1].plot(rows[:, 0], rows[:, 5], color=cols[cfg], lw=1.6, label=cfg)
        for r in rows:
            csv.append(f"{cfg},{r[0]:.1f},{r[1]:.4f},{r[2]:.4f},{r[3]:.4f},{r[4]:.4f},{r[5]:.4f}")
    axs[0].set_xlabel("迎角 α (°)"); axs[0].set_ylabel("CL"); axs[0].grid(alpha=0.3); axs[0].legend(fontsize=9)
    axs[0].set_title("升力线（解析面元牛顿法）")
    axs[1].axhspan(2.6, 2.8, color="#2471a3", alpha=0.10, label="C1 断言带")
    axs[1].axhspan(2.2, 2.4, color="#c0392b", alpha=0.10, label="A′ 断言带")
    axs[1].set_xlabel("迎角 α (°)"); axs[1].set_ylabel("L/D（含摩阻+底阻）")
    axs[1].set_title("升阻比 vs 方案断言"); axs[1].grid(alpha=0.3); axs[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "aero_polar.png"), dpi=150)
    with open(os.path.join(OUT, "aero_ld.csv"), "w", encoding="utf-8") as f:
        f.write("\n".join(csv) + "\n")
    print("\n[输出] export/aero/ aero_polar.png aero_ld.csv")


if __name__ == "__main__":
    main()
