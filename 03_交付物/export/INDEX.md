# 交付物索引（export/）— 报告引用总表

> 生成：2026-10-02（V5 模型 + V6 仿真批次）。图号建议按本表引用；
> 一句话结论可直接进 PPT/报告。构建脚本在 `model/`，改参数可全量重生成。

## A. 建模渲染（png/，31 张，1920×1080）

| 图号 | 文件 | 内容 | 一句话结论 |
|---|---|---|---|
| A1–A5 | sc_a_{front,side,top,axo1,axo2}.png | 组合态三视+轴测×2 | 军工级外观：钛灰弹体/炭黑罩/亮铝助推器，总长 8050 |
| A6–A7 | sc_a2_{side,axo}.png | 捆绑滑翔态（无助推器） | 助推器分离后构型 |
| A8–A11 | assembly_{front,side,top,axo}.png | 无罩装配四视 | 示导弹+无人机+支架安装关系与蒙皮细节 |
| A12–A23 | sep_k{0..5}_{side,axo}.png | 分离序列 6 关键帧×2 | 抛罩→推离→展翼→协同拉开 |
| A24–A27 | sc_c1_{front,side,top,axo}.png | 锐矛单机四视 | 尾端面喷口/襟副翼/小翼/工艺缝可见 |
| A28–A31 | sc_c2_{front,side,top,axo}.png | 影刃单机四视 | 菱边隐身机身/锯齿舱门/升降副翼 −10° |

## B. 动画（mp4/）

| 文件 | 内容 | 结论 |
|---|---|---|
| sep_seq.mp4 | 分离全序列 300 帧 @24fps（12.5s） | 时序已按 R1.7 修订口径演绎（抛罩/推离/展翼/脉冲2） |

## C. 几何（stl/，11 个）

rm_missile / yr_uav / br_brackets / fa_fairing / bo_booster（部件 5）+
sc_a / sc_a2 / sep_k0 / sc_c1 / sc_c2（状态 5）+ sc_a_merged（合体单实体）。
单位 mm；注意：布尔残留面元存在（见 MODELING_LOG §7 附注），CFD 前用 E1 水密网格。

## D. 雷达隐身（rcs/）— 脚本 rcs_sim.py / rcs_realistic.py

| 图号 | 文件 | 结论 |
|---|---|---|
| D1 | rcs_sphere_validation.png | 求解器标定：金属球 PO −11.50 vs 解析 −11.51 dBsm（+0.00dB） |
| D2 | rcs_compare_10GHz.png | 三状态对比：影刃比组合体鼻向低 ~35dB——解耦隐身价值量化 |
| D3 | rcs_yr_materials_10GHz.png | 涂层敏感性：−15dB 均匀涂层前向均值 −23.7dBsm（达标） |
| D4 | rcs_yr_freq.png | 频率影响 8/10/12GHz |
| D5 | rcs_polar_10GHz.png | 三状态极图 |
| D6 | rcs_realistic_10GHz.png | **真实环境**（温度分区涂层+展开态）：中位 −23.7dBsm（0.0043㎡ 达标）、均值 −19.8、达标率 71%；鼻帽 −8dB 工况仅 +0.3dB → **涂层整体性能优先于局部鼻帽** |
| 数据 | rcs_data.csv / rcs_realistic.csv / run.log | 全角度原始数据 |

## E. 气动（aero/）— aero_analytic.py / aero_shockexp.py

| 图号 | 文件 | 结论 |
|---|---|---|
| E1 | aero_polar.png | 牛顿面元：A′ max L/D=2.44@α14°（断言带内）；C1 修正后 2.6–2.8 |
| E2 | aero_shockexp.png | **精确斜激波**：C1 CL=0.033@5°（断言 0.234，7.1×）、A′ 0.063@7°（0.30，4.8×）；max L/D 2.28@15°/2.20@16°——低 α 断言 CL 需压缩面成形（R3 设计决策） |
| 数据 | aero_ld.csv / aero_shockexp.csv | α 扫描 CL/CD 分项 |

## E-Mesh. 水密网格（mesh/）— mesh_watertight.py

| 文件 | 结论 |
|---|---|
| c1_body.{stl,obj} | 锐矛弹身水密网格（21600 三角，0 非流形边，体积 2457.4L）——CFD/打印直用 |
| fairing.{stl,obj} | 整流罩包络水密网格（36608 三角，0 非流形边，2956.6L） |

## F. 分离 6-DOF（sim6dof/）— sep6dof.py

| 图号 | 文件 | 结论 |
|---|---|---|
| F1 | sep_gap.png | 间隙单调增长、0.70s 达 0.2m、无回接触；30m 于 T+3.25s |
| F2 | sep_attitude.png | 偏心 3mm+预偏置 0.45° PASS；10mm 最坏 4.99° FAIL → 公差 ≤3mm |
| F3 | sep_traj.png | 分离平面相对轨迹 |
| 数据 | sep6dof.csv | 全时程 |

## G. 红外（ir/）— ir_estimate.py

| 图号 | 文件 | 结论 |
|---|---|---|
| G1 | ir_spectra.png | 各热部件 Planck 光谱与 MWIR/LWIR 波段 |
| G2 | ir_power.png | MWIR 46.2 W/sr 主导；探测距离 MWIR≈21.5km >> 雷达 → 雷达隐身≠红外隐身 |
| 数据 | ir_report.csv | 分部件功率/距离 |

## H. 防热（thermal/）— tps_sizing.py

| 图号 | 文件 | 结论 |
|---|---|---|
| H1 | tps_profile.png | erfc 瞬态剖面：腹面需隔热 45.9mm / 背面 34.7mm（480s，背温限 600K） |
| H2 | tps_mass.png | TPS 合计 212kg vs 预算 1450kg，余量 85% |
| 数据 | tps_mass.csv | 分区质量 |

## 尺寸自检

`model/check.py` → PASS=13 / DEV=3 / FAIL=0（§4.6 全项）。
