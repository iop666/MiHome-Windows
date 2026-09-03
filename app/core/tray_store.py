# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""托盘快捷设备的本地持久化。

与 workbench.json 同目录，单独文件 tray.json，默认空列表，由用户
在管理对话框中自主添加；顺序即展示顺序。
"""

from app.core import _json_store

_VERSION = 1
_FILENAME = "tray.json"


def _empty() -> dict:
    return {"version": _VERSION, "devices": []}


def _read_raw() -> dict:
    raw = _json_store.read_json(_json_store.data_file(_FILENAME), _empty())
    if raw.get("version") != _VERSION:
        return _empty()
    devices = raw.get("devices")
    if not isinstance(devices, list) or not all(isinstance(d, str) for d in devices):
        return _empty()
    return raw


def _write_raw(raw: dict) -> None:
    _json_store.write_json(_json_store.data_file(_FILENAME), raw)


def load() -> list[str]:
    """托盘设备 did 列表，按添加顺序。"""
    return list(_read_raw().get("devices", []))


def save(dids: list[str]) -> None:
    raw = _read_raw()
    # 去重保序
    seen: set[str] = set()
    uniq: list[str] = []
    for d in dids:
        s = str(d)
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    raw["devices"] = uniq
    _write_raw(raw)


def add(did: str) -> None:
    dids = load()
    if str(did) not in dids:
        dids.append(str(did))
        save(dids)


def remove(did: str) -> None:
    dids = load()
    s = str(did)
    if s in dids:
        dids.remove(s)
        save(dids)


def contains(did: str) -> bool:
    return str(did) in load()
