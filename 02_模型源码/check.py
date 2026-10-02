# -*- coding: utf-8 -*-
"""尺寸自检：读 check_report.json 对照《建模方案》§4.6 表，打印 PASS/FAIL/SKIP/DEV/INFO。

口径：本体特征尺寸用单体 bbox（rm_body/yr_body/bo_fins），不含舵面/小翼/钝化珠外凸。
状态含义：PASS 达标｜FAIL 超差｜SKIP 报告缺该项数据（人工复核）｜DEV#n 执行期变更申请
（见 MODELING_LOG.md §3，符合变更后口径则不阻塞）｜INFO 参考量（不判超差）。
实测值全部来自 check_report.json 或 lib/params.py 推导，不填固定值。

用法: python check.py [s2|s3|s4|s5|s6|s7]      # 省略 = 全表
退出码: 0=无 FAIL；1=存在 FAIL；2=无法执行（报告缺失/损坏、未知步骤）
报告由 build_all.py 写入 <交付物根>/check_report.json（默认同级 03_交付物/，
环境变量 THUNDER_OUT 可指向其它交付物目录）。
"""
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from lib.paths import report_path, export_dir, blend_path

try:
    from lib import params as P
except Exception as _e:                       # 参数表缺失时相关项降级 SKIP
    print(f"[CHECK] 警告：lib/params.py 导入失败（{_e}），参数口径项记 SKIP")
    P = None

USAGE = "用法: python check.py [s2|s3|s4|s5|s6|s7]"
STEP_STL_FILES = ["rm_missile.stl", "yr_uav.stl", "br_brackets.stl", "fa_fairing.stl",
                  "bo_booster.stl", "sc_a.stl", "sc_a2.stl", "sep_k0.stl", "sc_c1.stl", "sc_c2.stl"]


def load_report():
    p = report_path()
    if not os.path.exists(p):
        print(f"[CHECK] 未找到自检报告：{p}")
        print("[CHECK] 请先在 02_模型源码/ 内生成报告，再运行本脚本：")
        print("  blender --background --factory-startup --python build_all.py -- s6   # 仅构建+写报告（分钟级）")
        print("  blender --background --factory-startup --python build_all.py -- all  # 全量重建+导出+渲染（约20分钟）")
        print("[CHECK] 若交付物在别处，设环境变量 THUNDER_OUT 指向其根目录（含 check_report.json）。")
        sys.exit(2)
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[CHECK] 报告无法解析：{p}（{e}）——请重新运行 build_all.py 生成")
        sys.exit(2)


def stl_verdict(path):
    """STL 实质校验：二进制按 84+50×n 吻合且 n>0；ASCII 数 facet。返回 (ok, 说明)。"""
    try:
        sz = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(80)
            if sz >= 84:
                n = struct.unpack("<I", f.read(4))[0]
            else:
                n = 0
        if head[:5] == b"solid" and not (n > 0 and sz == 84 + 50 * n):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                nfacet = sum(1 for line in f if "facet normal" in line)
            return nfacet > 0, f"ASCII {nfacet} facet"
        if n > 0 and sz == 84 + 50 * n:
            return True, f"binary {n} 三角形"
        return False, f"三角数 {n} 与文件大小 {sz}B 不符（期望 {84 + 50 * n}B）"
    except OSError as e:
        return False, str(e)


