# SPDX-License-Identifier: GPL-3.0-or-later
# 用米家百科真实目录生成虚拟测试家庭：mock_packs/mock_home.json
#
# 产品来源：mock_packs/baike_catalog.json（由 scrape_baike.py 抓取，
# 10239 个真实产品，含 name/model/brand/realIcon）。
# 配比：米家/小米出品约 60%，第三方品牌（Yeelight/Aqara/飞利浦/公牛/
# 杜亚/云米/追觅等）约 40%；房间与摆放贴近真实家庭生活场景。
#
# 运行：.venv\Scripts\python.exe mock_packs\gen_mock_home.py
import json
import math
import random
from pathlib import Path

random.seed(20260903)

HERE = Path(__file__).resolve().parent
OUT = HERE / "mock_home.json"
CATALOG = HERE / "baike_catalog.json"

HOME = "虚拟测试家庭"
ROOMS = [("客厅", 74), ("餐厅", 50), ("阳台", 46), ("卧室1", 66),
         ("卧室2", 60), ("书房", 54), ("厕所1", 42), ("厕所2", 38)]

# ---------- 品牌：米家/小米出品 = 60%，第三方 = 40% ----------
FAMILY_BRANDS = {"小米出品", "米家", "小米", "小米生态链"}
# 品牌名里含小米/米家也归米家系（少数条目品牌字段写法不同）

CLIMATE = {"客厅": (26.5, 55), "餐厅": (26.0, 58), "阳台": (29.5, 62),
           "卧室1": (25.8, 52), "卧室2": (26.2, 50), "书房": (25.5, 48),
           "厕所1": (27.0, 66), "厕所2": (27.0, 66)}

# ---------- 语义模板：中文类型名 / 能力 spec / 名称匹配关键词 ----------
# 每类设备的能力 spec 按语义建模（UI 测试用），产品名与型号取自百科。


def _prop(name, desc, ptype="int", rw="rw", rng=None, vlist=None):
    p = {"name": name, "desc": desc, "type": ptype, "rw": rw}
    if rng:
        p["range"] = list(rng)
    if vlist is not None:
        p["value_list"] = vlist
    return p


def _light(cct=True):
    props = [_prop("on", "开关", "bool"), _prop("brightness", "亮度", rng=(1, 100, 1))]
    if cct:
        props.append(_prop("color-temperature", "色温", rng=(2700, 6500, 1)))
    return props


def _sensor(*names):
    return [_prop(n, n, "float", rw="r") if n in ("temperature", "humidity")
            else _prop(n, n, "bool", rw="r") for n in names]


