# -*- coding: utf-8 -*-
"""一键构建/导出/渲染总控（Blender Python）

用法: blender --background --factory-startup --python build_all.py -- <step>
步骤（大小写不敏感，对应《建模方案》§4.3 S1→S7 与常用组合）:
  s1            参数/截面自检（不建几何）
  s2..s6        构建全部部件，打印对应步骤 bbox 自检，s6 写 check_report.json
  s7            导出 STL + 渲染静帧 + 分离动画（全流程）
  build/export  构建 + 导出（不出图）
  render        构建 + 渲染静帧
  render_seq    构建 + 分离动画
  all           构建 + 导出 + 渲染 + 动画
产物写入交付物根目录（默认同级 03_交付物/，环境变量 THUNDER_OUT 可覆盖），见 lib/paths.py。
"""
import bpy
import sys
import os
import json
import math
import time
import mathutils

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from asm.build_scenes import build_everything
from builders.common import union_bbox
from lib import params as P
from lib.paths import export_dir, report_path, blend_path

OUT = export_dir()
REPORT = {"engine": None, "bboxes": {}, "counts": {}, "notes": [], "errors": []}

# 步骤 → 说明（与《建模方案》§4.3 S1→S7 对应；其余为组合快捷方式）
STEPS = {
    "s1": "S1 参数/截面自检（不建几何）",
    "s2": "S2 构建部件，自检锐矛 bbox",
    "s3": "S3 构建部件，自检影刃 bbox",
    "s4": "S4 构建部件，自检支架/整流罩",
    "s5": "S5 构建部件，自检助推器",
    "s6": "S6 场景/关键帧 bbox 全量自检，写 check_report.json",
    "s7": "S7 导出 STL + 渲染静帧 + 分离动画",
    "build": "构建 + 导出（不出图）",
    "export": "构建 + 导出（不出图）",
    "render": "构建 + 渲染静帧",
    "render_seq": "构建 + 分离动画",
    "all": "构建 + 导出 + 渲染 + 动画",
}
EXPORT_STEPS = ("build", "export", "all", "s7")
RENDER_STEPS = ("render", "all", "s7")
SEQ_STEPS = ("render_seq", "all", "s7")


def usage(err=None):
    if err:
        print(f"[USAGE] {err}")
    print("[USAGE] blender --background --factory-startup --python build_all.py -- <step>")
    for k, v in STEPS.items():
        print(f"[USAGE]   {k:<11} {v}")
    sys.exit(2)


def parse_step():
    """解析 `--` 之后的步骤参数；缺失/未知直接报用法并退出（不静默全量构建）。"""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        usage("缺少步骤参数（`--` 后为空）")
    step = argv[0].lower()
    if argv[1:]:
        usage(f"多余参数 {argv[1:]!r}，一次只接受一个步骤")
    if step not in STEPS:
        usage(f"未知步骤 {argv[0]!r}")
    return step


