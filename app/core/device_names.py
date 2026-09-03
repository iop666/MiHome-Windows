# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""设备显示名覆盖存储（主界面重命名）。

真实改名在米家云端，本地客户端只维护“显示名覆盖”：用户在本程序里
给某台设备起的名字优先于云端/自动本地化名称展示，且可一键恢复默认。

文件与其他配置同放用户数据目录（settings.json 同侧），读写失败不阻断
主流程——重命名只是锦上添花，丢了退回云端名即可。
"""

from app.core import _json_store

_FILENAME = "device_names.json"


def _read() -> dict:
    raw = _json_store.read_json(_json_store.data_file(_FILENAME), {})
    if not isinstance(raw, dict):
        return {}
    return raw


def load() -> dict[str, dict]:
    """did -> {"name": 覆盖名, "orig": 覆盖前的默认名}。"""
    return {str(k): v for k, v in _read().items()
            if isinstance(v, dict) and v.get("name")}


def get(did: str) -> dict | None:
    return load().get(str(did))


def set_name(did: str, name: str, orig: str | None = None) -> None:
    """写入覆盖名。orig 传 None 时沿用旧条目里的原始名（首次设置时
    以 name 兜底为原始名，避免覆盖丢失默认名）。"""
    raw = _read()
    old = raw.get(str(did))
    if orig is None:
        orig = (old.get("orig") if isinstance(old, dict) and old.get("orig")
                else str(name))
    raw[str(did)] = {"name": str(name), "orig": str(orig)}
    _json_store.write_json(_json_store.data_file(_FILENAME), raw)


def remove(did: str) -> None:
    """删除覆盖，恢复默认名（由调用方用返回的 orig 刷新展示）。"""
    raw = _read()
    raw.pop(str(did), None)
    _json_store.write_json(_json_store.data_file(_FILENAME), raw)
