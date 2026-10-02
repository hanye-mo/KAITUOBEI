# -*- coding: utf-8 -*-
"""T3 红外特征量级估算（补"隐身只谈雷达"口子）
源数据：§2.6 平衡温度 + V5 几何面积；Planck 定律分波段辐射（3–5μm / 8–12μm）
输出：export/ir/ ir_spectra.png ir_power.png ir_report.csv + 控制台探测距离表
口径：灰体 ε=0.85（C/C-SiC）、朗伯辐射、31km 冷天空背景（对比度乐观）、
     IRST 点目标探测门限取 1e-7 W/m²（波段积分、冷却型探测器量级）
"""
import os
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "export", "ir")
os.makedirs(OUT, exist_ok=True)

C1, C2 = 3.1438e8, 1.4388e-3          # 光速×1e9(nm→m 换算入内) / 第二辐射常数


def planck(lam_um, T):
    lam = lam_um * 1e-6
    return 1.0 / (lam ** 5 * (np.exp(1.4388e-2 / (lam * T)) - 1.0)) * 1e-12  # 任意归一 W/m³→相对


def band_fraction(T, l0, l1, n=4000):
    lam = np.linspace(0.1, 50, 200000)                # μm
    B = 1.0 / (lam ** 5 * (np.exp(1.4388e-2 / (lam * 1e-6 * T * 1e6)) - 1e0)) if False else \
        1.0 / (lam ** 5 * (np.exp(14.388 / (lam * T)) - 1.0))   # λ单位μm, 指数=1.4388e-2m·K/(λ·T)
    tot = np.trapezoid(B, lam)
    m = (lam >= l0) & (lam <= l1)
    return np.trapezoid(B[m], lam[m]) / tot


SB = 5.670e-8

# (名称, T[K], 面积m², ε) —— 温度=§2.6 平衡值+273，面积=V5 几何量级
COMPONENTS = [
    ("锐矛前缘/鼻尖", 2263, 0.55, 0.85),
    ("锐矛腹部压缩面", 1723, 5.85, 0.85),
    ("锐矛背面", 1173, 5.00, 0.85),
    ("影刃前缘", 2263, 0.30, 0.85),
    ("影刃腹部", 1723, 1.20, 0.85),
    ("影刃背面", 1173, 1.00, 0.85),
    ("尾焰/喷管(有效)", 2200, 0.30, 0.60),
]
BANDS = [("MWIR 3–5μm", 3.0, 5.0), ("LWIR 8–12μm", 8.0, 12.0)]
E_MIN = 1e-7                          # W/m² IRST 点目标门限（量级）


def main():
    lam = np.linspace(0.5, 14, 800)
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for (nm, T, A, em) in COMPONENTS:
        B = planck(lam, T)
        ax.plot(lam, B / B.max(), lw=1.1, label=f"{nm} {T}K")
    for (bn, l0, l1) in BANDS:
        ax.axvspan(l0, l1, alpha=0.10, color="gray")
        ax.text((l0 + l1) / 2, 1.02, bn, ha="center", fontsize=9)
    ax.set_xlabel("波长 (μm)"); ax.set_ylabel("归一化光谱辐射")
    ax.set_title("各热部件 Planck 光谱（归一化）与探测器波段")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "ir_spectra.png"), dpi=150)

    rows = []
    print("== 红外波段辐射功率与点目标探测距离（门限 1e-7 W/m²）==")
    print(f"{'部件':16s} {'T(K)':>5s} {'A(m²)':>5s} {'总功率(W)':>9s} "
          f"{'MWIR(W/sr)':>10s} {'LWIR(W/sr)':>10s} {'R_MWIR(km)':>10s} {'R_LWIR(km)':>10s}")
    tot = {b: 0.0 for b, _, _ in BANDS}
    for (nm, T, A, em) in COMPONENTS:
        P_tot = em * SB * T ** 4 * A
        res = {}
        for (bn, l0, l1) in BANDS:
            f = band_fraction(T, l0, l1)
            I = em * SB * T ** 4 * f * A / np.pi          # 朗伯，W/sr
            res[bn] = I
            tot[bn] += I
        r1 = np.sqrt(res[BANDS[0][0]] / E_MIN) / 1000
        r2 = np.sqrt(res[BANDS[1][0]] / E_MIN) / 1000
        rows.append((nm, T, A, P_tot, res[BANDS[0][0]], res[BANDS[1][0]], r1, r2))
        print(f"{nm:16s} {T:5d} {A:5.2f} {P_tot:9.0f} {res[BANDS[0][0]]:10.1f} "
              f"{res[BANDS[1][0]]:10.1f} {r1:10.1f} {r2:10.1f}")
    rt = [np.sqrt(tot[b] / E_MIN) / 1000 for b, _, _ in BANDS]
    print(f"{'合计':16s} {'':5s} {'':5s} {'':9s} {tot[BANDS[0][0]]:10.1f} {tot[BANDS[1][0]]:10.1f} "
          f"{rt[0]:10.1f} {rt[1]:10.1f}")

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(rows))
    ax.bar(x - 0.18, [r[4] for r in rows], 0.34, label="MWIR 3–5μm (W/sr)", color="#c0392b")
    ax.bar(x + 0.18, [r[5] for r in rows], 0.34, label="LWIR 8–12μm (W/sr)", color="#2471a3")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r[0]}\n{r[1]}K" for r in rows], fontsize=8)
    ax.set_ylabel("波段辐射强度 (W/sr)")
    ax.set_title(f"分部件红外辐射强度（合计探测距离：MWIR {rt[0]:.0f} km / LWIR {rt[1]:.0f} km）")
    ax.legend(); ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "ir_power.png"), dpi=150)

    with open(os.path.join(OUT, "ir_report.csv"), "w", encoding="utf-8") as f:
        f.write("component,T_K,area_m2,P_total_W,I_MWIR_Wsr,I_LWIR_Wsr,R_MWIR_km,R_LWIR_km\n")
        for r in rows:
            f.write(f"{r[0]},{r[1]},{r[2]},{r[3]:.1f},{r[4]:.2f},{r[5]:.2f},{r[6]:.1f},{r[7]:.1f}\n")
        f.write(f"TOTAL,,,,{tot[BANDS[0][0]]:.2f},{tot[BANDS[1][0]]:.2f},{rt[0]:.1f},{rt[1]:.1f}\n")
    print("[输出] export/ir/ ir_spectra.png ir_power.png ir_report.csv")


if __name__ == "__main__":
    main()
