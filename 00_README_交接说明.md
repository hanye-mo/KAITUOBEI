# 迅雷协同高超突击系统 — 交接包说明

> 交接时间：2026-10-02｜交接方：建模/仿真执行（GLM 会话）｜接收方：后续负责同学
> 环境：Blender 4.5.5 LTS（`D:\DevTool\Blender Foundation\Blender 4.5\blender.exe`）+ Python 3.14（numpy/matplotlib）

## 目录结构

```
00_README_交接说明.md     ← 本文件（先读）
01_设计文档/              建模方案.md（含 R1.7 时序修订）｜MODELING_LOG.md（全部执行记录）
                          TODO.md（剩余待办：U6 真实 CFD）｜README.md｜背景综述
02_模型源码/              model/ 全部 Python：参数-构建-自检-五套仿真脚本（下表）
03_交付物/                thunder.blend + export/（八类产物，见 export/INDEX.md 索引）
```

## 核心操作（02_模型源码/ 内执行）

产物统一写入 03_交付物/（源码目录被单独拷出时落在源码旁；环境变量 `THUNDER_OUT` 可指定其它交付物根目录）。

```bash
# 全量重建模型+导出+渲染+动画（约 20 分钟）
blender --background --factory-startup --python build_all.py -- all
# 仅构建+导出（不出图）
blender --background --factory-startup --python build_all.py -- build
# 按《建模方案》§4.3 分步执行（S1→S7，每步含自检；大小写不敏感）
blender --background --factory-startup --python build_all.py -- s1   # 参数/截面自检
blender --background --factory-startup --python build_all.py -- s6   # 构建+场景，写 check_report.json
blender --background --factory-startup --python build_all.py -- s7   # 导出 STL+渲染+动画
# 尺寸自检（读 03_交付物/check_report.json；全部由 build_all 实测，不填固定值）
python check.py          # 全表；退出码 0=无 FAIL，1=有 FAIL，2=报告缺失/用法错误
python check.py s5       # 只看某一步相关项
```

依赖：普通 Python 脚本需 `python -m pip install -r 02_模型源码/requirements.txt`（numpy/matplotlib）；
Blender 脚本只用 bpy/bmesh，不装第三方包。普通 Python / Blender Python 的脚本边界见该文件头部注释。

## 仿真脚本（02_模型源码/，python 直接跑，输出进 export/ 对应目录）

| 脚本 | 内容 | 输出 |
|---|---|---|
| rcs_sim.py | PO 面元法 RCS（三对象×3频×3材质，金属球标定 +0.00dB） | export/rcs/ |
| rcs_realistic.py | 真实环境修正：温度分区涂层/等离子体判定/鼻帽工况 | export/rcs/ |
| sep6dof.py | 末段分离 6-DOF 简化仿真（§2.3.3 判据核验） | export/sim6dof/ |
| aero_analytic.py | 牛顿面元法 L/D（解析面元） | export/aero/ |
| aero_shockexp.py | 精确斜激波验证（低 α 断言 CL 判定） | export/aero/ |
| ir_estimate.py | 红外特征量级（MWIR/LWIR 探测距离） | export/ir/ |
| tps_sizing.py | TPS 厚度/质量闭环（erfc 瞬态导热） | export/thermal/ |
| mesh_watertight.py | 解析水密网格（CFD/打印用，0 非流形边） | export/mesh/ |
| render_detail.py | 细节特写渲染（相机定义在脚本内） | export/detail/ |

## 关键结论速查（详见 MODELING_LOG §6–§9 与 export/INDEX.md）

1. **RCS**：影刃真实涂层下中位 0.0043㎡（−21dBsm 门限内，F-117 级）；鼻帽仅 +0.3dB → 涂层整体性能优先。
2. **分离**：三判据 PASS；**两项设计发现**——弹簧偏心须 ≤3mm；脉冲 2 点火应 T+3.2s（方案已按 R1.7 修订）。
3. **气动**：A′ max L/D=2.44@α14°（断言带内）；但低 α 设计点 CL 差 5~7×（平底构型结构性矛盾，
   修法：下表面改压缩面 或 设计点挪 α12–16°——**待 R3 决策，见 TODO U6**）。
4. **红外**：MWIR 探测 ~21.5km >> 雷达——报告需写"雷达隐身≠红外隐身"。
5. **TPS**：212kg vs 预算 1450kg，余量 85%。

## 遗留事项（TODO.md）

- U6 真实 CFD（需装 SU2/OpenFOAM；水密网格已在 export/mesh/ 备好，0 非流形边）。
- 方案 §3.2 参数有 6 项 DEV 变更申请（含 R1.7 时序），团队需复核确认——见 MODELING_LOG §3。
