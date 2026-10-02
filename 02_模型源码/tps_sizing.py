# -*- coding: utf-8 -*-
"""T4 TPS 厚度/质量闭环（§2.6 防热表 → 结构质量核算）
模型：半无限体瞬态导热 T(x,t)=Ti+(Ts−Ti)·erfc(x/2√(αt))
     任务时间 480s（8min 巡航上限）；背温限 600K（钛合金内壁）
构型（方案 §2.6 材料）：C/C-SiC 热结构 3mm + 隔热毡 d(Ts) + Ti 内壁 1.2mm
输出：export/thermal/ tps_profile.png tps_mass.csv + 质量对照（预算 1100kg）
"""
import os
import sys
import math
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from lib.paths import export_dir

OUT = export_dir("thermal")
os.makedirs(OUT, exist_ok=True)

T_AMB, T_LIMIT, T_MISSION = 300.0, 600.0, 480.0
ALPHA_INS = 1.4e-6                     # 隔热毡热扩散率 m²/s（k0.15/ρ100/c1050，800K 均值）
RHO = {"CSiC": 2000.0, "INS": 100.0, "TI": 4430.0}


def erf_inv(y):
    """Abramowitz-Stegun 逼近（|err|<4.5e-4）"""
    a = [0.147, -1.101, 0.874, -0.124][0:]
    ln = math.log(1 - y * y) if y != 1 else 0.0
    t1 = 2 / (math.pi * a[0] + ln / 2)
    t2 = 1 / (a[1] + ln * a[3] + t1 ** 0.5) ** 0.5 if False else None
    # 用简单数值反演代替（稳健）：
    lo, hi = 0.0, 6.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if math.erf(mid) < y:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def thickness(Ts):
    """背温 600K 所需隔热厚度"""
    frac = (T_LIMIT - T_AMB) / (Ts - T_AMB)          # = erfc(z)
    z = erf_inv(1 - frac)
    return 2 * z * math.sqrt(ALPHA_INS * T_MISSION)


def areal(Ts):
    d = thickness(Ts)
    return 0.003 * RHO["CSiC"] + d * RHO["INS"] + 0.0012 * RHO["TI"], d


ZONES = [
    ("锐矛 腹部压缩面 1723K/1450℃", 1723.0, 5.85),
    ("锐矛 背面 1173K/900℃", 1173.0, 5.00),
    ("影刃 腹部 1723K/1450℃", 1723.0, 1.20),
    ("影刃 背面 1173K/900℃", 1173.0, 1.00),
]


def main():
    print("== TPS 厚度/质量闭环（erfc 瞬态导热，480s，背温限 600K）==")
    total = 0.0
    rows = []
    for (nm, Ts, A) in ZONES:
        am, d = areal(Ts)
        m = am * A
        total += m
        rows.append((nm, Ts, A, d * 1000, am, m))
        print(f"  {nm:28s}: 隔热 {d*1000:5.1f} mm | 面密度 {am:5.1f} kg/m² | 质量 {m:5.0f} kg")
    le_mass = 0.85 * 1500 * (0.55 + 0.30) * 0.010      # 前缘 C/C-SiC 实体（10mm 当量厚）
    total += le_mass
    print(f"  {'前缘/鼻尖 C/C-SiC 实体':28s}: 质量 {le_mass:5.0f} kg")
    print(f"  TPS 合计 ≈ {total:.0f} kg | 质量表预算（锐矛结构+TPS 1100 + 影刃 350）=1450 kg"
          f" → 余量 {1450-total:.0f} kg（{(1450-total)/1450*100:.0f}%）")

    # 图1：温度剖面
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.linspace(0, 0.08, 200) * 1000               # mm
    for (nm, Ts, A) in ZONES:
        T = T_AMB + (Ts - T_AMB) * np.array([math.erfc(xx / 1000 / (2 * math.sqrt(ALPHA_INS * T_MISSION)))
                                             for xx in x])
        ax.plot(x, T, lw=1.4, label=nm.split()[0] + " " + nm.split()[-1])
    ax.axhline(T_LIMIT, color="r", ls="--", label="背温限 600K（钛）")
    for (nm, Ts, A) in ZONES:
        d = thickness(Ts) * 1000
        ax.axvline(d, color="gray", ls=":", lw=0.8)
        ax.text(d + 0.6, 1500, f"{d:.0f}mm", fontsize=8, rotation=90)
    ax.set_xlabel("隔热层深度 (mm)"); ax.set_ylabel("温度 (K)")
    ax.set_title("隔热层瞬态温度剖面（480 s 任务末，半无限体 erfc 解）")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "tps_profile.png"), dpi=150)

    # 图2：质量瀑布
    fig, ax = plt.subplots(figsize=(8, 4.6))
    names = [r[0].split()[0] + r[0].split()[1] + "\n" + r[0].split()[-1] for r in rows] + ["前缘实体"]
    vals = [r[5] for r in rows] + [le_mass]
    ax.bar(names, vals, color=["#c0392b", "#e67e22", "#9b59b6", "#3498db", "#7f8c8d"])
    ax.axhline(1450, color="k", ls="--", label="预算 1450 kg（锐矛1100+影刃350）")
    for i, v in enumerate(vals):
        ax.text(i, v + 12, f"{v:.0f}", ha="center", fontsize=9)
    ax.set_ylabel("质量 (kg)")
    ax.set_title(f"TPS/隔热 分区质量 vs 预算（合计 {total:.0f} kg，余量 {1450-total:.0f} kg）")
    ax.legend(); ax.grid(alpha=0.3, axis="y")
    plt.xticks(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "tps_mass.png"), dpi=150)

    with open(os.path.join(OUT, "tps_mass.csv"), "w", encoding="utf-8") as f:
        f.write("zone,T_surface_K,area_m2,insulation_mm,areal_kg_m2,mass_kg\n")
        for r in rows:
            f.write(f"{r[0]},{r[1]},{r[2]},{r[3]:.1f},{r[4]:.1f},{r[5]:.0f}\n")
        f.write(f"LE_solid,2263,0.85,0,0,{le_mass:.0f}\n")
        f.write(f"TOTAL,,,,,{total:.0f}\n")
    print("[输出] export/thermal/ tps_profile.png tps_mass.png tps_mass.csv")


if __name__ == "__main__":
    main()