CAT = {
    "ceiling": ("吸顶灯", _light(True), ["吸顶"]),
    "downlight": ("筒灯", [_prop("on", "开关", "bool"),
                          _prop("brightness", "亮度", rng=(1, 100, 1))], ["筒灯"]),
    "strip": ("灯带", _light(True), ["灯带"]),
    "bulb": ("灯泡", _light(False), ["灯泡", "彩光"]),
    "bedside": ("床头灯", _light(False), ["床头"]),
    "desk": ("台灯", _light(True), ["台灯"]),
    "floor": ("落地灯", _light(True), ["落地"]),
    "ceiling_fan": ("吊扇灯", _light(False), ["吊扇"]),
    "tv": ("电视", [_prop("on", "开关", "bool"),
                   _prop("volume", "音量", rng=(0, 100, 1))], ["电视"]),
    "speaker": ("小爱音箱", [_prop("on", "开关", "bool"),
                            _prop("volume", "音量", rng=(0, 100, 1)),
                            _prop("mute", "静音", "bool")], ["音箱", "音响"]),
    "ac": ("空调", [_prop("on", "开关", "bool"),
                   _prop("mode", "模式", "int", vlist=[
                       {"value": 1, "description": "制冷"},
                       {"value": 2, "description": "制热"},
                       {"value": 3, "description": "自动"}]),
                   _prop("target-temperature", "目标温度", rng=(16, 30, 1))],
           ["空调", "风管机"]),
    "fridge": ("冰箱", [], ["冰箱"]),
    "washer": ("洗衣机", [], ["洗衣机"]),
    "vacuum": ("扫地机器人", [_prop("on", "开关", "bool"),
                             _prop("mode", "模式", "int", vlist=[
                                 {"value": 1, "description": "安静"},
                                 {"value": 2, "description": "标准"},
                                 {"value": 3, "description": "强力"}])],
               ["扫地", "扫拖"]),
    "washer_robot": ("洗地机", [_prop("on", "开关", "bool"),
                               _prop("mode", "模式", "int", vlist=[
                                   {"value": 0, "description": "自动"},
                                   {"value": 1, "description": "吸水"},
                                   {"value": 2, "description": "除菌"}])],
                     ["洗地"]),
    "purifier": ("空气净化器", [_prop("on", "开关", "bool"),
                               _prop("mode", "模式", "int", vlist=[
                                   {"value": 0, "description": "自动"},
                                   {"value": 1, "description": "睡眠"},
                                   {"value": 2, "description": "手动"}])],
                 ["净化"]),
    "humidifier": ("加湿器", [_prop("on", "开关", "bool"),
                              _prop("target-humidity", "目标湿度", rng=(30, 80, 1))],
                   ["加湿"]),
    "dehumidifier": ("除湿机", [_prop("on", "开关", "bool"),
                                _prop("target-humidity", "目标湿度", rng=(30, 70, 1))],
                     ["除湿"]),
    "heater": ("取暖器", [_prop("on", "开关", "bool"),
                         _prop("target-temperature", "目标温度", rng=(16, 30, 1))],
               ["取暖", "电暖", "暖风机"]),
    "fan": ("电风扇", [_prop("on", "开关", "bool"),
                      _prop("fan-level", "档位", rng=(1, 4, 1))], ["风扇"]),
    "gateway": ("智能网关", [_prop("light", "夜灯亮度", rng=(1, 100, 1))],
                ["网关", "中枢"]),
    "router": ("路由器", [], ["路由"]),
    "switch": ("智能开关", [_prop("on", "开关", "bool")], ["开关"]),
    "curtain": ("窗帘电机", [_prop("target-position", "目标位置", rng=(0, 100, 1))],
                ["窗帘"]),
    "dryer": ("晾衣架", [_prop("on", "开关", "bool"),
                        _prop("mode", "模式", "int", vlist=[
                            {"value": 0, "description": "上升"},
                            {"value": 1, "description": "下降"},
                            {"value": 2, "description": "风干"}])], ["晾衣"]),
    "camera": ("摄像机", [], ["摄像", "看护", "监控"]),
    "doorbell": ("智能门铃", [], ["门铃", "猫眼"]),
    "lock": ("智能门锁", [], ["门锁", "指纹"]),
    "sensor_ht": ("温湿度计", _sensor("temperature", "humidity"), ["温湿"]),
    "sensor_motion": ("人体传感器", _sensor("motion"), ["人体"]),
    "sensor_door": ("门窗传感器", _sensor("open"), ["门窗", "门磁"]),
    "sensor_smoke": ("烟雾传感器", _sensor("alarm"), ["烟雾"]),
    "sensor_gas": ("燃气传感器", _sensor("alarm"), ["燃气", "气感"]),
    "sensor_water": ("水浸传感器", _sensor("leak"), ["水浸", "漏水"]),
    "sensor_light": ("光照传感器", _sensor("illuminance"), ["光照", "照度"]),
    "sensor_bodytemp": ("体温计", _sensor("temperature"), ["体温"]),
    "towel_rack": ("智能浴霸", [_prop("on", "开关", "bool"),
                                _prop("mode", "模式", "int", vlist=[
                                    {"value": 1, "description": "取暖"},
                                    {"value": 2, "description": "吹风"},
                                    {"value": 3, "description": "换气"}])],
                   ["浴霸"]),
    "exhaust": ("换气扇", [_prop("on", "开关", "bool")], ["换气", "排气"]),
    "toilet": ("智能马桶", [], ["马桶"]),
    "water_heater": ("热水器", [_prop("on", "开关", "bool"),
                               _prop("target-temperature", "目标温度", rng=(30, 65, 1))],
                     ["热水器"]),
    "plug": ("智能插座", [_prop("on", "开关", "bool"),
                         _prop("power", "功率", "float", rw="r")], ["插座"]),
    "powerstrip": ("智能排插", [_prop("on", "开关", "bool")], ["排插", "插排"]),
    "ir": ("万能遥控器", [], ["遥控"]),
    "rice_cooker": ("电饭煲", [_prop("on", "开关", "bool")], ["饭煲", "电饭"]),
    "kettle": ("电水壶", [_prop("on", "开关", "bool")], ["水壶", "电热壶"]),
    "water_purifier": ("净水器", [_prop("on", "开关", "bool")], ["净水"]),
    "water_dispenser": ("饮水机", [_prop("on", "开关", "bool")], ["饮水"]),
    "coffee": ("咖啡机", [_prop("on", "开关", "bool")], ["咖啡"]),
    "cooker": ("空气炸锅/烤箱", [_prop("on", "开关", "bool")], ["烤箱", "炸锅"]),
    "blender": ("破壁机", [_prop("on", "开关", "bool")], ["破壁", "豆浆"]),
    "microwave": ("微波炉", [_prop("on", "开关", "bool")], ["微波"]),
    "hood": ("油烟机", [_prop("on", "开关", "bool")], ["油烟"]),
    "fryer": ("电磁炉", [_prop("on", "开关", "bool")], ["电磁炉", "电陶炉"]),
    "air_fryer": ("厨房料理", [_prop("on", "开关", "bool")], ["料理", "厨师机"]),
    "scale": ("体脂秤", [], ["体脂", "体重"]),
    "blood_pressure": ("血压计", [], ["血压"]),
    "massage": ("按摩椅", [_prop("on", "开关", "bool")], ["按摩"]),
    "hair_dryer": ("吹风机", [_prop("on", "开关", "bool")], ["吹风"]),
    "toothbrush": ("电动牙刷", [], ["牙刷"]),
    "blanket": ("电热毯/床垫", [_prop("on", "开关", "bool"),
                                _prop("target-temperature", "目标温度", rng=(20, 45, 1))],
                ["床垫", "电热毯", "智能床"]),
    "aroma": ("香薰机", [_prop("on", "开关", "bool")], ["香薰", "香氛"]),
    "pet": ("宠物喂食/饮水", [_prop("on", "开关", "bool")], ["喂食", "宠物"]),
    "plant": ("植物/浇灌", [_prop("on", "开关", "bool")], ["浇灌", "植物"]),
    "projector": ("投影", [_prop("on", "开关", "bool")], ["投影"]),
    "curtain2": ("电动窗帘", [], ["窗帘"]),
}

