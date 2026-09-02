# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""桌面小组件配置的本地持久化（widgets.json）。

每个小组件一条记录：
- id: 稳定标识（创建时生成）
- dids: 展示的设备 did 列表（顺序即展示顺序）
- x/y: 上次停留的桌面坐标
- scale: 显示缩放百分比 50–200（整数，1% 步进可调）
- locked: 锁定位置（True 时不可拖拽移动；需在设置中解锁）
- topmost: 是否置顶（固定在最上层）
- bg_alpha: 背景不透明度 0–100（0 全透明，100 不透明）
- visible: 是否显示（默认 True）
"""

import json
import time

from app.core import _json_store

_VERSION = 1
_FILENAME = "widgets.json"

_UI_MIN_SCALE, _UI_MAX_SCALE = 50, 200


def _empty() -> dict:
    return {"version": _VERSION, "widgets": []}


def _read_raw() -> dict:
    raw = _json_store.read_json(_json_store.data_file(_FILENAME), _empty())
    if raw.get("version") != _VERSION or not isinstance(raw.get("widgets"), list):
        return _empty()
    return raw


def load_all() -> list[dict]:
    """读取全部小组件配置；坏记录丢弃。"""
    result = []
    for w in _read_raw().get("widgets", []):
        norm = _normalize(w)
        if norm is not None:
            result.append(norm)
    return result


def _normalize(w) -> dict | None:
    if not isinstance(w, dict) or not isinstance(w.get("id"), str):
        return None
    dids = [str(d) for d in w.get("dids", []) if str(d)]
    if not dids:
        return None
    try:
        scale = int(w.get("scale", 100))
    except (TypeError, ValueError):
        scale = 100
    try:
        bg_alpha = int(w.get("bg_alpha", 90))
    except (TypeError, ValueError):
        bg_alpha = 90
    return {
        "id": w["id"],
        "dids": dids,
        "x": _int_or(w.get("x"), 120),
        "y": _int_or(w.get("y"), 120),
        "scale": min(max(scale, _UI_MIN_SCALE), _UI_MAX_SCALE),
        "locked": bool(w.get("locked", True)),
        "topmost": bool(w.get("topmost", True)),
        "bg_alpha": min(max(bg_alpha, 0), 100),
        "visible": bool(w.get("visible", True)),
    }


def _int_or(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def save_all(widgets: list[dict]) -> None:
    """整体落盘（顺序即列表顺序）。"""
    data = {"version": _VERSION, "widgets": widgets}
    _json_store.write_json(_json_store.data_file(_FILENAME), data)


def make_id() -> str:
    """稳定小组件 id。"""
    return f"w{int(time.time() * 1000)}{abs(hash(id(object()))) % 1000}"