def setup_scene(scene):
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.001
    scene.unit_settings.length_unit = 'MILLIMETERS'
    try:
        scene.view_settings.view_transform = 'Standard'   # 避免 AgX 洗白材质色
        scene.view_settings.look = 'None'
    except Exception:
        pass
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def probe_engine(scene):
    """EEVEE(快) → Cycles CPU，探测可用性（临时相机+灯光）。
    判据只看 RGB 通道灰度差：RGBA 的 Alpha 恒为 1 时，纯黑不透明图也会给出
    spread=1 的假通过；两引擎都失败则中止（不强行回退 Cycles）。"""
    os.makedirs(OUT, exist_ok=True)
    cam = bpy.data.cameras.new("probe_cam")
    cam.clip_start = 0.1
    cam.clip_end = 1e6
    cob = bpy.data.objects.new("probe_cam", cam)
    scene.collection.objects.link(cob)
    cob.location = (4000, -9000, 600)
    cob.rotation_euler = (math.radians(90), 0, 0)
    sun = bpy.data.lights.new("probe_sun", 'SUN')
    sun.energy = 3.0
    sob = bpy.data.objects.new("probe_sun", sun)
    scene.collection.objects.link(sob)
    sob.rotation_euler = (math.radians(45), 0, math.radians(30))
    probe_png = os.path.join(OUT, "_probe.png")
    candidates = ['BLENDER_EEVEE_NEXT', 'CYCLES']
    for eng in candidates:
        try:
            scene.render.engine = eng
            scene.render.resolution_x, scene.render.resolution_y = 64, 64
            scene.render.filepath = probe_png
            if eng == 'CYCLES':
                scene.cycles.device = 'CPU'
                scene.cycles.samples = 4
            scene.camera = cob
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(probe_png)
            px = list(img.pixels[:4096])
            bpy.data.images.remove(img)
            rgb = px[0::4] + px[1::4] + px[2::4]     # 剔除 Alpha 通道
            spread = max(rgb) - min(rgb)
            REPORT["notes"].append(f"probe {eng}: rgb_spread={spread:.3f}")
            if spread > 0.02:
                REPORT["engine"] = eng
                break
        except Exception as e:
            REPORT["notes"].append(f"probe {eng} FAIL: {e}")
    for nm in ("probe_cam", "probe_sun"):
        ob = bpy.data.objects.get(nm)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)
    if REPORT["engine"] is None:
        raise RuntimeError(
            "渲染引擎探测失败（EEVEE/Cycles 均无法出图，不强行回退）："
            + "; ".join(n for n in REPORT["notes"] if n.startswith("probe")))
    scene.render.engine = REPORT["engine"]
    if REPORT["engine"] == 'CYCLES':
        scene.cycles.device = 'CPU'
        scene.cycles.samples = 24
        try:
            scene.cycles.use_denoising = True
        except Exception:
            pass
        scene.render.resolution_x, scene.render.resolution_y = 1280, 720
        scene.render.resolution_percentage = 100
    else:
        scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    try:
        os.remove(probe_png)
    except OSError:
        pass


def export_stl(objs, path):
    import bpy.ops as ops
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, apply_modifiers=True)


def do_export(ctx):
    stl = os.path.join(OUT, "stl")
    os.makedirs(stl, exist_ok=True)
    groups = {
        "rm_missile": [o for o in bpy.data.objects if o.name.startswith(("RM_",)) and o.name != "RM_trim"],
        "yr_uav": [o for o in bpy.data.objects if o.name.startswith(("YR_", "YW_")) and o.name != "YR_trim"],
        "br_brackets": [o for o in bpy.data.objects if o.name.startswith("BR_")],
        "fa_fairing": [o for o in bpy.data.objects if o.name.startswith("FA_")],
        "bo_booster": [o for o in bpy.data.objects if o.name.startswith("BO_")],
    }
    PARTS = ctx["colls"]["PARTS"]
    for nm, objs in groups.items():
        objs = [o for o in objs if o.name in {x.name for x in PARTS.objects}]
        if objs:
            export_stl(objs, os.path.join(stl, nm + ".stl"))
            REPORT["counts"][nm] = len(objs)
    # 状态级 STL：导出前隐藏其它状态
    states = {"sc_a": "SC_A", "sc_a2": "SC_A2", "sep_k0": "SC_SEP", "sc_c1": "SC_C1", "sc_c2": "SC_C2"}
    cur_frame = 0
    bpy.context.scene.frame_set(cur_frame)
    for fname, cname in states.items():
        coll = ctx["colls"][cname]
        for c in ctx["colls"].values():
            if c.name.startswith("SC_"):
                c.hide_render = (c.name != cname)
        objs = [o for o in coll.objects if o.type == 'MESH']
        export_stl(objs, os.path.join(stl, fname + ".stl"))
        REPORT["counts"][fname] = len(objs)
        for c in ctx["colls"].values():
            if c.name.startswith("SC_"):
                c.hide_render = False
    # 3MF（Blender 4.5 无内置导出器则降级）
    try:
        bpy.ops.wm.stl_export  # noqa — 触发已有
        has3mf = any("3mf" in opId.lower() for opId in dir(bpy.ops.wm))
        if has3mf:
            REPORT["notes"].append("3MF exporter found (not exercised)")
        else:
            REPORT["notes"].append("3MF exporter 不存在(4.5 仅内置导入) → 按 §0.3 降级 STL+BLEND")
    except Exception as e:
        REPORT["notes"].append(f"3MF check error: {e}")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path())


