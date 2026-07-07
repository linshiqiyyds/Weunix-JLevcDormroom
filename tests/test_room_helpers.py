from room_helpers import (
    normalize_room_preference,
    pick_first_available_room,
    pref_ids,
    room_bed_count,
    room_charge,
    room_preference_label,
    room_type_text,
)


def test_normalize_room_preference():
    assert normalize_room_preference("4人间") == "1"
    assert normalize_room_preference("8人间") == "2"
    assert normalize_room_preference("4人间、8人间") == "1,2"
    assert normalize_room_preference("四人寝") == "1"
    assert normalize_room_preference("八人寝") == "2"
    assert normalize_room_preference("四人寝、八人寝") == "1,2"
    assert normalize_room_preference("不限") == ""


def test_room_preference_label():
    assert room_preference_label("1") == "4人间"
    assert room_preference_label("2") == "8人间"
    assert room_preference_label("") == "不限"


def test_pref_ids():
    assert pref_ids("1,2") == {"1", "2"}
    assert pref_ids("不限") == set()


def test_pick_first_available_room():
    rooms = [
        {"room_type_id": "1", "room_bed_num": 0},
        {"room_type_id": "2", "room_bed_num": 1},
    ]
    assert pick_first_available_room(rooms, "4人间") is None
    assert pick_first_available_room(rooms, "8人间")["room_type_id"] == "2"


def test_pick_long_service_room_type_id_by_label():
    rooms = [
        {"room_type_id": "1556921816654680064", "room_type": "4人间", "room_bed_num": 3},
        {"room_type_id": "1556921816654680065", "room_type": "8人间", "room_bed_num": 5},
    ]
    assert pick_first_available_room(rooms, "4人间")["room_type_id"] == "1556921816654680064"
    assert pick_first_available_room(rooms, "8人间")["room_type_id"] == "1556921816654680065"


def test_pick_unknown_bed_count_when_service_omits_count():
    rooms = [{"room_type_id": "1556921816654680064", "room_type": "4人间"}]
    assert pick_first_available_room(rooms, "4人间")["room_type_id"] == "1556921816654680064"


def test_parse_real_selection_copy_from_title_and_price():
    rooms = [
        {"room_type_id": "1556921816654680064", "title": "4人间(剩余12间) ¥1680"},
        {"room_type_id": "1556921816654680065", "title": "8人间(剩余15间) ¥980"},
    ]
    four = pick_first_available_room(rooms, "4人间")
    eight = pick_first_available_room(rooms, "8人间")
    assert four["room_type_id"] == "1556921816654680064"
    assert eight["room_type_id"] == "1556921816654680065"
    assert room_type_text(four) == "4人间"
    assert room_bed_count(four) == 12
    assert room_charge(four) == "1680"
    assert room_type_text(eight) == "8人间"
    assert room_bed_count(eight) == 15
    assert room_charge(eight) == "980"


def test_pick_by_relative_price_when_label_is_missing():
    rooms = [
        {"room_type_id": "type-high", "price": "¥1880", "room_bed_num": 2},
        {"room_type_id": "type-low", "price": "980元", "room_bed_num": 2},
    ]
    assert pick_first_available_room(rooms, "4人间")["room_type_id"] == "type-high"
    assert pick_first_available_room(rooms, "8人间")["room_type_id"] == "type-low"


if __name__ == "__main__":
    test_normalize_room_preference()
    test_room_preference_label()
    test_pref_ids()
    test_pick_first_available_room()
    test_pick_long_service_room_type_id_by_label()
    test_pick_unknown_bed_count_when_service_omits_count()
    test_parse_real_selection_copy_from_title_and_price()
    test_pick_by_relative_price_when_label_is_missing()
    print("test_room_helpers ok")
