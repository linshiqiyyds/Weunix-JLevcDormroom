import queue

import weunix_core as app


def test_mock_business_flow():
    calls = []
    order_payloads = []

    def fake_request_json(session, path, method="get", **kwargs):
        calls.append(path)
        if path == app.auth_api_path("LoginByopenid"):
            return {"code": 1, "result": {"TokenContent": "token"}}
        if path == app.batch_api_path("GetStepDetailByStudentId"):
            return {
                "code": 1,
                "result": {
                    "student_info": {
                        "UserCard": "S001",
                        "UserId": "U001",
                        "Name": "Test User",
                        "DepartmentName": "Group A",
                    }
                },
            }
        if path == app.room_api_path("GetroomCosts"):
            return {"code": 1, "result": [{"room_type_id": "1556921816654680064", "room_type": "4人间", "room_charge": "1680", "room_bed_num": 1}]}
        if path == app.room_api_path("CreateRoomOrder"):
            order_payloads.append(kwargs.get("json"))
            return {"code": 1, "result": "ORDER1"}
        if path == app.room_api_path("Get_PayRecord"):
            assert kwargs.get("params") == {"student_id": "U001"}
            return {"code": 1, "result": [{"id": "ORDER1", "pay_status": 0, "pay_links": "https://pay.example/ORDER1"}]}
        raise AssertionError(path)

    original = app.request_json
    app.request_json = fake_request_json
    try:
        msg_queue = queue.Queue()
        account = app.Account(openid="openid")
        engine = app.GrabberEngine(account, msg_queue)
        engine.login()
        engine.fetch_student_info()
        rooms = engine.fetch_rooms()
        room = engine.pick_room(rooms, "1")
        order_id, pay_url, _ = engine.create_order(room)
        payment = engine.payment_snapshot(order_id, room, pay_url, "已提交订单")
    finally:
        app.request_json = original

    assert account.student_id == "S001"
    assert account.user_id == "U001"
    assert room["room_type_id"] == "1556921816654680064"
    assert order_id == "ORDER1"
    assert pay_url.startswith("https://")
    assert payment["payment_state"] == "pending"
    assert payment["state_label"] == "待支付"
    assert payment["records_count"] == 1
    assert order_payloads[0]["student_id"] == "U001"
    assert order_payloads[0]["room_type_id"] == "1556921816654680064"
    assert app.room_api_path("CreateRoomOrder") in calls


def test_grab_worker_stops_after_first_created_order():
    calls = []
    room_calls = 0
    order_calls = 0
    watched = {}

    def fake_request_json(session, path, method="get", **kwargs):
        nonlocal room_calls, order_calls
        calls.append(path)
        if path == app.auth_api_path("LoginByopenid"):
            return {"code": 1, "result": {"TokenContent": "token"}}
        if path == app.batch_api_path("GetStepDetailByStudentId"):
            return {
                "code": 1,
                "result": {
                    "student_info": {
                        "UserId": "U001",
                        "UserCard": "S001",
                        "Name": "Test User",
                    }
                },
            }
        if path == app.room_api_path("GetroomCosts"):
            room_calls += 1
            return {"code": 1, "result": [{"room_type_id": "1556921816654680064", "room_type": "4人间", "room_charge": "1680", "room_bed_num": 1}]}
        if path == app.room_api_path("CreateRoomOrder"):
            order_calls += 1
            return {"code": 1, "result": "ORDER1"}
        if path == app.room_api_path("Get_PayRecord"):
            return {"code": 1, "result": [{"id": "ORDER1", "pay_status": 0, "pay_links": "https://pay.example/ORDER1"}]}
        raise AssertionError(path)

    original = app.request_json
    app.request_json = fake_request_json
    try:
        msg_queue = queue.Queue()
        account = app.Account(openid="openid")
        engine = app.GrabberEngine(account, msg_queue)

        def fake_watch_payment_status(order_id="", room=None, pay_url="", message=""):
            watched["order_id"] = order_id
            watched["pay_url"] = pay_url
            watched["room"] = room

        engine.watch_payment_status = fake_watch_payment_status
        engine._grab_worker("", "1")
    finally:
        app.request_json = original

    assert room_calls == 1
    assert order_calls == 1
    assert calls.count(app.room_api_path("CreateRoomOrder")) == 1
    assert watched["order_id"] == "ORDER1"
    assert watched["pay_url"].startswith("https://")
    assert engine.running is False


if __name__ == "__main__":
    test_mock_business_flow()
    test_grab_worker_stops_after_first_created_order()
    print("mock business flow ok")
