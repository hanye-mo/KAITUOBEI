# -*- coding: utf-8 -*-
"""U6-过渡 气动验证升级：精确斜激波迎风面法（shock-expansion 简化）
方法：迎风平底=精确斜激波 Cp(M,α)（θ-β-M 解），背风拱顶≈高超声速近真空（Cp→0），
     + 湍流摩阻 Cd_f + 底阻 Cd_b（同 aero_analytic 口径）。
判定目标：方案 C1/A′ 设计点 CL 断言（0.234@α5°M8 / 0.30@α7°M6）在压力面理论下的可达性。
输出：export/aero/ aero_shockexp.png aero_shockexp.csv + 控制台判定
"""
import os
import math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

from aero_analytic import oblique_shock_cp, A_REF

OUT = os.path.join(HERE, "export", "aero")
ALPHAS = np.arange(0.5, 16.01, 0.5)
S_BELLY_EFF = 1.0                      # 平底投影占 A_ref 比例（S_belly≈A_ref=5.85）


def sweep(M, cd_f, cd_b):
    rows = []
    for a in ALPHAS:
        try:
            cp = oblique_shock_cp(M, a)
        except Exception:
            cp = np.nan
        cl = cp * math.cos(math.radians(a)) * S_BELLY_EFF
        cdw = cp * math.sin(math.radians(a))
        cd = cdw + cd_f + cd_b
        rows.append((a, cl, cdw, cd, cl / cd))
    return np.array(rows)


def main():
    cfg = {
        "C1 锐矛 M8": (8.0, 0.0053, 0.0252, (2.6, 2.8), 5.0, 0.234),
        "A′ 捆绑 M6": (6.0, 0.0110, 0.0252, (2.2, 2.4), 7.0, 0.30),
    }
    fig, axs = plt.subplots(1, 2, figsize=(12, 5))
    csv = ["config,mach,alpha_deg,CL,CD_wave,CD_total,LD"]
    for tag, (M, cf, cb, band, a_des, cl_spec) in cfg.items():
        r = sweep(M, cf, cb)
        i = np.argmin(np.abs(r[:, 0] - a_des))
        im = np.nanargmax(r[:, 4])
        print(f"[{tag}] 设计点 α={a_des}°: CL={r[i,1]:.3f}（方案断言 {cl_spec}，"
              f"比值 {cl_spec/r[i,1]:.1f}×）| L/D={r[i,4]:.2f}（断言带 {band[0]}~{band[1]}）")
        print(f"  本法最优 L/D={r[im,4]:.2f} @ α={r[im,0]:.0f}°（CL={r[im,1]:.3f}）")
        for x in r:
            csv.append(f"{tag},{M},{x[0]:.1f},{x[1]:.4f},{x[2]:.4f},{x[3]:.4f},{x[4]:.4f}")
        col = "#8e44ad" if M == 8 else "#c0392b"
        axs[0].plot(r[:, 0], r[:, 1], color=col, lw=1.5, label=f"{tag} 精确斜激波")
        axs[0].plot([a_des], [cl_spec], "k*", ms=12)
        axs[1].plot(r[:, 0], r[:, 4], color=col, lw=1.5, label=tag)
    axs[0].annotate("方案断言点（★）", (6, cl_spec), fontsize=9)
    axs[0].set_xlabel("迎角 α (°)"); axs[0].set_ylabel("CL")
    axs[0].set_title("升力线：精确斜激波迎风面 vs 方案断言"); axs[0].grid(alpha=0.3); axs[0].legend(fontsize=9)
    axs[1].axhspan(2.2, 2.4, color="#c0392b", alpha=0.10, label="A′ 断言带")
    axs[1].axhspan(2.6, 2.8, color="#8e44ad", alpha=0.08, label="C1 断言带")
    axs[1].set_xlabel("迎角 α (°)"); axs[1].set_ylabel("L/D")
    axs[1].set_title("升阻比（精确斜激波 + 摩阻 + 底阻）"); axs[1].grid(alpha=0.3); axs[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "aero_shockexp.png"), dpi=150)
    with open(os.path.join(OUT, "aero_shockexp.csv"), "w", encoding="utf-8") as f:
        f.write("\n".join(csv) + "\n")
    print("[输出] export/aero/ aero_shockexp.png aero_shockexp.csv")


if __name__ == "__main__":
    main()