# 每房间配方（key, count）；count 超出目标会被裁剪，不足会补灯/插座等
RECIPE = {
    "客厅": [("ceiling", 3), ("downlight", 8), ("strip", 1), ("bulb", 3),
             ("floor", 1), ("tv", 1), ("projector", 1), ("speaker", 2),
             ("ac", 2), ("gateway", 2), ("curtain", 1), ("purifier", 2),
             ("humidifier", 1), ("vacuum", 2), ("washer_robot", 1),
             ("camera", 2), ("plug", 8), ("powerstrip", 2), ("switch", 4),
             ("fan", 1), ("ir", 1), ("router", 1), ("doorbell", 1),
             ("lock", 1), ("sensor_ht", 2), ("sensor_motion", 3),
             ("sensor_door", 1), ("sensor_smoke", 1), ("sensor_light", 1),
             ("pet", 1), ("blanket", 1), ("scale", 1), ("massage", 1)],
    "餐厅": [("ceiling", 2), ("downlight", 4), ("bulb", 2), ("ac", 1),
             ("fridge", 1), ("rice_cooker", 1), ("kettle", 1),
             ("water_purifier", 1), ("water_dispenser", 1), ("coffee", 1),
             ("cooker", 1), ("blender", 1), ("microwave", 1),
             ("hood", 1), ("fryer", 1), ("plug", 5), ("powerstrip", 1),
             ("switch", 2), ("sensor_ht", 1), ("sensor_motion", 1),
             ("sensor_gas", 1), ("sensor_smoke", 1), ("purifier", 1),
             ("speaker", 1), ("curtain", 1)],
    "阳台": [("ceiling", 1), ("downlight", 3), ("dryer", 1), ("washer", 1),
             ("camera", 1), ("plug", 4), ("sensor_ht", 1),
             ("sensor_door", 1), ("sensor_motion", 1), ("sensor_water", 1),
             ("curtain", 1), ("vacuum", 1), ("purifier", 1), ("plant", 1),
             ("washer_robot", 1)],
    "卧室1": [("ceiling", 1), ("bedside", 2), ("desk", 1), ("downlight", 4),
              ("bulb", 1), ("ac", 1), ("purifier", 1), ("humidifier", 1),
              ("speaker", 2), ("switch", 2), ("curtain", 1), ("plug", 4),
              ("powerstrip", 1), ("sensor_ht", 2), ("sensor_motion", 1),
              ("sensor_door", 1), ("camera", 1), ("lock", 1), ("blanket", 1),
              ("aroma", 1), ("scale", 1), ("blood_pressure", 1),
              ("hair_dryer", 1), ("toothbrush", 1)],
    "卧室2": [("ceiling", 1), ("bedside", 1), ("desk", 1), ("downlight", 3),
              ("bulb", 1), ("ac", 1), ("purifier", 1), ("fan", 1),
              ("speaker", 1), ("switch", 1), ("curtain", 1), ("plug", 3),
              ("sensor_ht", 1), ("sensor_motion", 1), ("sensor_door", 1),
              ("sensor_bodytemp", 1), ("gateway", 1), ("toothbrush", 1),
              ("aroma", 1), ("desk_light", 0)],
    "书房": [("ceiling", 1), ("desk", 2), ("downlight", 2), ("strip", 1),
             ("ac", 1), ("purifier", 1), ("dehumidifier", 1), ("plug", 4),
             ("powerstrip", 1), ("switch", 2), ("router", 1),
             ("speaker", 1), ("curtain", 1), ("sensor_ht", 1),
             ("sensor_motion", 1), ("sensor_door", 1), ("sensor_light", 1),
             ("camera", 1), ("blanket", 0)],
    "厕所1": [("ceiling", 1), ("downlight", 2), ("towel_rack", 1),
              ("exhaust", 1), ("toilet", 1), ("water_heater", 1),
              ("plug", 2), ("switch", 1), ("sensor_ht", 1),
              ("sensor_motion", 1), ("sensor_water", 2), ("hair_dryer", 1)],
    "厕所2": [("ceiling", 1), ("downlight", 2), ("towel_rack", 1),
              ("exhaust", 1), ("toilet", 1), ("plug", 2), ("switch", 1),
              ("sensor_ht", 1), ("sensor_motion", 1), ("sensor_water", 1)],
}

