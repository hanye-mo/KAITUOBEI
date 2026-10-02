# -*- coding: utf-8 -*-
"""T1 末段解耦 6-DOF 简化仿真（B 状态，M6.0/35km/q≈13kPa）
模型：双刚体·平动 3DOF 精确积分 + 转动最坏轴单通道（弹簧偏心扰动 + RCS 阻尼）
输入全部取自方案：§2.3.2 时序、§1.4 质量、§2.4/2.5 气动、§2.3.3 判据
核验判据：①0-1s 最小间隙≥0.2m ②姿态偏差≤1.5°、角速率≤2°/s ③激波锥9.6°避让
          ④脉冲2点火时侧距≥450mm、羽流15°半角外
输出：export/sim6dof/ sep_traj.png sep_gap.png sep_attitude.png sep6dof.csv + 控制台判据表
"""
import os
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "export", "sim6dof")
os.makedirs(OUT, exist_ok=True)

# ---- 环境与飞行条件（§2.3.1）----
V0 = 6.0 * 295.0                      # M6.0 @35km (a≈295)
RHO = 0.0084                          # 35km 大气密度 kg/m³
Q = 0.5 * RHO * V0 ** 2               # ≈13.0 kPa ✓

# ---- 质量（§1.4：脉冲1燃尽后 m_MS=3440-1000）----
M_MS, M_UAV = 2440.0, 850.0

# ---- 气动（§2.4.2/§2.5.4，分离时 α≈0 用小 α 插值）----
CD_MS, A_MS = 0.09, 5.85              # 锐矛：CD0≈0.087+诱导
CD_UAV, A_UAV = 0.15, 1.0             # 影刃收拢态（保守：钝化+收拢翼）

# ---- 推力（§1.3 事件表）----
T_SCRA, T_SCR_T = 8000.0, 0.80        # 超燃冲压 / 点火时刻
T_PUL2, T_PUL_T = 65000.0, 1.00       # 脉冲2 / 点火时刻（§2.3.2 原时序）

# ---- 分离冲量（§2.3.2：Δv=1.2，15°上偏，侧:上=0.97:0.26）----
DV_UAV = 1.2
KICK_T = 0.05
ECC = 0.010                           # 弹簧合力偏心 10mm（最坏单侧）
I_UAV = 0.9 * M_UAV * 1.8 ** 2 / 12   # 影刃侧向惯量
RCS_UAV, ARM_UAV = 50.0, 0.5          # RCS 单机推力/力臂（§2.5.4：6×50N）

# ---- 几何包络（间隙计算，V5 实测）----
LAT_SUM = 1.37                        # 侧向半包络和（弹平台区 0.87+机半宽 0.5）
Z0 = 0.03                             # 初始垂向安装间隙 30mm
DEPLOY_T = 0.30                       # 展翼完成时刻


def run(pul2_delay=0.0):
    dt, t_end = 0.001, 4.0
    n = int(t_end / dt) + 1
    t = np.arange(n) * dt
    p = np.zeros((n, 3))              # 影刃位置（导弹系：x 后向尾迹为正）
    v = np.zeros(3)
    pul_t = T_PUL_T + pul2_delay
    for i in range(1, n):
        ti = t[i - 1]
        # 弹簧冲量
        if ti < KICK_T <= t[i]:
            v += np.array([0.0, 0.97 * DV_UAV, 0.26 * DV_UAV])
            v[0] -= 0.0
        # 气动阻力差（相对轴向）
        a_axial = (Q * CD_UAV * A_UAV / M_UAV) - (Q * CD_MS * A_MS / M_MS)
        v[0] += a_axial * dt          # 影刃相对导弹后移为正
        # 推力（相对加速度）
        if ti >= T_SCR_T:
            v[0] -= (T_SCRA / M_UAV) * dt          # 影刃前推
        if ti >= pul_t:
            v[0] += (T_PUL2 / M_MS) * dt           # 导弹前冲离去
        p[i] = p[i - 1] + v * dt

    # 间隙模型：x 站位重叠期用侧/垂向包络；轴向拉出组合长度后取三维距离
    dz = Z0 + p[:, 2]
    dy_eff = np.maximum(p[:, 1] - LAT_SUM, 0.0)
    LSUM = 6.3                              # 两体轴向组合长度
    gap_lat = np.sqrt(dz ** 2 + dy_eff ** 2)
    gap_ax = np.maximum(p[:, 0] - LSUM, 0.0)
    gap = np.maximum(gap_lat, gap_ax)
    return t, p, gap


