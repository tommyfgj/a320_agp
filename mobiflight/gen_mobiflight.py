"""生成 A320 AGP 面板的 MobiFlight 引脚配置 (.mfmc) 与 Fenix A320 项目 (.mfproj)。

数据来源:
  ../mega_adapter_pinmap.csv  转接板插座 -> Mega2560 引脚
  ../korry_legends.csv        面板 Korry 灯/按键定义
  MobiFlight 11.1.0 Presets/msfs2020_hubhop_presets.json  Fenix A320 LVAR (UUID 为 HubHop 预设 id)
"""

import csv
import json
import uuid
from pathlib import Path
from xml.sax.saxutils import quoteattr

HERE = Path(__file__).resolve().parent

MODULE_NAME = "A320 AGP"
MODULE_SERIAL = "SN-000-000"
PROJECT_NAME = "A320 AGP - Fenix A320"

# (插座, 位置, Mega 引脚, MobiFlight 设备名, 面板项, 灯字/功能, 颜色, Fenix 变量代码, HubHop 预设 id)
OUTPUTS = [
    ("J1", "上", 3, "GEAR1_UNLK", "LDG GEAR 1 (左主轮)", "UNLK", "红", "(L:I_MIP_GEAR_1_U)", "7142c79b-bced-4424-b5d0-e1ee326bab08"),
    ("J1", "下", 2, "GEAR1_DOWN", "LDG GEAR 1 (左主轮)", "▽", "绿", "(L:I_MIP_GEAR_1_L)", "87d4c692-73e8-4448-81b6-12dd09a0575c"),
    ("J2", "上", 5, "GEAR2_UNLK", "LDG GEAR 2 (前轮)", "UNLK", "红", "(L:I_MIP_GEAR_2_U)", "ccdf88e7-597b-4bc6-8c44-4e32696b5449"),
    ("J2", "下", 4, "GEAR2_DOWN", "LDG GEAR 2 (前轮)", "▽", "绿", "(L:I_MIP_GEAR_2_L)", "b6d3c141-92ee-4d3d-9091-d206606b0b74"),
    ("J3", "上", 7, "GEAR3_UNLK", "LDG GEAR 3 (右主轮)", "UNLK", "红", "(L:I_MIP_GEAR_3_U)", "4f8c91b2-3687-4b7c-abca-da7bf0b4d0ba"),
    ("J3", "下", 6, "GEAR3_DOWN", "LDG GEAR 3 (右主轮)", "▽", "绿", "(L:I_MIP_GEAR_3_L)", "51b5025c-c71e-4442-b9f9-6dce3e4cdaf1"),
    ("J4", "上", 9, "ABRK_LO_DECEL", "AUTO BRK LO", "DECEL", "绿", "(L:I_MIP_AUTOBRAKE_LO_U)", "7598d4a6-f844-4fdd-a623-422dfd39a174"),
    ("J4", "下", 8, "ABRK_LO_ON", "AUTO BRK LO", "ON", "蓝", "(L:I_MIP_AUTOBRAKE_LO_L)", "1631ad70-b2e2-4203-92c7-dec73e06b10a"),
    ("J5", "上", 11, "ABRK_MED_DECEL", "AUTO BRK MED", "DECEL", "绿", "(L:I_MIP_AUTOBRAKE_MED_U)", "79f26531-8236-47f8-9854-d68f8dc8e2b9"),
    ("J5", "下", 10, "ABRK_MED_ON", "AUTO BRK MED", "ON", "蓝", "(L:I_MIP_AUTOBRAKE_MED_L)", "312c1115-898f-4e97-8426-10866b29a94b"),
    ("J6", "上", 13, "ABRK_MAX_DECEL", "AUTO BRK MAX", "DECEL", "绿", "(L:I_MIP_AUTOBRAKE_MAX_U)", "6d38c70d-6342-47fa-9264-223800cf6d3c"),
    ("J6", "下", 12, "ABRK_MAX_ON", "AUTO BRK MAX", "ON", "蓝", "(L:I_MIP_AUTOBRAKE_MAX_L)", "fc1d4c4d-5b73-4085-a3ca-cbe555ebb95f"),
    ("J7", "上", 15, "BRKFAN_HOT", "BRK FAN", "HOT", "琥珀", "(L:I_MIP_BRAKE_FAN_U)", "e3e4891d-3558-4b25-b974-d260069e64e1"),
    ("J7", "下", 14, "BRKFAN_ON", "BRK FAN", "ON", "蓝", "(L:I_MIP_BRAKE_FAN_L)", "71f795c8-523d-443b-a8ee-03c11e88703c"),
    ("J8", "上", 17, "GEAR_ARROW", "LDG GEAR 手柄", "向下箭头", "红", "(L:I_MIP_GEAR_RED)", "6d934eea-2ffd-4486-b97b-136df6e30675"),
    ("J8", "下", 16, "TERR_ON", "TERR ON ND (机长侧)", "ON", "绿", "(L:I_MIP_GPWS_TERRAIN_ON_ND_CAPT_L)", "7256246a-484e-4b37-bf6c-20a29efd11b4"),
]