FILLERS = ["plug", "downlight", "bulb", "sensor_motion", "switch", "sensor_ht"]
ONLINE_HIT = 29  # 每 29 台造 1 台离线


def _is_family(brand: str) -> bool:
    b = (brand or "").strip()
    return b in FAMILY_BRANDS or "小米" in b or "米家" in b or b.lower() in (
        "mi", "mijia", "xiaomi")


def main():
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))
    # 按语义关键词建索引：keyword -> [product...]（每个 product 含 model/name/brand/realIcon）
    idx: dict[str, list[dict]] = {}
    for kw_set in {k for _, _, m in CAT.values() for k in m}:
        idx[kw_set] = []
    # 传感器类关键词：目录里“照明/灯”产品名常含“光照/照度/夜灯”等
    # 子串（如“光照明”），必须靠类别/词形过滤，避免把吸顶灯当传感器
    _SENSOR_SOFT = {"光照", "照度", "温湿", "人体", "门窗", "门磁", "烟雾",
                    "燃气", "水浸", "漏水", "体温"}

    def _sensor_row_ok(kw: str, nm: str, cat: str) -> bool:
        if cat in ("传感器", "安防"):
            return True
        if "传感" in nm or "报警" in nm or "泄漏" in nm or "漏水" in nm \
                or "水浸" in nm or "检测" in nm:
            return ("灯" not in nm) and ("照明" not in nm)
        if kw in ("温湿", "体温") and ("计" in nm or "仪" in nm):
            return True
        return False

    for r in rows:
        nm = r.get("name") or ""
        cat = r.get("category") or ""
        for kw, lst in idx.items():
            if kw not in nm:
                continue
            if kw in _SENSOR_SOFT and not _sensor_row_ok(kw, nm, cat):
                continue
            lst.append(r)
    for kw, lst in idx.items():
        # 每个关键词池内去重（同型号多类别条目只留一个），保证图标可用
        seen = {}
        for r in lst:
            seen.setdefault(r["model"], r)
        idx[kw] = list(seen.values())

    family_count = 0
    other_count = 0
    devices = []
    models_out: dict[str, dict] = {}
    icons_out: dict[str, str] = {}
    counter = 0
    name_used: dict[str, int] = {}

    def take(cat_key, room, j):
        """从目录为某语义槽取一台产品；尽量维持米家系 60%。"""
        nonlocal family_count, other_count, counter, models_out, icons_out
        zh, props, kws = CAT[cat_key]
        # 品牌桶目标：已用总数里米家不足 60% 时优先选米家
        total = family_count + other_count
        prefer_family = (total == 0) or (family_count / total < 0.6)
        buckets = ["family" if prefer_family else "other",
                   "other" if prefer_family else "family",
                   "all"]
        for bucket in buckets:
            pool = []
            for kw in kws:
                for r in idx.get(kw, []):
                    if bucket == "all" or (bucket == "family") == _is_family(r.get("brand")):
                        pool.append(r)
            if pool:
                # 优先取名称含主关键词（第一个关键词）的产品，保证语义槽
                # 的代表品类稳定出现（如“电视”槽不会全被“投影”占掉）
                main_pool = [r for r in pool if kws[0] in (r.get("name") or "")]
                pick_pool = main_pool or pool
                # 同一真实型号可能在目录里跨品类重复出现（例如某吸顶灯
                # 型号同时挂在“照明”与别处）；若该型号已被其它语义槽用
                # 过（模板不一致会污染两台设备的 spec），顺延挑下一个
                picked = None
                for k in range(len(pick_pool)):
                    cand = pick_pool[(counter + k) % len(pick_pool)]
                    cmodel = cand["model"]
                    if cmodel in models_out and \
                            models_out[cmodel]["props"] is not props:
                        continue
                    picked = cand
                    break
                if picked is None:
                    picked = pick_pool[counter % len(pick_pool)]
                r = picked
                model = r["model"]
                counter += 1
                brand = r.get("brand") or ""
                if _is_family(brand):
                    family_count += 1
                else:
                    other_count += 1
                models_out.setdefault(model, {"name": r["name"] or zh,
                                              "props": props})
                if r.get("realIcon"):
                    icons_out[model] = r["realIcon"]
                return model, (r["name"] or zh).strip(), brand
        # 极端情况：目录缺词（几乎不会），退回语义名
        counter += 1
        family_count += 1
        return f"mock.{zh}.{counter:03d}", zh, "小米出品"

    for room, target in ROOMS:
        plan = [k for k, c in RECIPE.get(room, []) for _ in range(c)]
        # 超出目标则优先裁掉出现最多的项，保留多样性
        while len(plan) > target:
            from collections import Counter as _C
            most = _C(plan).most_common(1)[0][0]
            plan.remove(most)
        fi = 0
        while len(plan) < target:
            plan.append(FILLERS[fi % len(FILLERS)])
            fi += 1
        room_list = []
        j_map = {}
        for key in plan:
            j = j_map.get(key, 0) + 1
            j_map[key] = j
            model, pname, brand = take(key, room, j)
            # 注意：devices 在整间房结束后才 extend，须加上本房已建的
            # room_list 长度，否则同房内所有设备会拿到同一个 did
            did = f"v{len(devices) + len(room_list) + 1:05d}"
            zh = CAT[key][0]
            base = f"{room}·{pname}"
            cnt = name_used.get(base, 0)
            name_used[base] = cnt + 1
            name = base if cnt == 0 else f"{base} {cnt + 1}"
            online = (len(devices) + len(room_list) + 1) % ONLINE_HIT != 0
            room_list.append({"did": did, "name": name, "model": model,
                              "room": room, "online": online,
                              "props": CAT[key][1], "state": {}})
        devices.extend(room_list)

    # 状态种子：沿用默认（写入 json 让 mock 读取直观）
    for i, d in enumerate(devices):
        # 开关多为开，亮度/色温按序号给值
        d["state"]["on"] = i % 7 != 0
        d["state"]["brightness"] = 40 + (i * 7) % 60
        d["state"]["color-temperature"] = 3000 + (i * 130) % 2000
        d["state"]["target-temperature"] = 24 + (i % 5)
        d["state"]["target-humidity"] = 50 + (i % 20)
        d["state"]["volume"] = 20 + (i % 40)

    pack = {
        "home": {"name": HOME},
        "models": models_out,
        "model_icons": icons_out,
        "rooms": [r for r, _ in ROOMS],
        "devices": devices,
        "scenes": [],
    }
    total = len(devices)
    by_room = {}
    for d in devices:
        by_room[d["room"]] = by_room.get(d["room"], 0) + 1
    print("total:", total, by_room)
    print(f"brand: 米家系 {family_count} ({family_count / total:.0%}) / "
          f"第三方 {other_count} ({other_count / total:.0%})")
    print("unique models:", len(models_out), "icons:", len(icons_out))
    assert total >= 400
    assert set(pack["rooms"]) == set(by_room)
    assert 0.55 <= family_count / total <= 0.65, (family_count, total)
    OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=0),
                   encoding="utf-8")
    print("written:", OUT, round(OUT.stat().st_size / 1024, 1), "KB")


if __name__ == "__main__":
    main()
