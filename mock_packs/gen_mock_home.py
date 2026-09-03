# SPDX-License-Identifier: GPL-3.0-or-later
# 生成虚拟测试家庭测试包：mock_packs/mock_home.json
#
# 用途：在无真实米家账号/网络下压测「设备很多 + 全屏布局」场景。
# 型号与设备类别参照米家生态（Yeelight/Aqara/米家/智米/石头/创米/云米等），
# 房间与摆放位置贴近真实家庭（客厅多灯与娱乐、阳台晾晒与洗衣机等）。
#
# 运行：.venv\Scripts\python.exe mock_packs\gen_mock_home.py
import json
import math
import random
from pathlib import Path

random.seed(20260903)

OUT = Path(__file__).resolve().parent / "mock_home.json"

HOME = "虚拟测试家庭"

# 房间与每间目标台数（合计 430）
ROOMS = [("客厅", 74), ("餐厅", 50), ("阳台", 46), ("卧室1", 66),
         ("卧室2", 60), ("书房", 54), ("厕所1", 42), ("厕所2", 38)]

# ---------------- 类别目录：中文短名 / 型号池 / 能力 spec ----------------

def _prop(name, desc, ptype="int", rw="rw", rng=None, vlist=None):
    p = {"name": name, "desc": desc, "type": ptype, "rw": rw}
    if rng:
        p["range"] = list(rng)
    if vlist is not None:
        p["value_list"] = vlist
    return p


def _light(cct=True):
    props = [_prop("on", "开关", "bool")]
    props.append(_prop("brightness", "亮度", rng=(1, 100, 1)))
    if cct:
        props.append(_prop("color-temperature", "色温", rng=(2700, 6500, 1)))
    return props


