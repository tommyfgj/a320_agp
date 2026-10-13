"""离线全量校验 A320 AGP MobiFlight 配置。

用法: python test_mobiflight.py [MobiFlight 源码目录]
"""

import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MF_SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\fengguanjin\Downloads\MobiFlight-Connector-11.1.0-src")
BOARD = MF_SRC / "src/MobiFlightConnector/Boards/arduino_mega.board.json"
HUBHOP = MF_SRC / "src/MobiFlightConnector/Presets/msfs2020_hubhop_presets.json"

failures = []
passes = 0


def check(cond, msg):
    global passes
    if cond:
        passes += 1
    else:
        failures.append(msg)


def norm(code):
    return re.sub(r"\s+", " ", code or "").strip()


def rpn_balanced(code):
    return code.count("(") == code.count(")") and code.count("{") == code.count("}")


def main():
    mfmc = ET.parse(HERE / "A320_AGP_Mega.mfmc").getroot()
    proj = json.loads((HERE / "A320_AGP_Fenix.mfproj").read_text(encoding="utf-8"))
    board = json.loads(BOARD.read_text(encoding="utf-8"))
    presets = {p["id"]: p for p in json.loads(HUBHOP.read_text(encoding="utf-8"))}
    with (ROOT / "mega_adapter_pinmap.csv").open(encoding="utf-8-sig") as f:
        pinmap = list(csv.DictReader(f))
    with (ROOT / "korry_legends.csv").open(encoding="utf-8-sig") as f:
        legends = list(csv.DictReader(f))

    # 1. 引脚配置 vs 转接板
    devices = {}
    for el in mfmc:
        if el.tag in ("Output", "Button"):
            name, pin = el.get("Name"), int(el.get("Pin"))
            check(name not in devices, f"mfmc 设备名重复: {name}")
            devices[name] = (el.tag, pin)
            check(re.fullmatch(r"[A-Za-z0-9_]{1,16}", name or "") is not None, f"设备名不合法: {name}")
    pins = [p for _, p in devices.values()]
    check(len(pins) == len(set(pins)), "mfmc 引脚重复")
    check(mfmc.findtext("ModuleType") == "MobiFlight Mega", "ModuleType 不是 MobiFlight Mega")

    board_pins = {p["Pin"]: p for p in board["Pins"]}
    for name, (tag, pin) in devices.items():
        check(pin in board_pins, f"{name}: D{pin} 不在 Mega 板定义中")
    limits = board["ModuleLimits"]
    check(sum(t == "Output" for t, _ in devices.values()) <= limits["MaxOutputs"], "Output 超限")
    check(sum(t == "Button" for t, _ in devices.values()) <= limits["MaxButtons"], "Button 超限")
    cfg_str = "".join(f"{3 if t == 'Output' else 1}.{p}.{n}:" for n, (t, p) in devices.items())
    check(len(cfg_str) < board["Connection"]["EEPROMSize"], f"固件配置串 {len(cfg_str)} 字节超出 EEPROM")

    led_pins = {int(r["Mega2560引脚"][1:]): r for r in pinmap if "LED 负极" in r["功能"]}
    sw_pins = {int(r["Mega2560引脚"][1:]): r for r in pinmap if "自锁开关（" in r["功能"]}
    for name, (tag, pin) in devices.items():
        if tag == "Output":
            check(pin in led_pins, f"{name}: D{pin} 不是转接板 LED 通道")
        else:
            check(pin in sw_pins, f"{name}: D{pin} 不是转接板开关输入")
    out_pins = {p for t, p in devices.values() if t == "Output"}
    check(out_pins == set(led_pins), f"LED 通道未全部使用: {sorted(set(led_pins) - out_pins)}")

    # 2. 项目配置项
    items = proj["ConfigFiles"][0]["ConfigItems"]
    check(proj.get("_version") == "0.9", "项目 schema 版本不是 0.9")
    guids = [i["GUID"] for i in items]
    check(len(guids) == len(set(guids)), "GUID 重复")
    used_devices = set()
    var_by_device = {}
    for it in items:
        ctrl = it["Controller"]
        check(ctrl["Name"] == mfmc.findtext("ModuleName"), f"{it['Name']}: 控制器名与 mfmc 不一致")
        check(ctrl["Serial"].startswith("SN-"), f"{it['Name']}: 序列号前缀不是 SN-")
        if it["Type"] == "OutputConfigItem":
            dev = it["Device"]["Pin"]
            used_devices.add(dev)
            check(devices.get(dev, ("",))[0] == "Output", f"{it['Name']}: 设备 {dev} 不是 mfmc Output")
            sv = it["Source"]["SimConnectValue"]
            check(sv["VarType"] == 2, f"{dev}: VarType 不是 CODE")
            pre = presets.get(sv["UUID"])
            check(pre is not None, f"{dev}: HubHop 预设 {sv['UUID']} 不存在")
            if pre:
                check(pre["presetType"] == "Output", f"{dev}: 预设不是 Output 类型")
                check(norm(pre["code"]) == norm(sv["Value"]), f"{dev}: 代码与预设不一致 {sv['Value']} vs {pre['code']}")
                check("Fenix" in pre["vendor"] and "320" in pre["aircraft"], f"{dev}: 预设不属于 Fenix A320")
            check(it["Device"]["Brightness"] == 255 and not it["Device"]["PwmMode"], f"{dev}: 亮度/PWM 设置异常")
            var_by_device[dev] = sv["Value"]
        else:
            dev = it["DeviceName"]
            used_devices.add(dev)
            check(devices.get(dev, ("",))[0] == "Button", f"{it['Name']}: 设备 {dev} 不是 mfmc Button")
            for ev in ("onPress", "onRelease"):
                act = it["button"][ev]
                check(act and act["Type"] == "MSFS2020CustomInputAction", f"{dev}.{ev}: 动作缺失")
                code = act["Command"]
                check(rpn_balanced(code), f"{dev}.{ev}: RPN 括号不平衡")
                for var in re.findall(r"\(>L:([A-Za-z0-9_]+)\)", code):
                    known = any(f"L:{var})" in p["code"] for p in presets.values()
                                if "Fenix" in p["vendor"])
                    check(known, f"{dev}.{ev}: L:{var} 在 HubHop Fenix 预设中找不到")
            var_by_device[dev] = it["button"]["onPress"]["Command"]
    check(used_devices == set(devices), f"mfmc 中有未被项目使用的设备: {set(devices) - used_devices}")

    # 3. 同一插座的上下灯属于同一个 Korry
    for sock_leds in [(3, 2), (5, 4), (7, 6), (9, 8), (11, 10), (13, 12), (15, 14)]:
        names = [n for n, (t, p) in devices.items() if p in sock_leds]
        stems = {re.sub(r"_[^_]+$", "", n) for n in names}
        check(len(stems) == 1, f"同插座灯不属于同一按钮: {names}")
    for pin_up, pin_lo, sw in [(9, 8, 21), (11, 10, 22), (13, 12, 23), (15, 14, 24), (16, 16, 25)]:
        sw_name = next(n for n, (t, p) in devices.items() if p == sw)
        lo_name = next(n for n, (t, p) in devices.items() if p == pin_lo)
        check(sw_name.rsplit("_", 1)[0] == lo_name.rsplit("_", 1)[0], f"按钮 {sw_name} 与灯 {lo_name} 不在同一插座")
    for pre_var, lamp in [("AUTOBRAKE_LO", "ABRK_LO"), ("AUTOBRAKE_MED", "ABRK_MED"), ("AUTOBRAKE_MAX", "ABRK_MAX"),
                          ("BRAKE_FAN", "BRKFAN"), ("TERRAIN_ON_ND_CAPT", "TERR")]:
        btn_code = var_by_device[f"{lamp}_BTN"]
        lamp_codes = [v for k, v in var_by_device.items() if k.startswith(lamp) and not k.endswith("_BTN")]
        check(pre_var in btn_code and all(pre_var in c for c in lamp_codes), f"{lamp}: 按钮与灯变量不对应")
    for d, half in [(n, n.rsplit("_", 1)[1]) for n in var_by_device if n.startswith(("GEAR1", "GEAR2", "GEAR3", "ABRK", "BRKFAN"))
                    and not n.endswith(("_BTN", "_SW"))]:
        upper = half in ("UNLK", "DECEL", "HOT")
        check(var_by_device[d].endswith("_U)") == upper, f"{d}: 上下半灯与 Fenix _U/_L 不对应")

    # 4. Korry 表覆盖
    expected_lamps = 0
    for r in legends:
        n = int(r["数量"])
        for half in ("上半部分灯字", "下半部分灯字"):
            if r[half] not in ("—", "（空白）", ""):
                expected_lamps += n
    check(expected_lamps == sum(t == "Output" for t, _ in devices.values()),
          f"Korry 表灯数 {expected_lamps} 与 Output 数不一致")
    expected_inputs = sum(int(r["数量"]) for r in legends if "按钮" in r["类型"] or "开关" in r["类型"]) + 1
    check(expected_inputs == sum(t == "Button" for t, _ in devices.values()),
          f"Korry 表输入数 {expected_inputs}(含起落架手柄) 与 Button 数不一致")

    print(f"通过 {passes} 项, 失败 {len(failures)} 项")
    for m in failures:
        print("  FAIL:", m)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