def bbox_report(ctx):
    b = REPORT["bboxes"]
    def rec(name, objs):
        objs = [o for o in objs if o.type == 'MESH']
        if objs:
            mn, mx = union_bbox(objs)
            b[name] = {"min": [round(v, 1) for v in mn], "max": [round(v, 1) for v in mx]}
    for cname in ("SC_A", "SC_A2", "SC_SEP", "SC_C1", "SC_C2"):
        bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()          # 刷新 bound_box / matrix_world（陈旧值会骗人）
    PARTS = ctx["colls"]["PARTS"].objects
    rec("rm_missile", [o for o in PARTS if o.name.startswith("RM_") and o.name != "RM_trim"])
    rec("yr_uav", [o for o in PARTS if o.name.startswith(("YR_", "YW_")) and o.name != "YR_trim"])
    rec("brackets", [o for o in PARTS if o.name.startswith("BR_")])
    rec("fa_right", [o for o in PARTS if o.name == "FA_R"])
    rec("fa_left", [o for o in PARTS if o.name == "FA_L"])
    rec("booster", [o for o in PARTS if o.name.startswith("BO_")])
    rec("bo_fins", [o for o in PARTS if o.name.startswith("BO_GridFin")])
    rec("rm_body", [ctx["rm"]["body"]])
    rec("yr_body", [ctx["yr"]["body"]])
    for cname in ("SC_A", "SC_A2", "SC_C1", "SC_C2"):
        bpy.context.scene.frame_set(0)
        rec(cname, [o for o in ctx["colls"][cname].objects if o.type == 'MESH'])
    REPORT["counts"]["portholes"] = len(ctx["fa"].get("ports", []))
    # U4 质心估算：部件体积+形心 → 按方案 §1.4 质量加权质心（几何口径，空腔/贮箱未细分）
    import bmesh as _bm


    def _vol_centroid(ob):
        bm = _bm.new()
        bm.from_mesh(ob.data)
        mwx = ob.matrix_world
        for v in bm.verts:
            v.co = mwx @ v.co
        vol = bm.calc_volume(signed=False)
        cen = (sum((f.calc_center_median() * f.calc_area() for f in bm.faces), mathutils.Vector()) /
               sum(f.calc_area() for f in bm.faces)) if bm.faces else mathutils.Vector()
        bm.free()
        return vol / 1e9, (cen.x, cen.y, cen.z)          # m³, mm


    cg = {}
    masses = {"rm": 3440.0, "yr": 850.0, "fa": 90.0, "bo": 4950.0}
    groups = {
        "rm": [o for o in PARTS if o.name.startswith("RM_") and "trim" not in o.name and o.type == 'MESH'],
        "yr": [o for o in PARTS if o.name.startswith(("YR_", "YW_")) and "trim" not in o.name and o.type == 'MESH'],
        "fa": [o for o in PARTS if o.name.startswith("FA_") and o.type == 'MESH'],
        "bo": [o for o in PARTS if o.name.startswith("BO_") and o.type == 'MESH'],
    }
    for g, objs in groups.items():
        if not objs:
            continue
        tv = sum(_vol_centroid(o)[0] for o in objs)
        tcx = sum(_vol_centroid(o)[0] * _vol_centroid(o)[1][0] for o in objs)
        cg[g] = {"vol_m3": round(tv, 4), "centroid_mm": [round(tcx / tv, 1), 0.0,
                round(sum(_vol_centroid(o)[0] * _vol_centroid(o)[1][2] for o in objs) / tv, 1)]}
    if "rm" in cg:
        cg["rm"]["cg_x_mm"] = round(cg["rm"]["centroid_mm"][0], 1)
        m_tot = sum(masses[g] for g in cg)
        cx = sum(masses[g] * cg[g]["centroid_mm"][0] for g in cg) / m_tot
        cz = sum(masses[g] * cg[g]["centroid_mm"][2] for g in cg) / m_tot
        cg["STACK_A"] = {"mass_kg": m_tot, "cg_x_mm": round(cx, 1), "cg_z_mm": round(cz, 1)}
        # C1 锐矛单机（质量集中在弹体几何形心附近——工程近似）
        cg["C1"] = {"cg_x_mm": cg["rm"]["centroid_mm"][0]}
    REPORT["centroid"] = cg


