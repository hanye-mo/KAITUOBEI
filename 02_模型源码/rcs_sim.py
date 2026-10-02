# -*- coding: utf-8 -*-
"""迅雷系统 RCS 物理光学（PO）面元法仿真试验 V2
对象：影刃单机 C2（yr_uav.stl）/ 锐矛单机 C1（rm_missile.stl）/ 组合体 SC_A（sc_a.stl）
方法：单站 PO 面元近似（Crispin–Maffett）：
    σ(k̂) = (4π/λ²)·|Σᵢ Γᵢ(n̂ᵢ·k̂)Aᵢ·exp(j2k·k̂·rᵢ)|²，仅计被照射面元 (n̂ᵢ·k̂<0)
    标量实系数材质下 σ 与 Γ² 成正比 → 每组几何×频率只解一次复和 S，三材质按 Γ² 缩放
试验矩阵：3 对象 × 3 频率（8/10/12 GHz）× 方位角 −90°..+90°（0°=鼻锥向，0.5° 步长）
标定：金属球 σ=πr² 解析解
局限：PO 高频近似，不含边缘绕射（PTD）；腔体贡献为上界（背向剔除遮蔽）
输出：export/rcs/ rcs_data.csv + 5 张图
"""
import struct
import os
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
STL = os.path.join(HERE, "export", "stl")
OUT = os.path.join(HERE, "export", "rcs")
os.makedirs(OUT, exist_ok=True)

THRESH_DB = 10 * np.log10(0.008)          # −21.07 dBsm
FREQS = [8e9, 10e9, 12e9]
MATS = [("全金属", 1.0), ("涂层−10dB", 10 ** (-10 / 20)), ("涂层−15dB", 10 ** (-15 / 20))]
AZ = np.radians(np.arange(-90.0, 90.01, 0.5))
TARGET_EDGE = 0.012                        # 面元细分目标边长 12mm（≥2.5λ/10GHz 面内）


# ---------- STL ----------
def load_stl(path):
    with open(path, "rb") as f:
        data = f.read()
    n = struct.unpack("<I", data[80:84])[0]
    arr = np.frombuffer(data[84:84 + n * 50], dtype=np.uint8).reshape(n, 50)
    # STL 单位 mm → 统一换算为 m（与波长一致）
    return arr[:, 12:48].copy().view("<f4").reshape(n, 3, 3).astype(np.float64) / 1000.0


# ---------- 细分：面积等效边长判定 + 最长边一分二 ----------
def subdivide(tris, max_edge, tag=""):
    tris = tris.reshape(-1, 3, 3)
    a = 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    ok = a > 1e-12                                  # 过滤退化面（布尔残留）
    tris = tris[ok]
    for it in range(10):
        p0, p1, p2 = tris[:, 0], tris[:, 1], tris[:, 2]
        cr = np.cross(p1 - p0, p2 - p0)
        area = 0.5 * np.linalg.norm(cr, axis=1)
        eq = np.sqrt(4.0 * area / np.sqrt(3.0))     # 等效边长
        bad = eq > max_edge
        if not bad.any():
            print(f"[细分] {tag}: {it} 轮 → {len(tris)} 面")
            return tris
        keep, bt = tris[~bad], tris[bad]
        ab, bb, cb = bt[:, 0], bt[:, 1], bt[:, 2]
        eb = np.stack([np.linalg.norm(bb - ab, axis=1),
                       np.linalg.norm(cb - bb, axis=1),
                       np.linalg.norm(ab - cb, axis=1)], axis=1)
        imax = eb.argmax(axis=1)
        p0s = np.where(imax[:, None] == 0, ab, np.where(imax[:, None] == 1, bb, cb))
        p1s = np.where(imax[:, None] == 0, bb, np.where(imax[:, None] == 1, cb, ab))
        c2s = np.where(imax[:, None] == 0, cb, np.where(imax[:, None] == 1, ab, bb))
        mid = (p0s + p1s) / 2
        tris = np.concatenate([keep,
                               np.stack([p0s, mid, c2s], axis=1),
                               np.stack([mid, p1s, c2s], axis=1)], axis=0)
    print(f"[细分] {tag}: 达到轮次上限 → {len(tris)} 面")
    return tris


def prep(tris):
    cen = tris.mean(axis=1)
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    area = 0.5 * np.linalg.norm(nrm, axis=1)
    good = area > 1e-9
    tris, area, nrm = tris[good], area[good], nrm[good]
    nrm /= (2 * area[:, None])
    ref = (tris.min(axis=(0, 1)) + tris.max(axis=(0, 1))) / 2
    return cen[good] - ref, nrm, area


