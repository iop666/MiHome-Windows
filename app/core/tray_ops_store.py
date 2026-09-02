# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""托盘设备「调节项」自选的本地持久化。

每个 did 独立保存用户勾选的调节项名称列表（顺序即展示顺序）。
- 无记录（None）= 未自选：托盘调节用默认常用项（与卡片快捷面板一致）；
- 记录为空列表 = 明确不提供调节；
- 记录非空 = 只展示勾选的这些项。

文件与 tray.json 同目录，名为 tray_ops.json，不与主配置互相干扰。
"""

from app.core import _json_store

_VERSION = 1
_FILENAME = "tray_ops.json"


def _empty() -> dict:
    return {"version": _VERSION, "devices": {}}


def _read_raw() -> dict:
    raw = _json_store.read_json(_json_store.data_file(_FILENAME), _empty())
    if raw.get("version") != _VERSION or not isinstance(raw.get("devices"), dict):
        return _empty()
    return raw


def _write_raw(raw: dict) -> None:
    _json_store.write_json(_json_store.data_file(_FILENAME), raw)


def selected(did: str) -> list[str] | None:
    """该 did 的自选调节项；None=未自选（用默认常用项）。"""
    raw = _read_raw()
    val = raw["devices"].get(str(did))
    if val is None:
        return None
    if isinstance(val, list) and all(isinstance(k, str) for k in val):
        return list(val)
    return None


def save(did: str, names: list[str]) -> None:
    """保存自选列表（可为空=不提供调节）。"""
    raw = _read_raw()
    seen: set[str] = set()
    uniq: list[str] = []
    for n in names:
        s = str(n)
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    raw["devices"][str(did)] = uniq
    _write_raw(raw)


def clear(did: str) -> None:
    """删除自选记录，恢复「默认常用项」。"""
    raw = _read_raw()
    if str(did) in raw["devices"]:
        del raw["devices"][str(did)]
        _write_raw(raw)


def cleanup(dids: set[str]) -> None:
    """托盘列表变更后清理已移除设备的自选记录。"""
    raw = _read_raw()
    devices = raw["devices"]
    removed = [d for d in devices if d not in dids]
    if removed:
        for d in removed:
            del devices[d]
        _write_raw(raw)
