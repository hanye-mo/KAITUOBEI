# -*- coding: utf-8 -*-
"""材质 V4（军工配色，Principled BSDF + 视口色，Workbench 降级时用 diffuse_color）
分色体系：钛灰机体 / 深色碳陶 TPS（前缘、鼻尖）/ 近黑腔体（进气道、喷管、舱门）/
舵面深灰金属 / 陶瓷白支架 / 亮铝助推器。
"""
import bpy


def _mat(name, hexcol, rough, metal, alpha=1.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    r = ((hexcol >> 16 & 255) / 255, (hexcol >> 8 & 255) / 255, (hexcol & 255) / 255)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*r, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
            m.blend_method = 'BLEND'
    m.diffuse_color = (*r, alpha)
    m.roughness = rough
    m.metallic = metal
    return m


def _plume(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (1.0, 0.62, 0.25, 1.0)
        bsdf.inputs["Alpha"].default_value = 0.30
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (1.0, 0.55, 0.18, 1.0)
            bsdf.inputs["Emission Strength"].default_value = 9.0
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (1.0, 0.55, 0.18, 1.0)
    m.blend_method = 'BLEND'
    m.diffuse_color = (1.0, 0.6, 0.25, 0.30)
    return m


def build_all():
    return {
        "RM_BODY":  _mat("M_RM_BODY",  0x41474F, 0.50, 0.08),   # 钛灰机体（哑光）
        "TPS":      _mat("M_TPS",      0x1B1D21, 0.55, 0.03),   # 碳陶前缘/鼻尖（哑光近黑）
        "CTRL":     _mat("M_CTRL",     0x2C3036, 0.50, 0.15),   # 舵面/小翼
        "CAVITY":   _mat("M_CAVITY",   0x0C0D10, 0.80, 0.00),   # 腔体/舱门/喷管内壁
        "YR":       _mat("M_YR",       0x35383F, 0.55, 0.08),   # 影刃隐身灰
        "FA":       _mat("M_FA",       0x24262B, 0.45, 0.08),   # 整流罩
        "BR":       _mat("M_BR",       0xD8D3C8, 0.70, 0.00),   # 陶瓷白支架
        "BO":       _mat("M_BO",       0xC6CBD3, 0.35, 0.30),   # 亮铝助推器
        "NOZ":      _mat("M_NOZ",      0x4E3A28, 0.45, 0.60),   # 喷管青铜
        "FLOW":     _mat("M_FLOW",     0x7FA8D9, 0.30, 0.00, alpha=0.25),
        "PLUME":    _plume("M_PLUME"),
    }
