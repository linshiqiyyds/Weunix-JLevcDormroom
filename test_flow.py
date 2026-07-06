import queue

import weunix_core as app


def test_mock_business_flow():
    calls = []

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
                        "Name": "Test User",
                        "DepartmentName": "Group A",
                    }
                },
            }
        if path == app.room_api_path("GetRoomCosts"):
            return {"code": 1, "result": [{"room_type_id": "1", "room_type": "Type A", "room_charge": "1200", "room_bed_num": 1}]}
        if path == app.room_api_path("CreateRoomOrder"):
            return {"code": 1, "order_id": "ORDER1", "pay_url": "https://pay.example/ORDER1"}
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
        order_id, pay_url, _ = engine.create_order(rooms[0])
    finally:
        app.request_json = original

    assert account.student_id == "S001"
    assert rooms[0]["room_type_id"] == "1"
    assert order_id == "ORDER1"
    assert pay_url.startswith("https://")
    assert app.room_api_path("CreateRoomOrder") in calls


if __name__ == "__main__":
    test_mock_business_flow()
    print("mock business flow ok")
