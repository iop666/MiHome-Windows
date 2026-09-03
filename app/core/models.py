# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""界面层专用的数据模型。

刻意与 mijiaAPI 的原始 dict / 对象结构解耦：上游返回格式变化时只需调整
core.service 适配层，界面层永远只依赖这里的稳定类型。
"""

from dataclasses import dataclass


@dataclass
class DeviceInfo:
    """设备列表条目，只保留界面展示需要的最小字段集。"""

    did: str
    name: str
    model: str
    home_name: str
    room_name: str
    online: bool


@dataclass
class PropInfo:
    """单个属性的元数据，控件工厂据此决定生成哪种控件。

    range 来自米家 spec 的 valueRange；value_list 为枚举选项，
    每项含 value/description，可能附带 desc_zh_cn 中文描述。
    """

    name: str
    desc: str
    type: str  # bool / int / uint / float / string
    readable: bool
    writable: bool
    range: tuple | None = None  # (min, max, step)
    value_list: list | None = None


@dataclass
class ActionInfo:
    name: str
    desc: str


@dataclass
class DeviceDetail:
    """点击某台设备后加载的控制面板所需全部信息。"""

    did: str
    name: str
    model: str
    props: list[PropInfo]
    actions: list[ActionInfo]


@dataclass
class SceneInfo:
    """米家手动场景：主页「场景」入口列表与执行用。"""

    scene_id: str
    name: str
    home_id: str
    home_name: str


@dataclass
class QuickOpInfo:
    """设备卡片快捷操作的单个可调项（由 spec 推导，仅含能紧凑渲染的形态）。

    kind: "slider"（数值+range） / "enum"（value_list 枚举）
    """

    name: str
    desc: str
    type: str
    kind: str
    range: tuple | None = None
    value_list: list | None = None


@dataclass
class ActionArg:
    """动作的参数定义（来自 miot-spec 服务内 access=[] 的参数属性）。

    字段语义与 PropInfo 对齐；range/value_list 视型号而定可缺省。
    """

    name: str
    desc: str
    type: str  # bool / int / uint / float / string
    range: tuple | None = None
    value_list: list | None = None


def is_speaker(device: DeviceInfo) -> bool:
    """小爱音箱判定：音频控制栏、语音入口共用同一标准。

    用包含匹配而非限定 xiaomi 前缀，第三方音箱（模型含
    wifispeaker）同样具备音量/静音与文本指令能力。
    """
    return "wifispeaker" in device.model


# 数值属性的展示单位。米家 spec 未随属性下发 unit（上游解析丢弃），
# 详情/快捷调节的数值展示按属性名推导单位，命中即加后缀：
# 亮度 %、色温 K、温度 °C、湿度 %、功率 W 等。命名规律固定的
# 常见属性列在精确表，其余走稳妥的子串规则（宁可漏加不加错）。
_UNIT_BY_NAME: dict[str, str] = {
    "temperature": "°C",
    "target-temperature": "°C",
    "set-temperature": "°C",
    "room-temperature": "°C",
    "water-temperature": "°C",
    "relative-humidity": "%",
    "humidity": "%",
    "target-humidity": "%",
    "battery-level": "%",
    "brightness": "%",
    "color-temperature": "K",
    "colour-temperature": "K",
    "volume": "%",
    "sound-volume": "%",
    "power": "W",  # 数值型 power = 当前功率；布尔电源开关不走数值后缀
    "power-consumption": "W",
    "electric-power": "W",
    "light": "%",  # 数值型 light = 夜灯亮度类百分比档位
    "target-position": "%",  # 窗帘/晾衣杆等开合位置 0-100
    "illumination": "lx",
    "illuminance": "lx",
    "download-speed": "MB/s",
    "upload-speed": "MB/s",
    "rssi": "dBm",
    "online-time": "min",
    "work-minutes": "min",
    "break-minutes": "min",
    "work-countdown-sec": "s",
    "break-countdown-sec": "s",
    "delay-off-countdown": "s",
    "delay-time": "s",
    "countdown": "s",
}


def unit_suffix(name: str | None) -> str | None:
    """数值属性名 → 展示单位后缀；无可靠单位返回 None（不显示后缀）。"""
    if not name:
        return None
    key = str(name).strip().lower()
    exact = _UNIT_BY_NAME.get(key)
    if exact is not None:
        return exact
    # 子串兜底，只挑语义不会撞车的规则；色温必须先于“温度”判断
    if "color-temperature" in key or "colour-temperature" in key:
        return "K"
    if "temperature" in key:
        return "°C"
    if "brightness" in key:
        return "%"
    if "humidity" in key:
        return "%"
    if "illuminance" in key:
        return "lx"
    return None


def _has_cjk(text: str) -> bool:
    """是否含中文（标题/枚举里出现中文即视为已本地化）。"""
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


# 常见属性的中文标题。spec/测试包里的 desc 可能只有英文或干脆是属性名
# （如温湿度计的 temperature/humidity），详情/快捷调节的标题据此回退，
# 保证界面不出现英文裸名。设备特有、语义不确定的名字不在此列。
_PROP_TITLE_ZH: dict[str, str] = {
    "on": "开关",
    "mode": "模式",
    "brightness": "亮度",
    "color-temperature": "色温",
    "colour-temperature": "色温",
    "light": "灯光",
    "temperature": "温度",
    "target-temperature": "目标温度",
    "set-temperature": "设定温度",
    "room-temperature": "室温",
    "water-temperature": "水温",
    "humidity": "湿度",
    "relative-humidity": "湿度",
    "target-humidity": "目标湿度",
    "power": "功率",
    "power-consumption": "功率",
    "electric-power": "功率",
    "battery-level": "电量",
    "battery": "电量",
    "volume": "音量",
    "sound-volume": "音量",
    "mute": "静音",
    "fan-level": "档位",
    "target-position": "目标位置",
    "illuminance": "光照强度",
    "illumination": "光照强度",
    "leak": "漏水",
    "motion": "人体感应",
    "open": "开合",
    "alarm": "报警",
    "child-lock": "童锁",
    "lock": "童锁",
}


def prop_display_title(desc, name: str | None = None) -> str:
    """属性/动作的中文展示标题：双语取中文段，纯英文/裸名按属性名回退。

    命中《属性名→中文》表前必须确认原文没有中文——改名/自定义中文描述
    原样保留；翻译不了的名字保留原文，宁缺毋滥。
    """
    raw = str(desc or "").strip()
    # "Brightness / 亮度" 这类双语描述：优先取中文段
    if " / " in raw:
        parts = [part.strip() for part in raw.split("/")]
        zh_parts = [part for part in parts if _has_cjk(part)]
        if zh_parts:
            return zh_parts[-1]
        return parts[-1]
    if _has_cjk(raw):
        return raw
    if name:
        return _PROP_TITLE_ZH.get(str(name).strip().lower(), raw)
    return raw


# 常见枚举值英文 → 中文（枚举无中文描述时的保守回退）
_ENUM_ZH: dict[str, str] = {
    "auto": "自动",
    "manual": "手动",
    "on": "开启",
    "off": "关闭",
    "cool": "制冷",
    "cooling": "制冷",
    "heat": "制热",
    "heating": "制热",
    "dry": "除湿",
    "fan": "送风",
    "auto-mode": "自动",
    "sleep": "睡眠",
    "quiet": "静音",
    "silent": "静音",
    "standard": "标准",
    "normal": "标准",
    "medium": "中档",
    "mid": "中档",
    "high": "高档",
    "low": "低档",
    "boost": "强力",
    "turbo": "强力",
    "eco": "节能",
    "smart": "智能",
    "comfort": "舒适",
    "night": "夜间",
    "day": "日间",
    "unlock": "解锁",
    "lock": "锁定",
    "open": "开启",
    "close": "关闭",
}


def enum_option_text(item) -> str:
    """枚举项的展示文案：中文优先，纯英文按常见词表回退，否则保留原文。"""
    if isinstance(item, dict):
        zh = item.get("desc_zh_cn")
        if zh and _has_cjk(str(zh)):
            return str(zh)
        raw = item.get("description")
        if raw is None:
            raw = item.get("value")
    else:
        raw = item
    raw = str(raw if raw is not None else "").strip()
    if _has_cjk(raw):
        return raw
    key = raw.lower()
    if key in _ENUM_ZH:
        return _ENUM_ZH[key]
    first_word = key.split(" ")[0]
    if first_word in _ENUM_ZH:
        return _ENUM_ZH[first_word]
    return raw