def sweep_metal(cen, nrm, area, khat_list):
    """全金属复和 S(θ,ω)；材质缩放后处理。返回 (n_freq, n_az) 线性 σ"""
    out = np.zeros((len(FREQS), len(khat_list)))
    for j, khat in enumerate(khat_list):
        ndk = nrm @ khat
        lit = ndk < 0
        nda = (-ndk[lit]) * area[lit]
        cl = cen[lit]
        for i, f in enumerate(FREQS):
            k = 2 * np.pi * f / 3e8
            S = np.sum(nda * np.exp(2j * k * (cl @ khat)))
            out[i, j] = 4 * np.pi / (3e8 / f) ** 2 * abs(S) ** 2
    return out


def po_single(cen, nrm, area, khat, freq):
    ndk = nrm @ khat
    lit = ndk < 0
    k = 2 * np.pi * freq / 3e8
    S = np.sum((-ndk[lit]) * area[lit] * np.exp(2j * k * (cen[lit] @ khat)))
    return 4 * np.pi / (3e8 / freq) ** 2 * abs(S) ** 2


def uv_sphere(r, seg=200):
    th = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    ph = np.linspace(0, np.pi, seg // 2)
    tris = []
    for i in range(seg):
        for j in range(len(ph) - 1):
            p = lambda a, b: (r * np.sin(ph[b]) * np.cos(th[a]), r * np.sin(ph[b]) * np.sin(th[a]), r * np.cos(ph[b]))
            tris.append([p(i, j), p((i + 1) % seg, j), p((i + 1) % seg, j + 1)])
            tris.append([p(i, j), p((i + 1) % seg, j + 1), p(i, j + 1)])
    return np.array(tris)


# ================= 主流程 =================
if __name__ == "__main__":
    # 1) 球标定
    tri_s = uv_sphere(0.15)
    cen, nrm, area = prep(tri_s)
    sim = 10 * np.log10(po_single(cen, nrm, area, np.array([1.0, 0, 0]), 10e9))
    ana = 10 * np.log10(np.pi * 0.15 ** 2)
    print(f"[标定] 金属球 r=150mm @10GHz: PO {sim:.2f} dBsm vs 解析 {ana:.2f} dBsm 偏差 {sim - ana:+.2f} dB")

    # 2) 三对象
    targets = {
        "影刃（C2，翼展开）": os.path.join(STL, "yr_uav.stl"),
        "锐矛（C1）": os.path.join(STL, "rm_missile.stl"),
        "组合体（SC_A）": os.path.join(STL, "sc_a.stl"),
    }
    az_deg = np.degrees(AZ)
    results = {}                      # {obj: (n_freq, n_az) σ 全金属}
    for tag, path in targets.items():
        tris = subdivide(load_stl(path), TARGET_EDGE, tag)
        cen, nrm, area = prep(tris)
        results[tag] = sweep_metal(cen, nrm, area,
                                   [np.array([np.cos(a), np.sin(a), 0.0]) for a in AZ])
        print(f"[完成] {tag}")

    # 3) 统计（材质缩放：σ_mat = Γ²·σ_metal）
    print("\n===== 结果统计（dBsm） =====")
    stats = {}
    for tag, r in results.items():
        for name, g in MATS:
            for i, f in enumerate(FREQS):
                db = 10 * np.log10(r[i] * g ** 2)
                front = db[(az_deg >= -15) & (az_deg <= 15)]
                key = (tag, name, f)
                stats[key] = dict(peak=db.max(), peak_az=az_deg[db.argmax()],
                                  mean=10 * np.log10(np.mean(10 ** (db / 10))),
                                  fmean=10 * np.log10(np.mean(10 ** (front / 10))),
                                  over=100 * np.mean(db > THRESH_DB))
                print(f"{tag:14s} {name:8s} {f/1e9:2.0f}GHz: 峰值 {stats[key]['peak']:6.1f}"
                      f"@{stats[key]['peak_az']:+6.1f}° | 均值 {stats[key]['mean']:6.1f} | "
                      f"鼻向±15°均值 {stats[key]['fmean']:6.1f} | 超−21dBsm 占比 {stats[key]['over']:5.1f}%")

    # 4) CSV
    with open(os.path.join(OUT, "rcs_data.csv"), "w", encoding="utf-8") as f:
        cols = [f"{t}|{m}|{fr/1e9:.0f}GHz_dBsm" for t in targets for m, _ in MATS for fr in FREQS]
        f.write("azimuth_deg," + ",".join(cols) + "\n")
        for j in range(len(AZ)):
            row = [f"{az_deg[j]:.1f}"]
            for t in targets:
                for m, g in MATS:
                    for i in range(len(FREQS)):
                        row.append(f"{10*np.log10(results[t][i, j]*g**2):.2f}")
            f.write(",".join(row) + "\n")

    C = {"影刃（C2，翼展开）": "#c0392b", "锐矛（C1）": "#2471a3", "组合体（SC_A）": "#7d3c98"}

    # 图1 三对象对比 @10GHz 全金属
    fig, ax = plt.subplots(figsize=(11.5, 6))
    for t, col in C.items():
        ax.plot(az_deg, 10 * np.log10(results[t][1]), label=t, color=col, lw=1.3)
    ax.axhline(THRESH_DB, color="k", ls="--", lw=1.4, label="影刃设计门限 −21 dBsm (0.008 m²)")
    ax.axvspan(-15, 15, color="orange", alpha=0.08)
    ax.set_xlabel("方位角（°，0°=鼻锥向）"); ax.set_ylabel("RCS (dBsm)")
    ax.set_title("迅雷系统三状态单站 RCS 对比 — 10 GHz（X 波段），全金属工况")
    ax.set_xlim(-90, 90); ax.grid(alpha=0.3); ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "rcs_compare_10GHz.png"), dpi=150)

    # 图2 影刃材质对比
    fig, ax = plt.subplots(figsize=(11.5, 6))
    t = "影刃（C2，翼展开）"
    for (m, g), c in zip(MATS, ("#c0392b", "#2471a3", "#1e8449")):
        ax.plot(az_deg, 10 * np.log10(results[t][1] * g ** 2), label=f"影刃 {m}", color=c, lw=1.2)
    ax.plot(az_deg, 10 * np.log10(results["组合体（SC_A）"][1]), color="#7d3c98",
            lw=1.0, alpha=0.55, label="组合体（参照）")
    ax.axhline(THRESH_DB, color="k", ls="--", lw=1.4, label="设计门限 −21 dBsm")
    ax.axvspan(-15, 15, color="orange", alpha=0.08, label="前向重点区 ±15°")
    ax.set_xlabel("方位角（°，0°=鼻锥向）"); ax.set_ylabel("RCS (dBsm)")
    ax.set_title("影刃隐身工况对比 — 10 GHz（涂层反射率对整机 RCS 的抑制作用）")
    ax.set_xlim(-90, 90); ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="upper center", ncol=2)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "rcs_yr_materials_10GHz.png"), dpi=150)

    # 图3 频率影响（影刃全金属）
    fig, ax = plt.subplots(figsize=(11.5, 6))
    for i, fr in enumerate(FREQS):
        ax.plot(az_deg, 10 * np.log10(results[t][i]), lw=1.1, label=f"{fr/1e9:.0f} GHz")
    ax.axhline(THRESH_DB, color="k", ls="--", lw=1.4, label="设计门限 −21 dBsm")
    ax.set_xlabel("方位角（°，0°=鼻锥向）"); ax.set_ylabel("RCS (dBsm)")
    ax.set_title("频率对影刃 RCS 的影响 — 全金属工况（X 波段三频点）")
    ax.set_xlim(-90, 90); ax.grid(alpha=0.3); ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "rcs_yr_freq.png"), dpi=150)

    # 图4 极图（10GHz 全金属 三对象）
    fig = plt.figure(figsize=(8.5, 8.5))
    ax = fig.add_subplot(111, polar=True)
    th = np.radians(az_deg)
    for tg, col in C.items():
        rdb = 10 * np.log10(results[tg][1])
        ax.plot(np.concatenate([th, -th[::-1]]), np.concatenate([rdb, rdb[::-1]]),
                color=col, lw=1.1, label=tg)
    ax.set_thetamin(-90); ax.set_thetamax(90)
    ax.set_rlim(-50, 15); ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
    ax.set_title("三状态 RCS 极图（10 GHz，全金属，0°=鼻向）", pad=18)
    ax.legend(loc="lower left", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "rcs_polar_10GHz.png"), dpi=150)

    # 图5 标定
    fig, ax = plt.subplots(figsize=(6, 4.2))
    bars = ax.bar(["解析 πr²", "PO 仿真"], [ana, sim], color=["#7f8c8d", "#2471a3"], width=0.5)
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.15,
                f"{b.get_height():.2f} dBsm", ha="center", fontsize=10)
    ax.set_ylabel("RCS (dBsm)")
    ax.set_title(f"求解器标定：金属球 r=150 mm @ 10 GHz（偏差 {sim - ana:+.2f} dB）")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "rcs_sphere_validation.png"), dpi=150)

    print("\n[输出] CSV + 5 张图 →", OUT)