# (插座, Mega 引脚, MobiFlight 设备名, 面板项, 开关类型, onPress 代码, onRelease 代码)
# 输入为 INPUT_PULLUP，触点闭合 = LOW = MobiFlight onPress
INPUTS = [
    ("JS1", 18, "ASKID_SW", "A/SKID & N/W STRG", "两档拨杆 (闭合=ON)",
     "1 (>L:S_FC_MIP_ANTI_SKID)",
     "0 (>L:S_FC_MIP_ANTI_SKID)"),
    ("JS2", 19, "GEAR_LEVER_SW", "LDG GEAR 手柄", "两档手柄 (闭合=DOWN)",
     "1 (>L:S_MIP_GEAR)",
     "0 (>L:S_MIP_GEAR)"),
    ("JS4", 21, "ABRK_LO_BTN", "AUTO BRK LO", "瞬时按钮",
     "1 (>L:S_MIP_AUTOBRAKE_LO)",
     "0 (>L:S_MIP_AUTOBRAKE_LO)"),
    ("JS5", 22, "ABRK_MED_BTN", "AUTO BRK MED", "瞬时按钮",
     "1 (>L:S_MIP_AUTOBRAKE_MED)",
     "0 (>L:S_MIP_AUTOBRAKE_MED)"),
    ("JS6", 23, "ABRK_MAX_BTN", "AUTO BRK MAX", "瞬时按钮",
     "1 (>L:S_MIP_AUTOBRAKE_MAX)",
     "0 (>L:S_MIP_AUTOBRAKE_MAX)"),
    ("JS7", 24, "BRKFAN_BTN", "BRK FAN", "自锁按钮 (按下保持=ON)",
     "1 (>L:S_MIP_BRAKE_FAN) 2 (>L:S_MIP_BRAKE_FAN_Anim)",
     "0 (>L:S_MIP_BRAKE_FAN) 0 (>L:S_MIP_BRAKE_FAN_Anim)"),
    ("JS8", 25, "TERR_BTN", "TERR ON ND (机长侧)", "瞬时按钮",
     "1 (>L:S_MIP_GPWS_TERRAIN_ON_ND_CAPT)",
     "0 (>L:S_MIP_GPWS_TERRAIN_ON_ND_CAPT)"),
]

SPARE_INPUTS = [("JS3", 20)]


def stable_guid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"a320-agp/{name}"))


def controller():
    return {"Name": MODULE_NAME, "Serial": MODULE_SERIAL}


def output_item(sock, pos, pin, dev, panel, legend, color, code, preset):
    return {
        "Source": {
            "SourceType": "SIMCONNECT",
            "SimConnectValue": {"UUID": preset, "Value": code, "VarType": 2},
            "Type": "SimConnectSource",
        },
        "TestValue": {"type": 1, "Float64": 1.0, "String": None},
        "Device": {"Pin": dev, "Brightness": 255, "PwmMode": False, "Type": "Output"},
        "DeviceType": "Output",
        "GUID": stable_guid(f"out/{dev}"),
        "Active": True,
        "Name": f"{panel} {legend} ({sock}{pos} D{pin})",
        "Type": "OutputConfigItem",
        "Controller": controller(),
        "Preconditions": [],
        "Modifiers": {"Items": []},
        "ConfigRefs": [],
        "Status": {},
    }