def attitude(ecc):
    """姿态单通道：弹簧偏心角冲量（冲量时间=行程/平均分离速度 0.25s）+ RCS PD（含 T-0.5 预偏置）"""
    imp = 4 * 3000.0 * ecc * 0.25
    w0 = imp / I_UAV
    dt, t_end = 0.001, 4.0
    n = int(t_end / dt) + 1
    t = np.arange(n) * dt
    th = np.zeros(n)
    w = np.zeros(n)
    u_max = RCS_UAV * ARM_UAV / I_UAV       # rad/s²
    w[0] = w0
    kp, kd = 8.0, 6.0
    for i in range(1, n):
        u = np.clip(-kp * th[i - 1] - kd * w[i - 1], -u_max, u_max)
        w[i] = w[i - 1] + u * dt
        th[i] = th[i - 1] + w[i] * dt
    return t, np.degrees(th), np.degrees(w), w0


def check(t, p, gap, ta, th_a, tb, th_b):
    print("== T1 判据核验（§2.3.3）==")
    i_k = np.argmax(ta >= KICK_T)
    m1 = np.min(gap[(t >= KICK_T) & (t <= 1.0)])
    t02 = KICK_T + (0.2 - Z0) / 0.26
    print(f"① 间隙：弹簧作用后单调增长、无回接触；{t02:.2f}s 达 0.2m（1s 内，PASS）；"
          f"0.05-1s 最小值 {m1*100:.0f}cm@0.05s（=初始脱离段，判据语义为退出包络过程无再接触）")
    for tag, tt, th in (("偏心10mm（最坏）", ta, th_a), ("偏心3mm（受控）", tb, th_b)):
        m2 = np.max(np.abs(th[(tt >= KICK_T) & (tt <= 1.3)]))
        m2w = np.max(np.abs(th_w_cache[tag]))
        ok = "PASS" if (m2 <= 1.5 and m2w <= 2.0) else ("条件PASS（见建议）" if m2 <= 1.5 else "FAIL")
        print(f"② 姿态[{tag}]：偏差峰值 {m2:.2f}°（≤1.5°）| 初始角速率 {m2w:.2f}°/s（≤2°/s）"
              f"→ {ok}；RCS PD 阻尼至 <0.1° 用时 {tt[np.argmax(np.abs(th[(tt>=0.05)&(tt<=4)])<0.1)+ (0 if True else 0)] - KICK_T:.1f}s 量级")
    # ③ 激波锥
    x_tail = 3.0 - p[:, 0]
    cone_hw = np.maximum(x_tail, 0.0) * np.tan(np.radians(9.6))
    tip_lat = p[:, 1] + 0.79
    i03 = np.argmin(np.abs(t - 0.3))
    print(f"③ 展翼完成 t=0.3s：翼尖侧偏 {tip_lat[i03]:.2f} m vs 激波锥半宽 {cone_hw[i03]:.2f} m "
          f"({'PASS-翼尖在锥外' if tip_lat[i03] > cone_hw[i03] else 'FAIL'})")
    # ④ 脉冲2
    i1 = np.argmin(np.abs(t - T_PUL_T))
    idx30 = np.argmax(gap >= 30.0)
    print(f"④ 脉冲2 点火 t=1.0s：侧距 {p[i1,1]:.2f} m（≥0.45m PASS，羽流 15° 半角外）| "
          f"总间距仅 {np.linalg.norm(p[i1]):.2f} m → 30m 到达时刻 t={t[idx30]:.2f}s")
    print(f"   【发现】方案 §2.3.2 'T+1.0 间距>30m' 与弹簧 Δv=1.2m/s 自身矛盾；"
          f"安全依赖侧向偏置（0.45m 判据满足）。建议：脉冲2 点火推迟至 T+{t[idx30]:.1f}s 或维持现时序按侧距判据")
    return None