CAT = {
    # ---- 灯光（客厅主照明/氛围/阅读）----
    "ceiling": ("吸顶灯", ["yeelink.light.ceiling1", "yeelink.light.ceiling4",
                           "xiaomi.light.ceiling.01", "leshi.light.ceiling04"],
                _light(True)),
    "downlight": ("筒灯", ["yeelink.light.downlight3", "lumi.light.aqcn02"],
                  [_prop("on", "开关", "bool"),
                   _prop("brightness", "亮度", rng=(1, 100, 1))]),
    "strip": ("灯带", ["yeelink.light.strip1", "yeelink.light.strip6"],
              [_prop("on", "开关", "bool"),
               _prop("brightness", "亮度", rng=(1, 100, 1)),
               _prop("color-temperature", "色温", rng=(2700, 6500, 1))]),
    "bulb": ("灯泡", ["yeelink.light.color1", "yeelink.light.mono1",
                     "leshi.light.ceiling01"],
             _light(False)),
    "bedside": ("床头灯", ["yeelink.light.lamp2", "yeelink.light.bslamp2",
                          "leshi.light.bedside01"],
                _light(False)),
    "desk": ("台灯", ["xiaomi.light.lamp31", "yeelink.light.lamp4",
                     "philips.light.sread1", "mijia.light.lamp01"],
             _light(True)),
    "floor": ("落地灯", ["yeelink.light.floor1", "leshi.light.floor01"],
              _light(True)),
    # ---- 大家电 / 娱乐 ----
    "tv": ("电视", ["xiaomi.tv.mitv3", "xiaomi.tv.mitv5"],
           [_prop("on", "开关", "bool"),
            _prop("volume", "音量", rng=(0, 100, 1))]),
    "speaker": ("小爱音箱", ["xiaomi.wifispeaker.x08c", "xiaomi.wifispeaker.x10",
                            "xiaomi.wifispeaker.lx06", "xiaomi.wifispeaker.lx04",
                            "xiaomi.wifispeaker.mini1"],
                [_prop("on", "开关", "bool"),
                 _prop("volume", "音量", rng=(0, 100, 1)),
                 _prop("mute", "静音", "bool")]),
    "ac": ("空调", ["xiaomi.aircondition.c32", "xiaomi.aircondition.m16",
                   "xiaomi.aircondition.c20", "mijia.aircondition.v1"],
           [_prop("on", "开关", "bool"),
            _prop("mode", "模式", "int", vlist=[
                {"value": 1, "description": "制冷"}, {"value": 2, "description": "制热"},
                {"value": 3, "description": "自动"}, {"value": 0, "description": "除湿"},
                {"value": 4, "description": "送风"}]),
            _prop("target-temperature", "目标温度", rng=(16, 30, 1)),
            _prop("fan-level", "风速", "int", vlist=[
                {"value": 0, "description": "自动"}, {"value": 1, "description": "低"},
                {"value": 2, "description": "中"}, {"value": 3, "description": "高"}])]),
    "fridge": ("冰箱", ["midjd.fridge.bx27l", "midjd.fridge.bx24l"], []),
    "washer": ("洗衣机", ["midjd.washer.v1", "midjd.washer.pro"], []),
    "vacuum": ("扫地机器人", ["roborock.vacuum.a10", "roborock.vacuum.e2",
                             "rockrobo.vacuum.v1"],
               [_prop("on", "开关", "bool"),
                _prop("mode", "清扫模式", "int", vlist=[
                    {"value": 1, "description": "安静"}, {"value": 2, "description": "标准"},
                    {"value": 3, "description": "强力"}]),
                _prop("status", "状态", "int", rw="r",
                      vlist=[{"value": 1, "description": "待机"},
                             {"value": 2, "description": "清扫中"},
                             {"value": 3, "description": "回充"}]),
                _prop("battery", "电量", rw="r", rng=(0, 100, 1))]),
    "purifier": ("空气净化器", ["zhimi.airpurifier.m2", "zhimi.airpurifier.mb3",
                               "zhimi.airpurifier.mb1", "deerma.airpurifier.t9"],
                 [_prop("on", "开关", "bool"),
                  _prop("mode", "模式", "int", vlist=[
                      {"value": 0, "description": "自动"}, {"value": 1, "description": "睡眠"},
                      {"value": 2, "description": "手动"}]),
                  _prop("fan-level", "档位", rng=(1, 3, 1)),
                  _prop("aqi", "PM2.5", rw="r", rng=(0, 500, 1))]),
    "humidifier": ("加湿器", ["zhimi.humidifier.cb1", "deerma.humidifier.jsq1",
                              "smartmi.humidifier.1"],
                   [_prop("on", "开关", "bool"),
                    _prop("target-humidity", "目标湿度", rng=(30, 80, 1)),
                    _prop("mode", "模式", "int", vlist=[
                        {"value": 0, "description": "自动"}, {"value": 1, "description": "睡眠"},
                        {"value": 2, "description": "恒定"}]),
                    _prop("humidity", "当前湿度", rw="r", rng=(0, 100, 1))]),
    "dehumidifier": ("除湿机", ["zhimi.humidifier.de1"], [
        _prop("on", "开关", "bool"),
        _prop("target-humidity", "目标湿度", rng=(30, 70, 1))]),
    "heater": ("电暖器", ["zhimi.heater.za1", "smartmi.heater.1"], [
        _prop("on", "开关", "bool"),
        _prop("target-temperature", "目标温度", rng=(16, 30, 1)),
        _prop("mode", "模式", "int", vlist=[
            {"value": 0, "description": "自动"}, {"value": 1, "description": "低功率"},
            {"value": 2, "description": "高功率"}])]),
    "fan": ("电风扇", ["zhimi.fan.v2", "zhimi.fan.v3", "dmaker.fan.p5"],
            [_prop("on", "开关", "bool"),
             _prop("fan-level", "档位", rng=(1, 4, 1)),
             _prop("swing", "摇头", "bool")]),
    # ---- 网关 / 网络 / 控制 ----
    "gateway": ("智能网关", ["lumi.gateway.v3", "lumi.gateway.aqcn02"], [
        _prop("light", "夜灯亮度", rng=(1, 100, 1)),
        _prop("alarm", "报警开关", "bool"),
        _prop("status", "状态", "int", rw="r", vlist=[
            {"value": 1, "description": "在线"}, {"value": 2, "description": "离线"}])]),
    "router": ("路由器", ["xiaomi.router.ax6000", "xiaomi.router.ax3000"], []),
    "switch": ("智能开关", ["lumi.ctrl_ln1.aq1", "lumi.ctrl_ln2.aq1",
                           "lumi.ctrl_neutral1", "lumi.ctrl_neutral2"],
               [_prop("on", "开关", "bool"),
                _prop("mode", "模式", "int", vlist=[
                    {"value": 0, "description": "手动"}, {"value": 1, "description": "联动"}])]),
    "curtain": ("窗帘电机", ["lumi.curtain.hmcn1", "lumi.curtain.aq2"], [
        _prop("current-position", "当前位置", rw="r", rng=(0, 100, 1)),
        _prop("target-position", "目标位置", rng=(0, 100, 1)),
        _prop("status", "状态", "int", rw="r", vlist=[
            {"value": 0, "description": "停止"}, {"value": 1, "description": "运行中"}])]),
    "dryer": ("晾衣架", ["dmaker.dryer.s1"], [
        _prop("on", "开关", "bool"),
        _prop("mode", "模式", "int", vlist=[
            {"value": 0, "description": "上升"}, {"value": 1, "description": "下降"},
            {"value": 2, "description": "停止"}])]),
    # ---- 安全 / 传感 / 影音 ----
    "camera": ("摄像机", ["chuangmi.camera.069a01", "chuangmi.camera.ipc009",
                         "chuangmi.camera.018b01"], []),
    "doorbell": ("智能门铃", ["chuangmi.doorbell.v2", "chuangmi.doorbell.m20"], []),
    "lock": ("智能门锁", ["loock.lock.v5", "lumi.lock.aq1", "mijia.lock.m20"], []),
    "sensor_ht": ("温湿度计", ["miaomiaoce.sensor_ht.t2", "miaomiaoce.sensor_ht.t1",
                              "lumi.sensor_ht.v3"],
                  [_prop("temperature", "温度", "float", rw="r"),
                   _prop("relative-humidity", "湿度", "float", rw="r")]),
    "sensor_motion": ("人体传感器", ["lumi.sensor_motion.v2", "lumi.sensor_motion.aq2",
                                    "lumi.motion.ac01"],
                      [_prop("motion", "有人移动", "bool", rw="r"),
                       _prop("illuminance", "光照度", "int", rw="r", rng=(0, 1200, 1))]),
    "sensor_door": ("门窗传感器", ["lumi.sensor_magnet.v2", "lumi.sensor_magnet.aq2"],
                    [_prop("open", "门已打开", "bool", rw="r")]),
    "sensor_smoke": ("烟雾传感器", ["lumi.sensor_smoke.v2", "lumi.sensor_smoke.ac01"],
                     [_prop("alarm", "烟雾报警", "bool", rw="r")]),
    "sensor_gas": ("燃气传感器", ["lumi.sensor_natgas.v2", "lumi.sensor_natgas.ac01"],
                   [_prop("alarm", "燃气报警", "bool", rw="r")]),
    "sensor_water": ("水浸传感器", ["lumi.sensor_wleak.aq1"],
                     [_prop("leak", "浸水", "bool", rw="r")]),
    "sensor_light": ("光照传感器", ["lumi.sensor_light.aqcn02"],
                     [_prop("illuminance", "光照度", "int", rw="r", rng=(0, 120000, 1))]),
    "sensor_bodytemp": ("体温计", ["miaomiaoce.temperature.h1"],
                        [_prop("temperature", "体温", "float", rw="r")]),
    # ---- 阳台 / 卫浴 ----
    "towel_rack": ("智能浴霸", ["dmaker.bathroom.1", "yeelink.bhf_light.1"], [
        _prop("on", "开关", "bool"),
        _prop("mode", "模式", "int", vlist=[
            {"value": 1, "description": "取暖"}, {"value": 2, "description": "吹风"},
            {"value": 3, "description": "换气"}, {"value": 4, "description": "干燥"},
            {"value": 5, "description": "照明"}])]),
    "exhaust": ("排风扇", ["dmaker.bathroom.heater"], [
        _prop("on", "开关", "bool")]),
    "toilet": ("智能马桶", ["madefree.toilet.n1", "hinote.toilet.pro"], []),
    "water_heater": ("燃气热水器", ["midjd.waterheater.v1"], [
        _prop("on", "开关", "bool"),
        _prop("target-temperature", "目标温度", rng=(30, 65, 1))]),
    "plug": ("智能插座", ["chuangmi.plug.v3", "chuangmi.plug.m3", "qmi.plug.psv3",
                         "cuco.plug.v3"],
             [_prop("on", "开关", "bool"),
              _prop("power", "功率", "float", rw="r")]),
    "powerstrip": ("智能排插", ["zimi.powerstrip.v2", "zimi.powerstrip.4a"], [
        _prop("on", "开关", "bool"),
        _prop("power", "功率", "float", rw="r")]),
    "ir": ("万能遥控器", ["chuangmi.ir.v2"], []),
}