def action(code):
    return {"Type": "MSFS2020CustomInputAction", "Command": code}


def input_item(sock, pin, dev, panel, kind, on_press, on_release):
    return {
        "button": {
            "onPress": action(on_press),
            "onRelease": action(on_release),
            "onLongRelease": None,
            "onHold": None,
            "LongReleaseDelay": 350,
            "HoldDelay": 350,
            "RepeatDelay": 0,
        },
        "DeviceType": "Button",
        "DeviceName": dev,
        "GUID": stable_guid(f"in/{dev}"),
        "Active": True,
        "Name": f"{panel} {kind} ({sock} D{pin})",
        "Type": "InputConfigItem",
        "Controller": controller(),
        "Preconditions": [],
        "Modifiers": {"Items": []},
        "ConfigRefs": [],
        "Status": {},
    }


def write_mfmc(path):
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<Config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">',
        "  <ModuleType>MobiFlight Mega</ModuleType>",
        f"  <ModuleName>{MODULE_NAME}</ModuleName>",
    ]
    for _, _, pin, dev, *_ in sorted(OUTPUTS, key=lambda o: o[2]):
        lines.append(f"  <Output Name={quoteattr(dev)} Pin=\"{pin}\" />")
    for _, pin, dev, *_ in INPUTS:
        lines.append(f"  <Button Name={quoteattr(dev)} Pin=\"{pin}\" />")
    lines.append("</Config>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_mfproj(path):
    items = [output_item(*o) for o in OUTPUTS] + [input_item(*i) for i in INPUTS]
    project = {
        "Name": PROJECT_NAME,
        "Sim": "msfs",
        "Features": {"FSUIPC": False, "ProSim": False},
        "Aircraft": [],
        "ConfigFiles": [
            {
                "Label": MODULE_NAME,
                "FileName": None,
                "ReferenceOnly": False,
                "EmbedContent": True,
                "ConfigItems": items,
            }
        ],
        "_version": "0.9",
    }
    path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_map_csv(path):
    header = ["插座", "插座引脚", "位置", "Mega2560引脚", "MobiFlight设备", "MobiFlight类型",
              "面板项", "灯字/功能", "颜色", "Fenix 变量 / onPress", "onRelease"]
    pin_of_pos = {"上": "3(-)/4(+)", "下": "1(-)/2(+)"}
    rows = []
    for sock, pos, pin, dev, panel, legend, color, code, _ in OUTPUTS:
        rows.append([sock, pin_of_pos[pos], pos, f"D{pin}", dev, "Output (LED)", panel, legend, color, code, ""])
    for sock, pin, dev, panel, kind, on_press, on_release in INPUTS:
        rows.append([sock, "1(信号)/2(GND)", "", f"D{pin}", dev, "Button", panel, kind, "", on_press, on_release])
    for sock, pin in SPARE_INPUTS:
        rows.append([sock, "1(信号)/2(GND)", "", f"D{pin}", "", "", "备用", "", "", "", ""])
    rows.sort(key=lambda r: (r[0].replace("JS", "J") , r[0].startswith("JS"), r[2] != "上"))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def check_against_pinmap():
    pinmap = HERE.parent / "mega_adapter_pinmap.csv"
    expected = {}
    with pinmap.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["Mega2560引脚"].startswith("D"):
                pos = "上" if "上方" in r["功能"] else "下" if "下方" in r["功能"] else ""
                expected[(r["插座"], pos)] = int(r["Mega2560引脚"][1:])
    for sock, pos, pin, *_ in OUTPUTS:
        assert expected[(sock, pos)] == pin, (sock, pos, pin)
    for sock, pin, *_ in INPUTS:
        assert expected[(sock, "")] == pin, (sock, pin)
    used = [o[2] for o in OUTPUTS] + [i[1] for i in INPUTS]
    assert len(used) == len(set(used)), "引脚重复"


if __name__ == "__main__":
    check_against_pinmap()
    write_mfmc(HERE / "A320_AGP_Mega.mfmc")
    write_mfproj(HERE / "A320_AGP_Fenix.mfproj")
    write_map_csv(HERE / "korry_mobiflight_map.csv")
    print(f"outputs={len(OUTPUTS)} inputs={len(INPUTS)} spare={len(SPARE_INPUTS)}")
