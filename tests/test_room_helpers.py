from room_helpers import (
    normalize_room_preference,
    pick_first_available_room,
    pref_ids,
    room_preference_label,
)


def test_normalize_room_preference():
    assert normalize_room_preference("四人寝") == "1"
    assert normalize_room_preference("八人寝") == "2"
    assert normalize_room_preference("四人寝、八人寝") == "1,2"
    assert normalize_room_preference("不限") == ""


def test_room_preference_label():
    assert room_preference_label("1") == "四人寝"
    assert room_preference_label("2") == "八人寝"
    assert room_preference_label("") == "不限"


def test_pref_ids():
    assert pref_ids("1,2") == {"1", "2"}
    assert pref_ids("不限") == set()


def test_pick_first_available_room():
    rooms = [
        {"room_type_id": "1", "room_bed_num": 0},
        {"room_type_id": "2", "room_bed_num": 1},
    ]
    assert pick_first_available_room(rooms, "四人寝") is None
    assert pick_first_available_room(rooms, "八人寝")["room_type_id"] == "2"


if __name__ == "__main__":
    test_normalize_room_preference()
    test_room_preference_label()
    test_pref_ids()
    test_pick_first_available_room()
    print("test_room_helpers ok")