def step_s1():
    """S1 参数/截面自检（《建模方案》§4.3）：RM 各站位截面积落在 0.60–0.88×(2s·h) 带内，
    RM/YR 截面点数正确且无退化点；不通过则抛错中止。"""
    from lib import profiles, params as _P
    bad = []
    for tag, xs, ss, hs, (ep, eq) in (
            ("RM", _P.RM_X, _P.RM_S, _P.RM_H, (_P.RM_SE_P, _P.RM_SE_Q)),
            ("YR", _P.YR_X, _P.YR_S, _P.YR_H, (_P.YR_SE_P, _P.YR_SE_Q))):
        for i in range(1, len(xs)):
            s, h = ss[i], hs[i]
            if s <= 1e-9 or h <= 1e-9:
                continue
            poly = profiles.arch_pts(s, h, p=ep, q=eq)
            finite = all(math.isfinite(v) for pt in poly for v in pt)
            ratio = profiles.polygon_area(poly) / (2 * s * h)
            ok = finite and len(poly) >= 8 and (tag != "RM" or 0.60 <= ratio <= 0.88)
            REPORT["notes"].append(f"s1 {tag}@x={xs[i]}: n={len(poly)} ratio={ratio:.3f} "
                                   f"{'OK' if ok else 'FAIL'}")
            if not ok:
                bad.append(f"{tag}@x={xs[i]} ratio={ratio:.3f} finite={finite}")
    if bad:
        raise RuntimeError("S1 截面自检失败（RM 目标带 0.60–0.88）: " + "; ".join(bad))
    print("[S1] 参数/截面自检通过")


def print_dims(names):
    b = REPORT["bboxes"]
    for nm in names:
        v = b.get(nm)
        if v:
            print(f"[BBOX] {nm:<10s} min={v['min']} max={v['max']}")


def render_stills(ctx):
    scene = bpy.context.scene
    eng = REPORT["engine"]
    png = os.path.join(OUT, "png")
    os.makedirs(png, exist_ok=True)
    shots = []
    for cam, fname in (("cam_a_front", "sc_a_front"), ("cam_a_side", "sc_a_side"),
                       ("cam_a_top", "sc_a_top"), ("cam_a_axo1", "sc_a_axo1"),
                       ("cam_a_axo2", "sc_a_axo2")):
        shots.append(("SC_A", 0, cam, fname))
    shots += [("SC_A2", 0, "cam_a2_side", "sc_a2_side"), ("SC_A2", 0, "cam_a2_axo", "sc_a2_axo")]
    # 装配图（隐藏整流罩，三视图 + 轴测）
    for cam, fname in (("cam_a2_front", "assembly_front"), ("cam_a2_side", "assembly_side"),
                       ("cam_a2_top", "assembly_top"), ("cam_a2_axo", "assembly_axo")):
        shots.append(("SC_A2", 0, cam, fname))
    for k in ("K0", "K1", "K2", "K3", "K4", "K5"):
        f = P.K_FRAMES[k]
        shots.append(("SC_SEP", f, "cam_sep_side", f"sep_{k.lower()}_side"))
        shots.append(("SC_SEP", f, "cam_sep_axo", f"sep_{k.lower()}_axo"))
    for cam, fname in (("cam_c1_front", "sc_c1_front"), ("cam_c1_side", "sc_c1_side"),
                       ("cam_c1_top", "sc_c1_top"), ("cam_c1_axo", "sc_c1_axo")):
        shots.append(("SC_C1", 0, cam, fname))
    for cam, fname in (("cam_c2_front", "sc_c2_front"), ("cam_c2_side", "sc_c2_side"),
                       ("cam_c2_top", "sc_c2_top"), ("cam_c2_axo", "sc_c2_axo")):
        shots.append(("SC_C2", 0, cam, fname))
    for cname, f, cam, fname in shots:
        coll = ctx["colls"][cname]
        for c in ctx["colls"].values():
            if c.name.startswith("SC_"):
                c.hide_render = (c.name != cname)
        hide_fa = fname.startswith("assembly")
        for o in coll.objects:
            if o.name.startswith("FA_"):
                o.hide_render = hide_fa
        scene.frame_set(f)
        scene.camera = bpy.data.objects.get(cam)
        scene.render.filepath = os.path.join(png, fname + ".png")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        REPORT["notes"].append(f"render {fname}: {time.time()-t0:.1f}s")
        for o in coll.objects:
            if o.name.startswith("FA_"):
                o.hide_render = False
    for c in ctx["colls"].values():
        if c.name.startswith("SC_"):
            c.hide_render = False