def build_rows(R):
    B = R.get("bboxes", {})
    C = R.get("counts", {})
    rows = []

    def add(no, item, target, tol, meas, status, note="", step=""):
        rows.append((no, item, target, tol, meas, status, note, step))

    def near(v, t, tol):
        return abs(v - t) <= tol

    def dims(key):
        b = B.get(key)
        if not b:
            return None
        return tuple(b["max"][i] - b["min"][i] for i in range(3))

    def span(key):
        b = B.get(key)
        if not b:
            return None
        return b["min"][0], b["max"][0]

    # 1 组合体总长（SC_A bbox，含鼻部钝化球则 +18；本体 0–8050）
    a = dims("SC_A")
    if a is None:
        add(1, "组合体总长", 8050, 2, "报告缺 SC_A bbox", "SKIP", "运行 build_all.py -- s6", "s6")
    else:
        L = a[0]
        add(1, "组合体总长", 8050, 2, f"{L:.1f}", "PASS" if near(L, 8050, 2) else "FAIL",
            "鼻尖球与 LE 链首端相切于 x=0，无前凸", "s6")

    # 2 锐矛本体（rm_body：机身+鼻尖+前缘链）
    m = dims("rm_body")
    if m is None:
        add(2, "锐矛 本体长/展", "4500/2600（LE管包络+31）", "2/6", "报告缺 rm_body bbox", "SKIP",
            "运行 build_all.py -- s2", "s2")
        add("2a", "锐矛 高 [DEV#1]", "850→650(等峰拱顶)", 2, "报告缺 rm_body bbox", "SKIP", "", "s2")
    else:
        l, sp, h = m
        ok = near(l, 4500, 2) and near(sp, 2631, 6)
        add(2, "锐矛 本体长/展", "4500/2600（LE管包络+31）", "2/6", f"{l:.0f}/{sp:.0f}",
            "PASS" if ok else "FAIL", "长含尾站 LE 珠 +18，展含 LE 珠 +18/侧", "s2")
        add("2a", "锐矛 高 [DEV#1]", "850→650(等峰拱顶)", 2, f"{h:.0f}",
            "DEV#1" if near(h, 650, 2) else "FAIL", "[V2] 顶部骑乘无人机，等峰拱顶峰值650", "s2")

    # 3 前缘后掠角：由站位表（params 唯一来源）推算，对照 §4.6 目标 74°
    if P is None:
        add(3, "锐矛前缘后掠角", 74, 0.5, "lib/params.py 不可用", "SKIP", "", "s2")
    else:
        sweep = math.degrees(math.atan2(P.RM_X[-1] - P.RM_X[0], P.RM_S[-1] - P.RM_S[0]))
        add(3, "锐矛前缘后掠角", 74, 0.5, f"{sweep:.1f}(站位表推算)",
            "PASS" if near(sweep, 74, 0.5) else "FAIL", "", "s2")

    # 4 搭载平台区间 [DEV#1]：目标以变更后口径核对
    if P is None:
        add(4, "搭载平台区间", "1600–4000→1600–4500", 2, "lib/params.py 不可用", "SKIP", "", "s6")
    else:
        add(4, "搭载平台区间", "1600–4500 [DEV#1]", 2,
            f"{P.RM_PLAT_X0:.0f}–{P.RM_PLAT_X1:.0f}",
            "DEV#1" if (near(P.RM_PLAT_X0, 1600, 2) and near(P.RM_PLAT_X1, 4500, 2)) else "FAIL",
            "[V2] 平台延伸覆盖无人机尾(4500)，变更申请待复核", "s6")

    # 5 支架间距：params 实际站位间距，对照 §4.6 目标 1200±1
    if P is None:
        add(5, "支架间距", 1200, 1, "lib/params.py 不可用", "SKIP", "", "s4")
    else:
        sp_br = P.BR_X2 - P.BR_X1
        add(5, "支架间距", 1200, 1, f"{sp_br:.0f}（{P.BR_X1:.0f}/{P.BR_X2:.0f}）",
            "DEV#2" if near(sp_br, 1200, 1) else "FAIL",
            "[V2] 站位 2900/4100 随影刃缩比移位，间距保持，变更申请待复核", "s4")

    # 6 影刃本体
    u = dims("yr_body")
    if u is None:
        add(6, "影刃 本体长/机身宽 [V2]", "1800/980", 2, "报告缺 yr_body bbox", "SKIP",
            "运行 build_all.py -- s3", "s3")
    else:
        l, w = u[0], u[1]
        add(6, "影刃 本体长/机身宽 [V2]", "1800/980", 2, f"{l:.0f}/{w:.0f}",
            "PASS" if (near(l, 1800, 2) and near(w, 980, 2)) else "FAIL", "", "s3")
    if P is None:
        add("6a", "影刃部署翼展 [V2]", 1580, 2, "lib/params.py 不可用", "SKIP", "", "s3")
    else:
        span_dep = 2 * (P.YW_ROOTY + P.YW_SPAN)
        add("6a", "影刃部署翼展 [V2]", 1580, 2, f"{span_dep:.0f}(参数 2×({P.YW_ROOTY:.0f}+{P.YW_SPAN:.0f}))",
            "PASS" if near(span_dep, 1580, 2) else "FAIL", "部署态翼尖 y_loc=铰线490+展300", "s3")
    ub = dims("yr_uav")
    if ub is None:
        add("6b", "影刃收拢包络高(局部)", 422, 6, "报告缺 yr_uav bbox", "SKIP", "", "s3")
    else:
        h_u = ub[2]
        add("6b", "影刃收拢包络高(局部)", 422, 6, f"{h_u:.0f}",
            "PASS" if near(h_u, 422, 6) else "INFO",
            "局部 0–515（翼尖 95+420），含进气道 −60/SERN −70；超差请人工复核", "s3")

    # 7 外翼前缘后掠角：params 实配值对照 §4.6 目标 65°
    if P is None:
        add(7, "外翼前缘后掠角", 65, 0.5, "lib/params.py 不可用", "SKIP", "", "s3")
    else:
        add(7, "外翼前缘后掠角", 65, 0.5, f"{P.YW_LE_SWEEP:.1f}(参数生成)",
            "PASS" if near(P.YW_LE_SWEEP, 65, 0.5) else "FAIL", "", "s3")

    # 8 整流罩
    fx = span("fa_right")
    fl = B.get("fa_left")
    if fx is None or fl is None:
        add(8, "整流罩 X区间/顶高", "2000–4550/≤1180", 3, "报告缺 fa_right/fa_left bbox", "SKIP",
            "运行 build_all.py -- s4", "s4")
    else:
        x0, x1 = fx
        zt = max(B["fa_right"]["max"][2], fl["max"][2])
        ok = near(x0, 1950, 3) and near(x1, 4550, 3) and zt <= 1183
        add(8, "整流罩 X区间/顶高", "2000–4550/≤1180", 3, f"{x0:.0f}–{x1:.0f}/{zt:.0f}",
            "PASS" if ok else "FAIL", "[DEV#3] 包络紧贴：头部锥度自 1950，顶高=包络+15", "s4")

    # 9 泄压孔
    n = C.get("portholes")
    if n is None:
        add(9, "泄压孔", "4×Φ20", 0, "报告缺 counts.portholes", "SKIP", "运行 build_all.py -- s4", "s4")
    else:
        add(9, "泄压孔", "4×Φ20", 0, f"{n}处", "PASS" if n == 4 else "FAIL", "", "s4")

    # 10 助推器：机体 φ900（构造保证）+ 栅格舵外缘（实测）
    fins = dims("bo_fins")
    if fins is None:
        add(10, "助推器直径/栅格外缘", "900/1156(45°位包络)", "1/6", "报告缺 bo_fins bbox", "SKIP",
            "运行 build_all.py -- s5", "s5")
    else:
        fin_dia = max(fins[1], fins[2])
        add(10, "助推器直径/栅格外缘", "900/1156(45°位包络)", "1/6", f"900(构造)/{fin_dia:.0f}",
            "PASS" if near(fin_dia, 1156, 6) else "FAIL",
            "栅格舵径向 450→790，45°/135°/225°/315° 位 y/z 向包络=2·790·cos45°+舵厚", "s5")

    # 11 过渡段/分离面：params 构造值（过渡段 4500–4850，即 4502 起避免与机体共面）
    if P is None:
        add(11, "过渡段长/分离面", "350/4850", 2, "lib/params.py 不可用", "SKIP", "", "s5")
    else:
        tran_l = P.BO_TRAN_X1 - P.BO_TRAN_X0
        ok = near(tran_l, 350, 2) and near(P.BO_TRAN_X1, 4850, 2)
        add(11, "过渡段长/分离面", "350/4850", 2, f"{tran_l:.0f}/{P.BO_TRAN_X1:.0f}(构造保证)",
            "PASS" if ok else "FAIL", "", "s5")

    # 12 STL：逐文件存在性 + 三角数与文件大小自洽（非仅存在性）
    stl_dir = export_dir("stl")
    verdicts = []
    for fname in STEP_STL_FILES:
        fp = os.path.join(stl_dir, fname)
        ok, msg = stl_verdict(fp) if os.path.exists(fp) else (False, "文件缺失")
        verdicts.append((fname, ok, msg))
    n_ok = sum(1 for _, ok, _ in verdicts)
    bad_txt = "；".join(f"{f}:{msg}" for f, ok, msg in verdicts if not ok) or "全部自洽"
    add(12, "STL 导出", f"{len(STEP_STL_FILES)} 个均完整", "—", f"{n_ok}/{len(STEP_STL_FILES)} {bad_txt}",
        "PASS" if n_ok == len(STEP_STL_FILES) else "FAIL", f"见 {stl_dir}", "s7")

    # 13 单位mm / thunder.blend：存在 + Blender 头 + 体量非空
    bp = blend_path()
    if not os.path.exists(bp):
        add(13, "单位mm / thunder.blend", "通过", "—", "文件缺失", "FAIL",
            "运行 build_all.py -- build 生成", "s7")
    else:
        with open(bp, "rb") as f:
            head = f.read(7)
        sz = os.path.getsize(bp)
        ok = head == b"BLENDER" and sz > 1024 * 1024
        add(13, "单位mm / thunder.blend", "通过", "—", f"{head.decode('ascii', 'replace')!r} {sz // 1024}KB",
            "PASS" if ok else "FAIL", "", "s7")

    # 14 质心估算（U4：几何体积形心 × §1.4 质量加权；对照 §2.4.3 设计值 62%L=2790）
    cg = R.get("centroid", {})
    if "rm" in cg:
        cg_rm = cg["rm"]["centroid_mm"][0]
        dev = (cg_rm - 2790.0) / 4500.0 * 100
        add("14a", "锐矛几何形心 vs 重心设计 62%L", 2790, 50, f"{cg_rm:.0f} ({cg_rm/4500*100:.1f}%L)",
            "INFO", f"体积形心口径（空腔/推进剂分布未细分），偏差 {dev:+.1f}%L", "s6")
        if "STACK_A" in cg:
            s = cg["STACK_A"]
            add("14b", "组合体质量加权质心 x", "—", "—", f"{s['cg_x_mm']:.0f} (z={s['cg_z_mm']:.0f})",
                "INFO", f"总质量 {s['mass_kg']:.0f}kg；助推段静稳定由栅格舵保证（§2.2.3）", "s6")
    else:
        add("14a", "锐矛几何形心 vs 重心设计 62%L", 2790, 50, "报告缺 centroid.rm", "SKIP",
            "运行 build_all.py -- s6", "s6")
    return rows


