from __future__ import annotations

ROOM_PREF_OPTIONS = ("四人寝、八人寝", "四人寝", "八人寝", "不限")

ROOM_PREF_TO_IDS = {
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
    "1,2": "四人寝、八人寝",
    "1": "四人寝",
    "2": "八人寝",
    "": "不限",
}


def normalize_room_preference(pref) -> str:
    if isinstance(pref, str):
        pref = pref.strip()
    return ROOM_PREF_TO_IDS.get(pref, "")


def room_preference_label(pref) -> str:
    return IDS_TO_ROOM_PREF.get(normalize_room_preference(pref), "不限")


def pref_ids(pref) -> set[str]:
    normalized = normalize_room_preference(pref)
    return {part for part in normalized.split(",") if part}


def room_type_id(room: dict) -> str:
    return str(room.get("room_type_id") or room.get("roomTypeId") or room.get("id") or "")


def room_bed_count(room: dict) -> int:
    value = room.get("room_bed_num") or room.get("room_bed_count") or room.get("bed_num") or 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def room_matches_preference(room: dict, pref) -> bool:
    ids = pref_ids(pref)
    rid = room_type_id(room)
    return not ids or rid in ids


def pick_first_available_room(rooms: list[dict], pref="") -> dict | None:
    for room in rooms:
        if room_matches_preference(room, pref) and room_bed_count(room) > 0:
            return room
    return None
