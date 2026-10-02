# -*- coding: utf-8 -*-
"""真实环境 RCS 修正仿真：温度分区涂层 + 全方位扫描（含尾向）
修正1：影刃用 sc_c2.stl（外翼展开态，上轮误用收拢态 yr_uav.stl）
修正2：涂层按 §2.6 温度场分区退化（高温区吸波体保持 -8dB / 腹面 -10 / 背面 -12，
        替代上轮全域均匀 -15dB 的乐观假设）
等离子体鞘层：解析计算 f_p，判定 X 波段欠密/过密（不入面元模型）
输出：export/rcs/ rcs_realistic.csv + rcs_realistic_10GHz.png + 控制台统计
"""
import os
import sys
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

from rcs_sim import load_stl, subdivide, prep, THRESH_DB

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from lib.paths import export_dir

OUT = export_dir("rcs")
FREQS = [8e9, 10e9, 12e9]
AZ = np.radians(np.arange(-180.0, 180.01, 0.5))
INSTALL = np.array([2.7, 0.0, 0.68])           # 影刃全局安装位（m）

# 分区涂层（按方案 §2.6 温度场：前缘1990℃ / 腹面1450℃ / 背面900℃；
# 公开高温吸波体性能：1600-1800K 下反射损耗保持 8~12dB）
ZONE_G = {"高温区(鼻/翼/尾缘)": 10 ** (-8 / 20),
          "腹面压缩面": 10 ** (-10 / 20),
          "背面机身": 10 ** (-12 / 20)}


def classify(cen):
    """面元分区（cen 为以安装位为原点的局部坐标, m）
    高温区=鼻锥(lx<0.35)/外翼(|ly|>0.50)/垂尾(lx∈[1.31,1.61] 且 lz>0.15)"""
    lx, ly, lz = cen
    if lx < 0.35 or abs(ly) > 0.50 or (1.31 < lx < 1.61 and lz > 0.15):
        return 0                                # 鼻锥/外翼/垂尾（薄热结构）
    if lz < 0.05:
        return 1                                # 腹面
    return 2                                    # 背面


