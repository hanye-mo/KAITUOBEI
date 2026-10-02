# -*- coding: utf-8 -*-
"""交付物路径解析（纯 Python，无 bpy 依赖，普通 Python 与 Blender Python 通用）

优先级：
1. 环境变量 THUNDER_OUT —— 指定交付物根目录（含 thunder.blend / check_report.json / export/）
2. 交接包约定目录 —— 源码同级 03_交付物/，存在即采用
3. 回退源码目录 —— 02_模型源码 被单独拷出时自包含运行（产物落在源码旁）

全部构建/自检/仿真脚本经此取路径，保证重建时写入与既有交付物同一位置，
不会在源码目录下另起一套 export/。
"""
import os

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 02_模型源码
PKG_DIR = os.path.dirname(SRC_DIR)                                      # 交接包根


def deliverable_root():
    env = os.environ.get("THUNDER_OUT")
    if env:
        return os.path.abspath(env)
    cand = os.path.join(PKG_DIR, "03_交付物")
    if os.path.isdir(cand):
        return cand
    return SRC_DIR


def export_dir(sub=""):
    d = os.path.join(deliverable_root(), "export")
    return os.path.join(d, sub) if sub else d


def report_path():
    return os.path.join(deliverable_root(), "check_report.json")


def blend_path():
    return os.path.join(deliverable_root(), "thunder.blend")