# 真实室温/湿度基线（按房间），用于传感器种子值
ROOM_CLIMATE = {"客厅": (26.5, 55), "餐厅": (26.0, 58), "阳台": (29.5, 62),
                "卧室1": (25.8, 52), "卧室2": (26.2, 50), "书房": (25.5, 48),
                "厕所1": (27.0, 66), "厕所2": (27.0, 66)}

# 每类设备的数量配方（客厅多灯/插座的密集家庭，厕所少）
RECIPE = {
    "客厅": [("ceiling", 3), ("downlight", 12), ("strip", 1), ("bulb", 4),
             ("floor", 1), ("tv", 1), ("speaker", 3), ("ac", 2), ("gateway", 2),
             ("curtain", 1), ("purifier", 2), ("humidifier", 1), ("vacuum", 1),
             ("camera", 2), ("plug", 8), ("powerstrip", 2), ("switch", 4),
             ("fan", 1), ("sensor_ht", 3), ("sensor_motion", 4),
             ("sensor_door", 1), ("sensor_smoke", 1), ("sensor_light", 1),
             ("router", 1), ("doorbell", 1), ("ir", 1)],
    "餐厅": [("ceiling", 2), ("downlight", 6), ("bulb", 3), ("ac", 1),
             ("fridge", 1), ("plug", 6), ("powerstrip", 1), ("switch", 2),
             ("sensor_ht", 1), ("sensor_motion", 1), ("sensor_door", 1),
             ("sensor_smoke", 1), ("sensor_gas", 1), ("purifier", 1),
             ("speaker", 1)],
    "阳台": [("ceiling", 1), ("downlight", 3), ("dryer", 1), ("washer", 1),
             ("camera", 1), ("plug", 5), ("sensor_ht", 1), ("sensor_door", 1),
             ("sensor_motion", 1), ("sensor_water", 1), ("curtain", 1),
             ("vacuum", 1), ("purifier", 1)],
    "卧室1": [("ceiling", 1), ("bedside", 2), ("desk", 2), ("downlight", 5),
              ("bulb", 2), ("ac", 1), ("purifier", 1), ("humidifier", 1),
              ("speaker", 2), ("switch", 2), ("curtain", 1), ("plug", 5),
              ("powerstrip", 1), ("sensor_ht", 2), ("sensor_motion", 1),
              ("sensor_door", 1), ("camera", 1), ("lock", 1)],
    "卧室2": [("ceiling", 1), ("bedside", 1), ("desk", 1), ("downlight", 4),
              ("bulb", 1), ("ac", 1), ("purifier", 1), ("fan", 1),
              ("speaker", 1), ("switch", 1), ("curtain", 1), ("plug", 4),
              ("sensor_ht", 1), ("sensor_motion", 1), ("sensor_door", 1),
              ("sensor_bodytemp", 1), ("gateway", 1)],
    "书房": [("ceiling", 1), ("desk", 2), ("downlight", 3), ("strip", 1),
             ("bulb", 1), ("ac", 1), ("purifier", 1), ("dehumidifier", 1),
             ("plug", 5), ("powerstrip", 1), ("switch", 2), ("router", 1),
             ("speaker", 1), ("curtain", 1), ("sensor_ht", 1),
             ("sensor_motion", 1), ("sensor_door", 1), ("sensor_light", 1),
             ("camera", 1)],
    "厕所1": [("ceiling", 1), ("downlight", 2), ("towel_rack", 1),
              ("exhaust", 1), ("toilet", 1), ("water_heater", 1), ("plug", 2),
              ("switch", 1), ("sensor_ht", 1), ("sensor_motion", 1),
              ("sensor_water", 1), ("sensor_bodytemp", 1)],
    "厕所2": [("ceiling", 1), ("downlight", 2), ("towel_rack", 1),
              ("exhaust", 1), ("toilet", 1), ("plug", 2), ("switch", 1),
              ("sensor_ht", 1), ("sensor_motion", 1), ("sensor_water", 1)],
}