def main():
    # ---- 等离子体鞘层解析判定 ----
    print("== 等离子体鞘层判定（f_p = 8.98·√n_e）==")
    for ne, tag in ((1e9, "M6 弱电离区（典型）"), (1e11, "驻点附近峰值量级"),
                    (1e13, "M10+ 量级"), (1.24e18, "达到 10GHz 过密所需")):
        print(f"  n_e={ne:.1e} /m³ ({tag}): f_p = {8.98*np.sqrt(ne)/1e9:.3g} GHz")
    print("  → M6.2@31km 电子密度 ~1e9-1e11 /m³，f_p≪10GHz：欠密等离子体，"
          "X 波段近透明（<1dB）；也低于 S 波段遥测频点 → 无通信黑障\n")

    # ---- 网格（先滤退化面；反转 SC_C2 的 -9° 迎角展示旋转回 α=0 再分区）----
    tris = subdivide(load_stl(export_dir(os.path.join("stl", "sc_c2.stl"))), 0.012, "影刃展开态")
    araw = 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
    tris = tris[araw > 1e-9]
    th = np.radians(9.0)                       # 撤销 rig2 的 R_y(−9°)
    loc = tris - INSTALL                        # (n,3,3) 平移到局部
    loc = np.stack([loc[..., 0] * np.cos(th) + loc[..., 2] * np.sin(th),
                    loc[..., 1],
                    -loc[..., 0] * np.sin(th) + loc[..., 2] * np.cos(th)], axis=-1)
    raw_cen = loc.mean(axis=1)
    print(f"[局部系] x[{raw_cen[:,0].min():.2f},{raw_cen[:,0].max():.2f}] "
          f"y[{raw_cen[:,1].min():.2f},{raw_cen[:,1].max():.2f}] "
          f"z[{raw_cen[:,2].min():.2f},{raw_cen[:,2].max():.2f}]")
    cen, nrm, area = prep(tris)
    zone = np.array([classify(c) for c in raw_cen])
    for i, zn in enumerate(ZONE_G):
        print(f"[分区] {zn}: {100*np.mean(zone == i):.1f}% 面元, Γ={20*np.log10(ZONE_G[zn]):.0f}dB")

    # ---- 逐角度：分 zone 复和（含 U2 鼻帽工况：鼻区 lx<0.35 再叠加 −8dB）----
    nz = len(ZONE_G)
    nose_m = (raw_cen[:, 0] < 0.35)
    res = {k: np.zeros((len(FREQS), len(AZ))) for k in
           ("全金属", "均匀涂层-15dB", "温度分区涂层", "温度分区+鼻帽−8dB")}
    for j, az in enumerate(AZ):
        khat = np.array([np.cos(az), np.sin(az), 0.0])
        ndk = nrm @ khat
        lit = ndk < 0
        w = (-ndk[lit]) * area[lit]
        cl = cen[lit]
        zl = zone[lit]
        nl = nose_m[lit]
        for i, f in enumerate(FREQS):
            k = 2 * np.pi * f / 3e8
            ph = np.exp(2j * k * (cl @ khat))
            S_all = np.sum(w * ph)
            res["全金属"][i, j] = 4 * np.pi / (3e8 / f) ** 2 * abs(S_all) ** 2
            res["均匀涂层-15dB"][i, j] = 4 * np.pi / (3e8 / f) ** 2 * abs(
                10 ** (-15 / 20) * S_all) ** 2
            S_map = sum(ZONE_G[zn] * np.sum(w[zl == iz] * ph[zl == iz])
                        for iz, zn in enumerate(ZONE_G))
            res["温度分区涂层"][i, j] = 4 * np.pi / (3e8 / f) ** 2 * abs(S_map) ** 2
            g_nose = 10 ** (-8 / 20)
            res["温度分区+鼻帽−8dB"][i, j] = 4 * np.pi / (3e8 / f) ** 2 * abs(
                S_map - (1 - g_nose) * np.sum(w[nl] * ph[nl])) ** 2

    # ---- 统计 ----
    azd = np.degrees(AZ)
    front = np.abs(azd) <= 60
    rear = np.abs(azd) >= 120
    print("\n== 统计（10 GHz，dBsm）==")
    print(f"{'工况':14s} {'前向±60°均值':>10s} {'中位':>8s} {'达标率':>7s} "
          f"{'后向120°+均值':>10s} {'后向中位':>8s}")
    for k in res:
        db = 10 * np.log10(res[k][1])
        fw, rr = db[front], db[rear]
        print(f"{k:14s} {10*np.log10(np.mean(10**(fw/10))):10.1f} {np.median(fw):8.1f} "
              f"{100*np.mean(fw <= THRESH_DB):6.1f}% "
              f"{10*np.log10(np.mean(10**(rr/10))):10.1f} {np.median(rr):8.1f}")

    # ---- CSV ----
    with open(os.path.join(OUT, "rcs_realistic.csv"), "w", encoding="utf-8") as f:
        cols = [f"{k}|{fr/1e9:.0f}GHz_dBsm" for k in res for fr in FREQS]
        f.write("azimuth_deg," + ",".join(cols) + "\n")
        for j in range(len(AZ)):
            f.write(f"{azd[j]:.1f}," + ",".join(
                f"{10*np.log10(res[k][i, j]):.2f}" for k in res for i in range(len(FREQS))) + "\n")

    # ---- 图 ----
    fig, ax = plt.subplots(figsize=(11.5, 6))
    for k, c in zip(res, ("#c0392b", "#2471a3", "#1e8449", "#8e44ad")):
        ax.plot(azd, 10 * np.log10(res[k][1]), label=k, color=c, lw=1.2)
    ax.axhline(THRESH_DB, color="k", ls="--", lw=1.4, label="设计门限 −21 dBsm")
    ax.axvspan(-60, 60, color="orange", alpha=0.07, label="前向威胁区 ±60°")
    ax.axvspan(-180, -120, color="gray", alpha=0.06)
    ax.axvspan(120, 180, color="gray", alpha=0.06, label="后向（尾焰/SERN 区，几何上界）")
    ax.set_xlabel("方位角（°，0°=鼻锥向，±180°=尾向）")
    ax.set_ylabel("RCS (dBsm)")
    ax.set_title("影刃 RCS — 真实环境修正（外翼展开态）：涂层温度分区退化 vs 均匀涂层，10 GHz")
    ax.set_xlim(-180, 180)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9, loc="upper center", ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "rcs_realistic_10GHz.png"), dpi=150)
    print("\n[输出] rcs_realistic.csv + rcs_realistic_10GHz.png")


if __name__ == "__main__":
    main()
