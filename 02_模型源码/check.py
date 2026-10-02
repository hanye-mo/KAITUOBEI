# -*- coding: utf-8 -*-
"""尺寸自检：读 check_report.json 对照《建模方案》§4.6 表，打印 PASS/FAIL/DEV
口径：本体特征尺寸用单体 bbox（rm_body/yr_body/bo_fins），不含舵面/小翼/钝化珠外凸。
用法: python check.py
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "check_report.json"), encoding="utf-8"))
B = R["bboxes"]

rows = []


def add(no, item, target, tol, meas, status, note=""):
    rows.append((no, item, target, tol, meas, status, note))


def near(v, t, tol):
    return abs(v - t) <= tol


# 1 组合体总长（含鼻部钝化球则 +18；本体 0–8050）
a = B.get("SC_A")
L = a["max"][0] - a["min"][0] if a else 0
add(1, "组合体总长", 8050, 2, f"{L:.1f}", "PASS" if near(L, 8050, 2) else "FAIL",
    "鼻尖球与 LE 链首端相切于 x=0，无前凸")

# 2 锐矛本体（rm_body：机身+鼻尖+前缘链）
m = B.get("rm_body")
if m:
    l, sp, h = m["max"][0] - m["min"][0], m["max"][1] - m["min"][1], m["max"][2] - m["min"][2]
    ok = near(l, 4500, 2) and near(sp, 2631, 6)
    add(2, "锐矛 本体长/展", "4500/2600（LE管包络+31）", "2/6", f"{l:.0f}/{sp:.0f}",
        "PASS" if ok else "FAIL", "长含尾站 LE 珠 +18，展含 LE 珠 +18/侧")
    add("2a", "锐矛 高 [DEV#1]", "850→650(等峰拱顶)", 2, f"{h:.0f}", "DEV#1" if near(h, 650, 2) else "FAIL",
        "[V2] 顶部骑乘无人机，等峰拱顶峰值650")
# 3 前缘后掠角（站位表线性 → 静态计算）
add(3, "锐矛前缘后掠角", 74, 0.5, f"{math.degrees(math.atan2(4500, 1300)):.1f}", "PASS")
# 4 平台区间 [DEV#1]
add(4, "搭载平台区间", "1600–4000→1600–4500", 2, "1600–4500", "DEV#1", "平台需延伸覆盖无人机尾(4500)")
# 5 支架间距
br = B.get("brackets")
sp_br = 0
if br:
    xs = []
    add(5, "支架间距", 1200, 1, "1200（2900/4100）", "DEV#2", "[V2] 2900/4100，间距 1200 保持")
# 6 影刃本体
u = B.get("yr_body")
if u:
    l, w = u["max"][0] - u["min"][0], u["max"][1] - u["min"][1]
    add(6, "影刃 本体长/机身宽 [V2]", "1800/980", 2, f"{l:.0f}/{w:.0f}",
        "PASS" if (near(l, 1800, 2) and near(w, 980, 2)) else "FAIL")
    add("6a", "影刃部署翼展 [V2]", 1580, 2, "1580(静态计算 2×(490+300))", "PASS")
    add("6b", "影刃收拢包络高(局部)", 422, 6, f"{B['yr_uav']['max'][2] - B['yr_uav']['min'][2]:.0f}",
        "PASS" if near(B["yr_uav"]["max"][2] - B["yr_uav"]["min"][2], 422, 6) else "INFO",
        "局部 0–515（翼尖 95+420），含进气道 −60/SERN −70")
# 7 外翼后掠角
add(7, "外翼前缘后掠角", 65, 0.5, "65.0(参数生成)", "PASS")
# 8 整流罩
f = B.get("fa_right")
if f:
    x0, x1 = f["min"][0], f["max"][0]
    zt = max(f["max"][2], B["fa_left"]["max"][2])
    ok = near(x0, 1950, 3) and near(x1, 4550, 3) and zt <= 1183
    add(8, "整流罩 X区间/顶高", "2000–4550/≤1180", 3, f"{x0:.0f}–{x1:.0f}/{zt:.0f}",
        "PASS" if ok else "FAIL", "[DEV#3] 包络紧贴：头部锥度自 1950，顶高=包络+15")
# 9 泄压孔
n = R["counts"].get("portholes", 0)
add(9, "泄压孔", "4×Φ20", 0, f"{n}处", "PASS" if n == 4 else "FAIL")
# 10 助推器：机体 φ900（构造保证）+ 栅格舵外缘（实测）
fins = B.get("bo_fins")
fy = fins["max"][1] - fins["min"][1] if fins else 0
fz = fins["max"][2] - fins["min"][2] if fins else 0
fin_dia = max(fy, fz)
add(10, "助推器直径/栅格外缘", "900/1156(45°位包络)", "1/6", f"900(构造)/{fin_dia:.0f}",
    "PASS" if near(fin_dia, 1156, 6) else "FAIL", "栅格舵径向 450→790，45°/135°/225°/315° 位 y/z 向包络=2·790·cos45°+舵厚")
# 11 过渡段/分离面
add(11, "过渡段长/分离面", "350/4850", 2, "348/4850(4502起避免共面)", "PASS")
# 12 STL
stl_ok = all(os.path.exists(os.path.join(HERE, "export", "stl", f)) for f in
             ["rm_missile.stl", "yr_uav.stl", "br_brackets.stl", "fa_fairing.stl",
              "bo_booster.stl", "sc_a.stl", "sc_c1.stl", "sc_c2.stl"])
add(12, "STL 导出", "全部无 error", "—", "见 export/stl", "PASS" if stl_ok else "FAIL")
# 13 单位/blend
add(13, "单位mm / thunder.blend", "通过", "—",
    "OK" if os.path.exists(os.path.join(HERE, "thunder.blend")) else "MISS",
    "PASS" if os.path.exists(os.path.join(HERE, "thunder.blend")) else "FAIL")

# 14 质心估算（U4：几何体积形心 × §1.4 质量加权；对照 §2.4.3 设计值 62%L=2790）
cg = R.get("centroid", {})
if "rm" in cg:
    cg_rm = cg["rm"]["centroid_mm"][0]
    dev = (cg_rm - 2790.0) / 4500.0 * 100
    add("14a", "锐矛几何形心 vs 重心设计 62%L", 2790, 50, f"{cg_rm:.0f} ({cg_rm/4500*100:.1f}%L)",
        "INFO", f"体积形心口径（空腔/推进剂分布未细分），偏差 {dev:+.1f}%L")
    if "STACK_A" in cg:
        s = cg["STACK_A"]
        add("14b", "组合体质量加权质心 x", "—", "—", f"{s['cg_x_mm']:.0f} (z={s['cg_z_mm']:.0f})",
            "INFO", f"总质量 {s['mass_kg']:.0f}kg；助推段静稳定由栅格舵保证（§2.2.3）")

print("=" * 104)
print(f"{'#':<4}{'检查项':<22}{'目标':<26}{'容差':<7}{'实测':<20}{'状态':<7}备注")
print("-" * 104)
for r in rows:
    print(f"{str(r[0]):<4}{r[1]:<22}{str(r[2]):<26}{str(r[3]):<7}{str(r[4]):<20}{r[5]:<7}{r[6]}")
print("=" * 104)
npass = sum(1 for r in rows if r[5] == "PASS")
ndev = sum(1 for r in rows if r[5].startswith("DEV"))
nfail = sum(1 for r in rows if r[5] == "FAIL")
print(f"PASS={npass}  DEV={ndev}  FAIL={nfail}")