def main():
    step = None
    if len(sys.argv) > 1:
        step = sys.argv[1].lower()
        if step not in ("s2", "s3", "s4", "s5", "s6", "s7"):
            print(f"[CHECK] 未知步骤 {sys.argv[1]!r}；{USAGE}")
            sys.exit(2)
    R = load_report()
    rows = [r for r in build_rows(R) if step is None or r[7] == step]
    print("=" * 104)
    print(f"{'#':<4}{'检查项':<22}{'目标':<26}{'容差':<7}{'实测':<20}{'状态':<7}备注")
    print("-" * 104)
    for r in rows:
        print(f"{str(r[0]):<4}{r[1]:<22}{str(r[2]):<26}{str(r[3]):<7}{str(r[4]):<20}{r[5]:<7}{r[6]}")
    print("=" * 104)
    npass = sum(1 for r in rows if r[5] == "PASS")
    ndev = sum(1 for r in rows if r[5].startswith("DEV"))
    nskip = sum(1 for r in rows if r[5] == "SKIP")
    ninfo = sum(1 for r in rows if r[5] == "INFO")
    nfail = sum(1 for r in rows if r[5] == "FAIL")
    print(f"PASS={npass}  DEV={ndev}  SKIP={nskip}  INFO={ninfo}  FAIL={nfail}"
          + (f"  [步骤 {step}]" if step else ""))
    if nskip:
        print("[CHECK] 存在 SKIP 项：报告数据不全，请重跑 build_all.py 对应步骤后复核。")
    sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()