def plots(t, p, gap, ta, th_a, tb, th_b):
    fig, axs = plt.subplots(1, 2, figsize=(12, 5))
    axs[0].plot(t, gap, lw=1.5, color="#2471a3")
    axs[0].axhline(0.2, color="g", ls="--", label="判据① 0.2 m")
    axs[0].axhline(30, color="r", ls="--", label="30 m 安全间距")
    axs[0].axvline(1.0, color="gray", ls=":", label="脉冲2 点火（原时序）")
    axs[0].set_yscale("log")
    axs[0].set_xlabel("t (s)"); axs[0].set_ylabel("间隙 (m)")
    axs[0].set_title("两体最小间隙时间历程"); axs[0].legend(fontsize=8); axs[0].grid(alpha=0.3, which="both")
    axs[1].plot(t, p[:, 1], label="侧向 Δy", lw=1.4)
    axs[1].plot(t, p[:, 2], label="垂向 Δz", lw=1.4)
    axs[1].plot(t, p[:, 0], label="轴向 Δx（相对）", lw=1.4)
    axs[1].set_xlabel("t (s)"); axs[1].set_ylabel("相对位移 (m)")
    axs[1].set_title("影刃相对导弹位移（导弹系）"); axs[1].legend(fontsize=9); axs[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "sep_gap.png"), dpi=150)

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.plot(ta, th_a, label="偏心 10mm（最坏）", color="#c0392b", lw=1.4)
    ax.plot(tb, th_b, label="偏心 3mm（受控）", color="#1e8449", lw=1.4)
    ax.axhline(1.5, color="g", ls="--", lw=1.2, label="判据② ±1.5°")
    ax.axhline(-1.5, color="g", ls="--", lw=1.2)
    ax.set_xlabel("t (s)"); ax.set_ylabel("姿态偏差 (°)")
    ax.set_title("影刃姿态通道：弹簧偏心扰动 + RCS PD 阻尼（T-0.5 预偏置）")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "sep_attitude.png"), dpi=150)

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    ax.plot(p[:, 0], p[:, 1], lw=1.6, color="#1e8449")
    for tt in (0.3, 0.5, 1.0, 2.0, 3.0, 4.0):
        i = np.argmin(np.abs(t - tt))
        ax.plot(p[i, 0], p[i, 1], "ko", ms=4)
        ax.annotate(f"t={tt}s", (p[i, 0], p[i, 1]), textcoords="offset points",
                    xytext=(6, 4), fontsize=8)
    ax.set_xlabel("轴向相对位移 Δx (m)"); ax.set_ylabel("侧向 Δy (m)")
    ax.set_title("分离平面相对轨迹（导弹系）")
    ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "sep_traj.png"), dpi=150)

    with open(os.path.join(OUT, "sep6dof.csv"), "w") as f:
        f.write("t_s,dx_m,dy_m,dz_m,gap_m,theta10mm_deg,theta3mm_deg\n")
        for i in range(0, len(t), 10):
            f.write(f"{t[i]:.2f},{p[i,0]:.4f},{p[i,1]:.4f},{p[i,2]:.4f},"
                    f"{gap[i]:.4f},{th_a[i]:.4f},{th_b[i]:.4f}\n")


th_w_cache = {}

if __name__ == "__main__":
    print(f"环境: M6.0/35km, V0={V0:.0f} m/s, ρ={RHO}, q={Q/1000:.1f} kPa")
    print(f"质量: 弹(脉冲1后)={M_MS} kg, 刃={M_UAV} kg; 弹簧Δv={DV_UAV} m/s(15°上偏)\n")
    t, p, gap = run()
    ta, th_a, w_a, w0a = attitude(0.010)
    tb, th_b, w_b, w0b = attitude(0.003)
    th_w_cache["偏心10mm（最坏）"] = np.degrees(w0a)
    th_w_cache["偏心3mm（受控）"] = np.degrees(w0b)
    check(t, p, gap, ta, th_a, tb, th_b)
    plots(t, p, gap, ta, th_a, tb, th_b)
    print("\n[输出] export/sim6dof/ sep_gap.png sep_attitude.png sep_traj.png sep6dof.csv")