FILLERS = ["downlight", "plug", "bulb", "sensor_motion", "switch", "sensor_ht"]
# 少量离线设备（模拟个别设备掉线时的灰置样式）
ONLINE_HIT = 29


def _default_state(cat_key, model, room, index):
    """按类别/房间给出合理默认状态（真实使用时的常见取值）。"""
    base_t, base_h = ROOM_CLIMATE.get(room, (25.0, 55))
    noise = lambda spread: round(random.uniform(-spread, spread), 1)  # noqa: E731
    props = CAT[cat_key][2]
    state = {}
    for p in props:
        name, ptype, rw = p["name"], p["type"], p["rw"]
        if "w" not in rw:
            continue
        if ptype == "bool":
            state[name] = index % 7 != 0 if name in ("on",) else index % 3 == 0
        elif ptype in ("int", "uint", "float"):
            rng = p.get("range") or (0, 100, 1)
            lo, hi = rng[0], rng[1]
            if name == "brightness":
                state[name] = 40 + (index * 7) % 60
            elif name == "color-temperature":
                state[name] = 3000 + (index * 130) % 2000
            elif name == "target-temperature":
                state[name] = 24 + (index % 5)
            elif name == "target-humidity":
                state[name] = 50 + (index % 20)
            elif name in ("fan-level",):
                state[name] = 1 + (index % 3)
            elif name == "volume":
                state[name] = 15 + (index % 40)
            elif name == "power":
                state[name] = round(2 + (index % 9) * 13.7, 1)
            else:
                state[name] = min(hi, max(lo, lo + (index * (hi - lo)) // 7))
        elif p.get("value_list"):
            vals = [v["value"] for v in p["value_list"]]
            state[name] = vals[index % len(vals)]
    return state


def _gen():
    models: dict[str, dict] = {}
    for key, (zh, model_list, props) in CAT.items():
        for m in model_list:
            models.setdefault(m, {"name": zh, "props": props})
    devices = []
    counter = 0
    for room, target in ROOMS:
        room_list = []
        for key, cnt in RECIPE.get(room, []):
            zh, model_list, _ = CAT[key]
            for j in range(cnt):
                counter += 1
                model = model_list[j % len(model_list)]
                did = f"v{counter:05d}"
                label = f"{room}{zh}" + (f"{j + 1}" if cnt > 1 else "")
                online = counter % ONLINE_HIT != 0  # 每隔若干台模拟一台离线
                state = _default_state(key, model, room, counter)
                room_list.append({"did": did, "name": label, "model": model,
                                  "room": room, "online": online,
                                  "state": state})
        # 不足目标台数时用密集家庭常见的设备类型补齐（灯/插座/人体/湿度计）
        fi = 0
        while len(room_list) < target:
            counter += 1
            key = FILLERS[fi % len(FILLERS)]
            fi += 1
            zh, model_list, _ = CAT[key]
            model = model_list[(fi + len(room_list)) % len(model_list)]
            did = f"v{counter:05d}"
            label = f"{room}{zh}{len(room_list) + 1}"
            online = counter % ONLINE_HIT != 0
            state = _default_state(key, model, room, counter)
            room_list.append({"did": did, "name": label, "model": model,
                              "room": room, "online": online,
                              "state": state})
        devices.extend(room_list)
    return {
        "home": {"name": HOME},
        "models": models,
        "rooms": [r for r, _ in ROOMS],
        "devices": devices,
        "scenes": [],
    }


def main():
    pack = _gen()
    by_room = {}
    for d in pack["devices"]:
        by_room[d["room"]] = by_room.get(d["room"], 0) + 1
    total = len(pack["devices"])
    print("rooms:", by_room)
    print("total devices:", total)
    assert total >= 400, f"设备数不足: {total}"
    assert set(pack["rooms"]) == set(by_room), "存在未分配房间的设备"
    OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("written:", OUT, round(OUT.stat().st_size / 1024, 1), "KB")


if __name__ == "__main__":
    main()
