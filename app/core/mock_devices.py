# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""虚拟测试家庭（模拟设备模式）。

为「设备数量多 / 全屏布局」等 UI 压力测试提供完全离线的设备源：
设置环境变量 ``MIWU_MOCK_DEVICES`` 指向测试包 JSON 后，主界面用
本模块的 MockMijiaService 代替真实米家网关——设备列表、开关、
环境读数、详情工作台、快捷操作全部在内存里模拟，不联网、不登录、
不碰真实设备，天然满足安全红线。

测试包结构（见仓库 mock_packs/gen_mock_home.py 生成的 JSON）::

    {
      "home": {"name": "虚拟测试家庭"},
      "models": {                       # 型号 -> 该型号能力说明
        "yeelink.light.ceiling1": {
          "name": "Yeelight 智能吸顶灯",
          "props": [
            {"name": "on", "desc": "开关", "type": "bool", "rw": "rw"},
            {"name": "brightness", "desc": "亮度", "type": "int",
             "rw": "rw", "range": [1, 100, 1]},
          ]
        }, ...
      },
      "rooms": ["客厅", "餐厅", "阳台", "卧室1", "卧室2", "书房", "厕所1", "厕所2"],
      "devices": [                        # 每台设备引用型号并按房间摆放
        {"did": "v00001", "name": "客厅吸顶灯1", "model": "yeelink.light.ceiling1",
         "room": "客厅", "online": true, "state": {"on": true, "brightness": 80}},
        ...
      ],
      "scenes": []
    }
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from .models import (
    ActionInfo,
    DeviceDetail,
    DeviceInfo,
    PropInfo,
    QuickOpInfo,
)

logger = logging.getLogger(__name__)

# 读不到开关/读数的保守语义与真实实现一致：None = 无能力/未知
_BOOL_NAMES = ("on",)
_RANGE_PAD = (1, 100, 1)


class ServiceError(Exception):
    """与 app.core.service.ServiceError 同语义（避免强依赖导入链）。"""