def render_seq(ctx):
    scene = bpy.context.scene
    mp4 = os.path.join(OUT, "mp4")
    os.makedirs(mp4, exist_ok=True)
    for c in ctx["colls"].values():
        if c.name.startswith("SC_"):
            c.hide_render = (c.name != "SC_SEP")
    scene.frame_start, scene.frame_end = 0, P.K_FRAMES["END"]
    scene.camera = bpy.data.objects.get("cam_sep_axo")
    r = scene.render
    r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format = 'MPEG4'
    r.ffmpeg.codec = 'H264'
    r.ffmpeg.constant_rate_factor = 'HIGH'
    if REPORT["engine"] != 'CYCLES':
        r.resolution_x, r.resolution_y = 1280, 720
    else:
        r.resolution_x, r.resolution_y = 960, 540
        scene.cycles.samples = 12
    r.filepath = os.path.join(mp4, "sep_seq.mp4")
    bpy.ops.render.render(animation=True)
    r.image_settings.file_format = 'PNG'
    for c in ctx["colls"].values():
        if c.name.startswith("SC_"):
            c.hide_render = False


def write_report():
    with open(report_path(), "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=1)
    print("[REPORT]", report_path())
    print("[REPORT]", json.dumps(REPORT["bboxes"], ensure_ascii=False))


def main():
    step = parse_step()
    scene = bpy.context.scene
    if step == "s1":                       # 纯参数自检：不建几何、不探测引擎
        step_s1()
        write_report()
        return
    setup_scene(scene)
    ctx = build_everything(scene)
    print("[BUILD] parts done")
    bbox_report(ctx)
    if step == "s2":
        print_dims(("rm_body", "rm_missile"))
    elif step == "s3":
        print_dims(("yr_body", "yr_uav"))
    elif step == "s4":
        print_dims(("brackets", "fa_right", "fa_left"))
        print("[COUNT] portholes =", REPORT["counts"].get("portholes"))
    elif step == "s5":
        print_dims(("booster", "bo_fins"))
    elif step == "s6":
        print_dims(("SC_A", "rm_body", "yr_body"))
        print("[KFRAMES]", P.K_FRAMES)
    if step in RENDER_STEPS or step in SEQ_STEPS:
        probe_engine(scene)
        print("[ENGINE]", REPORT["engine"])
    if step in EXPORT_STEPS:
        do_export(ctx)
        print("[EXPORT] done")
    if step in RENDER_STEPS:
        render_stills(ctx)
        print("[RENDER] stills done")
    if step in SEQ_STEPS:
        render_seq(ctx)
        print("[RENDER] seq done")
    write_report()


if __name__ == "__main__":
    main()
