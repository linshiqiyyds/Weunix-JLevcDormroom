from __future__ import annotations

import re

ROOM_PREF_OPTIONS = ("4人间、8人间", "4人间", "8人间", "不限")

ROOM_PREF_TO_IDS = {
    "4人间、8人间": "1,2",
    "4人间": "1",
    "8人间": "2",
    "四人寝、八人寝": "1,2",
    "四人寝": "1",
    "八人寝": "2",
    "不限": "",
    "1,2": "1,2",
    "1": "1",
    "2": "2",
    "": "",
    None: "",
}

IDS_TO_ROOM_PREF = {
    "1,2": "4人间、8人间",
    "1": "4人间",
    "2": "8人间",
    "": "不限",
}

ROOM_TYPE_ID_KEYS = ("room_type_id", "roomTypeId", "room_typeid", "roomTypeID", "type_id", "typeId", "id")
ROOM_TYPE_KEYS = ("room_type", "roomType", "room_type_name", "roomTypeName", "type_name", "typeName", "name", "title")
ROOM_BED_KEYS = ("room_bed_num", "room_bed_count", "roomBedNum", "roomBedCount", "bed_num", "bedNum", "remain", "surplus", "left_count", "available_count", "count")
ROOM_CHARGE_KEYS = ("room_charge", "roomCharge", "charge", "price", "amount", "money", "need_pay_money", "pay_money")


def normalize_room_preference(pref) -> str:
    if isinstance(pref, str):
        pref = pref.strip()
    return ROOM_PREF_TO_IDS.get(pref, "")


def room_preference_label(pref) -> str:
    return IDS_TO_ROOM_PREF.get(normalize_room_preference(pref), "不限")


def pref_ids(pref) -> set[str]:
    normalized = normalize_room_preference(pref)
    return {part for part in normalized.split(",") if part}


def first_present(room: dict, *keys):
    lower_map = {str(key).lower(): key for key in room.keys()}
    for key in keys:
        if key in room and room.get(key) not in (None, ""):
            return room.get(key)
        actual = lower_map.get(str(key).lower())
        if actual is not None and room.get(actual) not in (None, ""):
            return room.get(actual)
    return None


def iter_text_values(room: dict, keys: tuple[str, ...] | None = None):
    if not isinstance(room, dict):
        return
    source_keys = keys or tuple(room.keys())
    for key in source_keys:
        value = first_present(room, key)
        if isinstance(value, (str, int, float)):
            text = str(value).strip()
            if text:
                yield text


def normalize_money_value(value):
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        number = float(value)
        return str(int(number)) if number.is_integer() else str(number)
    text = str(value).strip()
    currency_match = re.search(r"[¥￥]\s*([0-9]+(?:\.[0-9]+)?)", text)
    if currency_match:
        return normalize_money_value(currency_match.group(1))
    yuan_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*元", text)
    if yuan_match:
        return normalize_money_value(yuan_match.group(1))
    plain = re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text)
    if plain:
        return normalize_money_value(float(text))
    return text


def parse_money_from_text(text: str) -> str:
    return normalize_money_value(text)


def canonical_room_type(text: str) -> str:
    value = str(text or "").strip()
    if any(mark in value for mark in ("4人", "四人")):
        return "4人间"
    if any(mark in value for mark in ("8人", "八人")):
        return "8人间"
    return value


def room_type_id(room: dict) -> str:
    return str(first_present(room, *ROOM_TYPE_ID_KEYS) or "")


def room_type_text(room: dict) -> str:
    return canonical_room_type(str(first_present(room, *ROOM_TYPE_KEYS) or ""))


def room_charge(room: dict) -> str:
    direct = first_present(room, *ROOM_CHARGE_KEYS)
    parsed = normalize_money_value(direct)
    if parsed:
        return parsed
    for text in iter_text_values(room, ROOM_TYPE_KEYS):
        parsed = parse_money_from_text(text)
        if parsed and parsed != text:
            return parsed
    return ""


def room_charge_number(room: dict) -> float | None:
    value = room_charge(room)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def room_bed_count(room: dict) -> int | None:
    value = first_present(room, *ROOM_BED_KEYS)
    if value in (None, ""):
        for text in iter_text_values(room, ROOM_TYPE_KEYS):
            match = re.search(r"(?:剩余|余)\s*([0-9]+)\s*(?:间|个|套|床)?", text)
            if match:
                value = match.group(1)
                break
        else:
            return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def room_matches_preference(room: dict, pref) -> bool:
    ids = pref_ids(pref)
    if not ids or ids == {"1", "2"}:
        return True
    rid = room_type_id(room)
    label = room_type_text(room)
    if rid and rid in ids:
        return True
    if "1" in ids and any(mark in label for mark in ("4", "四")):
        return True
    if "2" in ids and any(mark in label for mark in ("8", "八")):
        return True
    return False


def pick_first_available_room(rooms: list[dict], pref="") -> dict | None:
    available = []
    for room in rooms:
        beds = room_bed_count(room)
        if beds is None or beds > 0:
            available.append(room)
        if room_matches_preference(room, pref) and (beds is None or beds > 0):
            return room
    ids = pref_ids(pref)
    priced = [(room_charge_number(room), room) for room in available]
    priced = [(price, room) for price, room in priced if price is not None]
    if len({price for price, _ in priced}) >= 2:
        priced.sort(key=lambda item: item[0])
        if ids == {"1"}:
            return priced[-1][1]
        if ids == {"2"}:
            return priced[0][1]
    return None
