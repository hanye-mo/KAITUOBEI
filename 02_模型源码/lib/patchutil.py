# -*- coding: utf-8 -*-
"""文本补丁两阶段执行器：内存改写 → 全量语法校验 → 一次性落盘（失败可回滚）

补丁作业格式 apply(patches)：patches 为 [(relpath, [(tag, old, new[, skip_if]), ...]), ...]
  - relpath 相对源码根目录（02_模型源码）解析，与当前工作目录无关；
  - (tag, old, new) 语义：
      skip_if 命中         → 视为已应用/已被后续补丁取代，跳过（用于 old⊂new 等无法
                              自判幂等的作业，标记取"应用后必然出现"的子串）；
      old 命中             → 替换为 new；
      old 未命中、new 已在 → 视为已应用，跳过（脚本可重复执行）；
      两者皆无             → 报错中止，且任何文件都不落盘；
      new 为 None          → 只读校验锚点存在，不改写文件。
  - 全部替换完成并通过 ast 语法校验后才写盘；写盘阶段出错则回滚已写文件，
    不会留下半修改状态。
"""
import ast
import io
import os

from lib.paths import SRC_DIR


def _read_text(path):
    with io.open(path, "rb") as f:
        raw = f.read()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    return text, crlf


def _write_text(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    tmp = path + ".patching"
    with io.open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def apply(patches, label="patch"):
    """执行补丁，返回实际改写的文件相对路径列表。任一锚点缺失或语法错误时不修改任何文件。"""
    plan = []                                   # (abs_path, new_text, orig_text, crlf)
    for rel, jobs in patches:
        path = os.path.join(SRC_DIR, rel)
        s, crlf = _read_text(path)
        orig = s
        for job in jobs:
            tag, old, new = job[0], job[1], job[2]
            skip_if = job[3] if len(job) > 3 else None
            if skip_if and skip_if in s:
                print(f"[{label}] {rel} :: {tag} 已应用/已被后续补丁取代（含 {skip_if!r}），跳过")
                continue
            if old in s:
                if new is None:
                    print(f"[{label}] {rel} :: {tag} 锚点校验通过")
                    continue
                s = s.replace(old, new)
                print(f"[{label}] {rel} :: {tag} 已替换")
            elif new is not None and new in s:
                print(f"[{label}] {rel} :: {tag} 已应用过，跳过")
            else:
                raise RuntimeError(f"[{label}] {rel} :: 锚点缺失 [{tag}]，未修改任何文件")
        if s != orig:
            ast.parse(s)                        # 语法不合法则整体中止，不落盘
        plan.append((path, s, orig, crlf))

    written = []
    try:
        for path, s, _, crlf in plan:
            if s != _read_text(path)[0]:
                _write_text(path, s, crlf)
                written.append(path)
    except Exception:
        for path, _, orig, crlf in plan:        # 回滚本轮已写文件（未写的恢复为等值，无副作用）
            if path in written:
                _write_text(path, orig, crlf)
        raise
    return [os.path.relpath(p, SRC_DIR) for p in written]