def _norm_bool_prop(prop: dict) -> bool:
    """是否可作为开关（writable bool，name 为 on 或 on-*）。"""
    return (
        prop.get("type") == "bool"
        and "w" in str(prop.get("rw", ""))
        and (str(prop.get("name")) == "on"
             or str(prop.get("name", "")).replace("_", "-").startswith("on-"))
    )


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class MockMijiaService:
    """纯内存模拟的米家服务：接口面与 MijiaService 对 UI 暴露的一致。

    未继承真实实现（避免构造时触碰 mijiaAPI/认证/网络），所有方法
    都是自包含的离线模拟。
    """

    is_mock = True

    def __init__(self, pack: dict):
        self._home_name = str(pack.get("home", {}).get("name") or "虚拟测试家庭")
        self._models: dict[str, dict] = pack.get("models") or {}
        self._scenes: list[dict] = pack.get("scenes") or []
        self._devices: list[dict] = []
        # did -> (name, model, room, online, state)
        room_temp = {"客厅": 26.5, "餐厅": 26.0, "阳台": 29.5, "卧室1": 25.8,
                     "卧室2": 26.2, "书房": 25.5, "厕所1": 27.0, "厕所2": 27.0}
        room_hum = {"客厅": 55, "餐厅": 58, "阳台": 62, "卧室1": 52,
                    "卧室2": 50, "书房": 48, "厕所1": 66, "厕所2": 66}
        for dev in pack.get("devices") or []:
            did = str(dev["did"])
            model = str(dev.get("model") or "")
            room = str(dev.get("room") or "未知")
            spec = self._models.get(model) or {}
            state: dict[str, Any] = {}
            for prop in spec.get("props") or []:
                pname = prop["name"]
                ptype = prop.get("type")
                # 数值属性给合理默认值；状态里缺的值在读取时再兜底
                if pname == "on" and ptype == "bool":
                    state[pname] = bool(dev.get("state", {}).get("on", True))
            state.update({k: v for k, v in (dev.get("state") or {}).items()
                          if k in {p["name"] for p in spec.get("props") or []}})
            # 未播种的只读测量属性给贴近真实环境的读数，让卡片副标题
            # 与详情页在测试包里就有温湿度可看（数值确定性，不随机）
            base_t = room_temp.get(room, 26.0)
            base_h = room_hum.get(room, 55)
            for prop in spec.get("props") or []:
                pname = prop["name"]
                if pname in state:
                    continue
                if pname == "temperature":
                    # 体温计类显示体温，其余环境温度按房间基线
                    state[pname] = 36.5 if "temperature.h1" in model \
                        else round(base_t + (sum(map(ord, did)) % 5) * 0.1, 1)
                elif pname in ("relative-humidity", "humidity"):
                    state[pname] = float(base_h + (sum(map(ord, did)) % 7))
                elif pname in ("motion", "open", "alarm", "leak"):
                    state[pname] = False
                elif pname == "illuminance":
                    state[pname] = 320.0
                elif pname == "aqi":
                    state[pname] = 38
                elif pname == "power":
                    state[pname] = 0.0
                elif pname == "current-position":
                    state[pname] = 100
                elif pname == "battery":
                    state[pname] = 86
                elif ptype == "bool":
                    state[pname] = False
            self._devices.append({
                "did": did,
                "name": str(dev.get("name") or did),
                "model": model,
                "room": room,
                "online": bool(dev.get("online", True)),
                "state": state,
            })
        self._by_did = {d["did"]: d for d in self._devices}
        # 安全模式（MIWU_SAFE_DEVICE）与真实服务同语义：可选支持
        from . import safety as _safety
        self._guard = _safety.get_guard()

    # ---------- 登录 / 设备列表 ----------

    def login_status(self) -> bool:
        return True

    def list_devices(self) -> list[DeviceInfo]:
        result = [
            DeviceInfo(did=d["did"], name=d["name"], model=d["model"],
                       home_name=self._home_name, room_name=d["room"],
                       online=d["online"])
            for d in self._devices
        ]
        if self._guard.enabled:
            result = self._guard_filtered(result)
        return sorted(result, key=lambda x: (x.home_name, x.room_name, x.name))

    def _guard_filtered(self, items: list[DeviceInfo]) -> list[DeviceInfo]:
        """安全模式：只留匹配设备（did/名/型号含 needle），不触网。"""
        guard = self._guard
        if guard.did_exact is not None:
            return [it for it in items if it.did == guard.did_exact]
        allowed = {it.did for it in items
                   if guard.matches(it.did, it.name, it.model)}
        guard.set_allowed_dids(allowed)
        return [it for it in items if it.did in allowed]

    # ---------- 能力 / 详情 ----------

    def _spec_props(self, model: str) -> list[dict]:
        return list((self._models.get(model) or {}).get("props") or [])

    def model_has_published_functions(self, model: str) -> bool | None:
        """该型号在测试包里有可读/可写属性即视为有功能。"""
        props = self._spec_props(model)
        if not props:
            return False
        return any("r" in str(p.get("rw", "")) or "w" in str(p.get("rw", ""))
                   for p in props)

    def device_detail(self, did: str) -> DeviceDetail:
        dev = self._require(did)
        props = [
            PropInfo(name=p["name"], desc=str(p.get("desc") or p["name"]),
                     type=str(p.get("type") or "int"),
                     readable="r" in str(p.get("rw", "")),
                     writable="w" in str(p.get("rw", "")),
                     range=tuple(p["range"]) if p.get("range") else None,
                     value_list=p.get("value_list"))
            for p in self._spec_props(dev["model"])
        ]
        actions: list[ActionInfo] = []
        return DeviceDetail(did=did, name=dev["name"], model=dev["model"],
                            props=props, actions=actions)

    # ---------- 开关 ----------

    def _has_on(self, did: str) -> bool:
        dev = self._require(did)
        return any(_norm_bool_prop(p) for p in self._spec_props(dev["model"]))

    def power_state(self, did: str) -> bool | None:
        if not self._has_on(did):
            return None
        return bool(self._state_value(did, "on", True))

    def power_states(self, dids: list[str]) -> dict[str, bool | None]:
        return {did: self.power_state(did) for did in dids}

    def set_power_state(self, did: str, state: bool) -> None:
        self._assert_allowed(did)
        if not self._has_on(did):
            raise ServiceError("设备不支持开关控制")
        self._by_did[did]["state"]["on"] = bool(state)

    def toggle_power(self, did: str) -> bool:
        self._assert_allowed(did)
        current = self.power_state(did)
        if current is None:
            raise ServiceError("设备不支持开关控制或已离线")
        new_state = not current
        self.set_power_state(did, new_state)
        return new_state

    # ---------- 属性读写（详情工作台 / 快捷操作共用） ----------

    def read_prop(self, did: str, name: str):
        return self._state_value(did, name)

    def read_props(self, did: str, names: list[str]) -> dict[str, Any | None]:
        return {n: self._state_value(did, n) for n in names}

    def write_prop(self, did: str, name: str, value) -> None:
        self._assert_allowed(did)
        dev = self._require(did)
        spec = next((p for p in self._spec_props(dev["model"])
                     if p["name"] == name), None)
        if spec is None or "w" not in str(spec.get("rw", "")):
            raise ServiceError(f"设备不支持属性 {name}")
        dev["state"][name] = value

    def run_action(self, did: str, name: str, params=None) -> None:
        raise ServiceError(f"虚拟测试包未定义动作 {name}")

    def read_quick_values(self, did: str, names: list[str]) -> dict[str, Any | None]:
        return {n: self._state_value(did, n) for n in names}

    def write_quick_value(self, did: str, name: str, value: Any) -> None:
        self.write_prop(did, name, value)

    # ---------- 快捷操作候选（由测试包属性推导，与真实服务口径一致） ----------

    def quick_op_defs(self, did: str) -> list[QuickOpInfo]:
        return self.quick_op_candidates(did)

    def quick_op_candidates(self, did: str) -> list[QuickOpInfo]:
        dev = self._require(did)
        ops: list[QuickOpInfo] = []
        for p in self._spec_props(dev["model"]):
            if "w" not in str(p.get("rw", "")):
                continue
            if p.get("type") == "bool":
                continue  # 开关走电源钮，不进快捷调节
            rng = p.get("range")
            if rng and len(rng) >= 2:
                ops.append(QuickOpInfo(
                    name=p["name"], desc=str(p.get("desc") or p["name"]),
                    type=str(p.get("type") or "int"), kind="slider",
                    range=tuple(rng)))
            elif p.get("value_list"):
                ops.append(QuickOpInfo(
                    name=p["name"], desc=str(p.get("desc") or p["name"]),
                    type=str(p.get("type") or "int"), kind="enum",
                    value_list=p.get("value_list")))
        return ops

    # ---------- 环境读数（副标题温湿度） ----------

    def read_metrics(self, dids: list[str]) -> dict[str, str | None]:
        from .service import format_metrics_text
        result: dict[str, str | None] = {}
        for did in dids:
            dev = self._require(did)
            temp = hum = None
            for p in self._spec_props(dev["model"]):
                name = p["name"]
                if "r" not in str(p.get("rw", "")):
                    continue
                if name == "temperature" and temp is None:
                    temp = _as_float(self._state_value(did, name))
                elif name in ("relative-humidity", "humidity") and hum is None:
                    hum = _as_float(self._state_value(did, name))
            result[did] = format_metrics_text(temp, hum)
        return result

    # ---------- 本地化 / 产品图（虚拟包全部离线：直接空结果） ----------

    def localized_product_names(self, dids: list[str], names: dict[str, str]) -> dict[str, str]:
        return {}

    def has_product_page_name(self, model: str) -> bool:
        return False

    def product_page_name(self, model: str) -> str | None:
        return None

    def cached_product_page_names(self, models: list[str]) -> dict[str, str]:
        return {}

    def fetch_product_icon(self, model: str) -> bytes | None:
        return None

    def product_icon_url(self, model: str) -> str | None:
        return None

    # ---------- 场景 ----------

    def list_scenes(self) -> list:
        return []

    def run_scene(self, scene_id: str, home_id: str) -> None:
        raise ServiceError("虚拟测试包未定义场景")

    # ---------- 内部 ----------

    def _require(self, did: str) -> dict:
        dev = self._by_did.get(str(did))
        if dev is None:
            raise ServiceError(f"设备不存在或已移除: {did}")
        return dev

    def _state_value(self, did: str, name: str, default: Any = None) -> Any:
        dev = self._require(did)
        state = dev["state"]
        if name in state:
            return state[name]
        # 未显式播种的读取：按类型给保守默认，绝不抛异常
        spec = next((p for p in self._spec_props(dev["model"])
                     if p["name"] == name), None)
        if spec is None:
            return default
        if spec.get("type") == "bool":
            return bool(default)
        rng = spec.get("range") or _RANGE_PAD
        if len(rng) >= 3 and isinstance(rng[0], (int, float)) \
                and isinstance(rng[1], (int, float)):
            return rng[0] if default is None else default
        return default

    def _assert_allowed(self, did: str) -> None:
        if not self._guard.enabled:
            return
        if did in (self._guard.allowed_dids or set()):
            return
        raise ServiceError("安全模式已启用：该设备不在测试白名单内")


def load_mock_pack(path: str | Path) -> dict | None:
    """读取并校验虚拟测试包；损坏/缺失返回 None（由调用方决定回退）。"""
    p = Path(path)
    if not p.is_file():
        logger.warning("MIWU_MOCK_DEVICES 指向的文件不存在: %s", p)
        return None
    try:
        pack = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("虚拟测试包解析失败: %s", exc)
        return None
    if not isinstance(pack.get("devices"), list) or not pack["devices"]:
        logger.warning("虚拟测试包缺少 devices 列表")
        return None
    return pack


def create_service():
    """按环境变量构造服务：MIWU_MOCK_DEVICES=<json> 时返回模拟服务。

    供界面装配处调用（与 MijiaService 接口一致），未设置或包无效时
    回退真实米家服务。延迟 import 真实服务，避免本模块被先导入时
    产生循环依赖。
    """
    env = os.environ.get("MIWU_MOCK_DEVICES", "").strip()
    if env:
        pack = load_mock_pack(env)
        if pack is not None:
            logger.info("虚拟测试家庭模式：加载 %d 台模拟设备",
                        len(pack.get("devices") or []))
            return MockMijiaService(pack)
    from .service import MijiaService
    return MijiaService()
