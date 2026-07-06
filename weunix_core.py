import json
import os
import queue
import re
import shutil
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import unquote, urlparse

import requests


_DEFAULT_SERVICE_HOST = "".join(chr(code) for code in (122, 110, 46, 106, 108, 101, 118, 99, 46, 99, 110))
BASE = os.environ.get("WEUNIX_SERVICE_BASE", f"http://{_DEFAULT_SERVICE_HOST}").rstrip("/")
SERVICE_HOST = urlparse(BASE).hostname or ""
SERVICE_LABEL = os.environ.get("WEUNIX_SERVICE_LABEL", "服务端点已配置")
_SERVICE_ROOT = "".join(chr(code) for code in (47, 89, 88, 50, 48, 50, 50))
_API_ROOT = f"{_SERVICE_ROOT}/api"
_VIEW_ROOT = f"{_SERVICE_ROOT}/mbview/"
AUTH_API = "".join(chr(code) for code in (83, 116, 117, 100, 101, 110, 116, 76, 111, 103, 105, 110))
BATCH_API = "".join(chr(code) for code in (89, 120, 66, 97, 116, 99, 104))
ROOM_API = "".join(chr(code) for code in (83, 116, 117, 100, 101, 110, 116, 82, 111, 111, 109))
SETTING_API = "Setting"
CFG = "grabber_config.json"
MAX_ATTEMPTS = 3000
RETRY_INTERVAL = 0.12


def service_api_path(path: str) -> str:
    return f"{_API_ROOT}/{str(path or '').strip('/')}"


def auth_api_path(action: str) -> str:
    return service_api_path(f"{AUTH_API}/{str(action or '').strip('/')}")


def batch_api_path(action: str) -> str:
    return service_api_path(f"{BATCH_API}/{str(action or '').strip('/')}")


def room_api_path(action: str) -> str:
    return service_api_path(f"{ROOM_API}/{str(action or '').strip('/')}")


def setting_api_path(action: str) -> str:
    return service_api_path(f"{SETTING_API}/{str(action or '').strip('/')}")


def service_view_path(fragment: str = "") -> str:
    return f"{_VIEW_ROOT}{fragment.lstrip('/')}"

ROOM_PREF_OPTIONS = ("四人寝、八人寝", "四人寝", "八人寝", "不限")
_ROOM_PREF_TO_IDS = {
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
_IDS_TO_ROOM_PREF = {
    "1,2": "四人寝、八人寝",
    "1": "四人寝",
    "2": "八人寝",
    "": "不限",
}


def normalize_room_preference(pref) -> str:
    if isinstance(pref, str):
        pref = pref.strip()
    return _ROOM_PREF_TO_IDS.get(pref, "")


def room_preference_label(pref) -> str:
    return _IDS_TO_ROOM_PREF.get(normalize_room_preference(pref), "不限")


def pref_ids(pref) -> set[str]:
    normalized = normalize_room_preference(pref)
    return {p for p in normalized.split(",") if p}


def extract_openid_like(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    for name in ("openid", "wxopid"):
        patterns = [
            rf"[?&]{name}=([^&#\s]+)",
            rf'"{name}"\s*:\s*"([^"]+)"',
            rf"'{name}'\s*:\s*'([^']+)'",
            rf"{name}\s*[:=]\s*([A-Za-z0-9_\-\.]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return unquote(match.group(1).strip())
    if re.fullmatch(r"[A-Za-z0-9_\-\.]{12,80}", text):
        return text
    return ""


def is_probably_wxopid(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith("wxce") or lowered.startswith("wx"):
        return False
    return bool(re.fullmatch(r"o[A-Za-z0-9_\-\.]{12,79}", text))


def friendly_error(exc) -> str:
    text = str(exc).strip()
    if not text:
        return "操作失败，请查看运行日志。"
    if "Object reference not set to an instance of an object" in text:
        return "登录接口返回后端空引用：当前 openid / wxopid 不能换取有效登录态。请重新扫码获取新的 wxopid，或确认该账号已绑定身份信息。"
    if "身份认证失败" in text or "401" in text:
        return "身份认证失败：Token 未获取、已过期，或当前 openid 不能登录目标服务。请重新同步或重新扫码。"
    if "40163" in text:
        return "二维码 code 已使用或过期，请重新扫码。"
    if "Read timed out" in text or "timeout" in text.lower():
        return "服务器响应超时，请稍后重试。"
    if "Connection" in text or "connect" in text.lower():
        return "无法连接服务器，请检查网络。"
    if len(text) > 180:
        return text[:177] + "..."
    return text


def deep_get(obj, *keys):
    if obj is None:
        return None
    if isinstance(obj, dict):
        for key in keys:
            value = obj.get(key)
            if value not in (None, ""):
                return value
        for nested in ("result", "data", "Data", "Result"):
            value = obj.get(nested)
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except Exception:
                    value = None
            if isinstance(value, (dict, list)):
                found = deep_get(value, *keys)
                if found not in (None, ""):
                    return found
    if isinstance(obj, list):
        for item in obj:
            found = deep_get(item, *keys)
            if found not in (None, ""):
                return found
    return None


def extract_token(data):
    token = deep_get(data, "TokenContent", "token", "access_token")
    if token:
        return str(token)
    access_token = deep_get(data, "AccessToken")
    if isinstance(access_token, dict):
        token = deep_get(access_token, "TokenContent", "token", "access_token")
        return str(token) if token else ""
    return str(access_token) if access_token else ""


def make_session(token=""):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) MicroMessenger/8.0.43",
        "Referer": f"{BASE}{service_view_path()}",
    })
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    return session


def request_json(session, path, method="get", **kwargs):
    response = session.request(method, f"{BASE}{path}", timeout=10, **kwargs)
    response.raise_for_status()
    try:
        return response.json()
    except Exception:
        response.encoding = "gbk"
        return json.loads(response.text)


def normalize_backend_message(message, context="接口"):
    text = str(message or "").strip()
    if text in ("失败", "False", "false", "None", "null"):
        return ""
    if "Object reference not set to an instance of an object" in text:
        return f"{context}返回后端空引用：当前 openid / wxopid 无法换取有效登录态。请重新扫码获取新的 wxopid，或确认账号已绑定身份信息。"
    if "身份认证失败" in text:
        return f"{context}身份认证失败：Token 未获取、已过期，或当前 openid 不能登录目标服务。"
    return text


def api_message(data, fallback="接口返回异常", context="接口"):
    if isinstance(data, dict):
        raw = data.get("msg") or data.get("ErrorReason") or data.get("message") or fallback
        return normalize_backend_message(raw, context) or fallback
    return fallback


def is_success(data):
    return isinstance(data, dict) and data.get("code") == 1


def analyze_order_response(data):
    if not isinstance(data, dict):
        return False, "", "", "下单接口返回格式异常"
    code = data.get("code")
    message = data.get("msg") or data.get("ErrorReason") or data.get("message") or ""
    if code == -1:
        return False, "", "", message or "服务器拒绝下单"
    order_id = deep_get(data, "order_id", "orderid", "OrderId", "id", "OrderNo") or ""
    pay_url = deep_get(data, "pay_url", "payUrl", "PayUrl", "url", "Url") or ""
    success_signal = code in (None, 1, 0) and not any(s in str(message) for s in ("失败", "错误", "未开放"))
    if success_signal or order_id or pay_url:
        return True, str(order_id), str(pay_url), message or "已提交订单"
    return False, "", "", message or "未能创建订单"


def default_config():
    return {"accounts": [], "open_time": "", "pref": "1,2", "mask_sensitive": True}


def load_cfg(path=CFG):
    if not os.path.exists(path):
        return default_config()
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception:
        try:
            shutil.copy2(path, path + ".corrupted.bak")
        except Exception:
            pass
        return default_config()
    if not isinstance(data, dict):
        return default_config()
    if "accounts" not in data:
        data = {"accounts": [], "open_time": data.get("open_time", ""), "pref": data.get("pref", "1,2")}
    data.setdefault("open_time", "")
    data.setdefault("pref", "1,2")
    data.setdefault("accounts", [])
    data.setdefault("mask_sensitive", True)
    return data


def save_cfg(data, path=CFG):
    tmp = path + ".tmp"
    try:
        if os.path.exists(path):
            shutil.copy2(path, path + ".bak")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


@dataclass
class Account:
    openid: str = ""
    nickname: str = ""
    tag: str = ""
    college: str = ""
    class_name: str = ""
    student_id: str = ""
    user_id: str = ""
    user_role: str = ""
    user_host: str = ""
    control_scope: str = ""
    token: str = ""
    batch_open: bool = False
    start_time: str = ""
    end_time: str = ""
    uid: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @classmethod
    def from_dict(cls, data):
        return cls(
            openid=extract_openid_like(data.get("openid", "")),
            nickname=data.get("nickname", ""),
            tag=data.get("tag", ""),
            college=data.get("college", ""),
            class_name=data.get("class_name", ""),
            student_id=data.get("student_id", ""),
            user_id=data.get("user_id", ""),
            user_role=data.get("user_role", ""),
            user_host=data.get("user_host", ""),
            control_scope=data.get("control_scope", ""),
            token=data.get("token", ""),
            batch_open=bool(data.get("batch_open", False)),
            start_time=data.get("start_time", ""),
            end_time=data.get("end_time", ""),
            uid=data.get("uid") or uuid.uuid4().hex[:8],
        )

    def to_dict(self):
        return {
            "openid": self.openid,
            "nickname": self.nickname,
            "tag": self.tag,
            "college": self.college,
            "class_name": self.class_name,
            "student_id": self.student_id,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "user_host": self.user_host,
            "control_scope": self.control_scope,
            "batch_open": self.batch_open,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "uid": self.uid,
        }

    @property
    def display_name(self):
        return self.nickname or self.student_id or (self.openid[:10] + "..." if self.openid else "未命名账号")


class GrabberEngine:
    def __init__(self, account: Account, msg_queue: queue.Queue):
        self.account = account
        self.queue = msg_queue
        self.session = make_session()
        self.stop_event = threading.Event()
        self.thread = None
        self.running = False

    def emit(self, kind, data=None, color=None):
        self.queue.put((self.account.uid, kind, data, color))

    def check_auto_login(self):
        data = request_json(
            make_session(),
            auth_api_path("IsAutoLogin"),
            params={"wxopid": self.account.openid},
        )
        return is_success(data) and bool(data.get("result")), data

    def login(self):
        if not self.account.openid:
            raise RuntimeError("账号缺少 openid")
        self.emit("status", "正在登录")
        data = request_json(
            self.session,
            auth_api_path("LoginByopenid"),
            params={"wxopid": self.account.openid},
        )
        if data.get("code") != 1:
            raise RuntimeError(api_message(data, "登录失败，请确认 openid 是否有效", "登录接口"))
        token = extract_token(data)
        if not token:
            raise RuntimeError("登录成功但未返回 TokenContent")
        self.account.token = token
        self.session = make_session(token)
        self.emit("log", "登录成功，访问令牌已刷新", "success")
        return data

    def fetch_student_info(self):
        self.emit("status", "正在同步身份信息")
        data = request_json(self.session, batch_api_path("GetStepDetailByStudentId"))
        if data.get("code") != 1:
            raise RuntimeError(api_message(data, "身份信息获取失败", "身份信息接口"))
        result = data.get("result") or {}
        info = result.get("student_info") or result.get("StudentInfo") or {}
        self.account.student_id = str(info.get("UserCard") or info.get("student_id") or self.account.student_id or "")
        self.account.nickname = str(info.get("Name") or self.account.nickname or "")
        self.account.college = str(info.get("DepartmentName") or self.account.college or "")
        self.account.class_name = str(info.get("ClassName") or self.account.class_name or "")
        self.account.user_id = str(info.get("UserId") or info.get("id") or self.account.user_id or "")
        self.account.user_role = str(info.get("UserRoles") or info.get("UserRolesIdentify") or self.account.user_role or "")
        self.account.user_host = str(info.get("UserHost") or self.account.user_host or "")
        self.account.control_scope = str(info.get("ControlScope") or self.account.control_scope or "")
        self.account.batch_open = bool(result.get("batch_open"))
        self.account.start_time = str(result.get("start_time") or "")
        self.account.end_time = str(result.get("end_time") or "")
        self.emit("student", self.account)
        self.emit("log", f"身份信息已同步：{self.account.display_name}", "success")
        return data

    def fetch_rooms(self):
        self.emit("status", "正在读取资源")
        data = request_json(self.session, room_api_path("GetRoomCosts"))
        if data.get("code") != 1:
            raise RuntimeError(api_message(data, "资源获取失败", "资源接口"))
        rooms = data.get("result") or []
        if not isinstance(rooms, list):
            rooms = []
        self.emit("rooms", rooms)
        self.emit("log", f"资源已刷新：{len(rooms)} 条", "info")
        return rooms

    def preflight_network(self, pref=""):
        def worker():
            payload = {
                "auto_login": False,
                "token": False,
                "student": False,
                "batch_open": False,
                "start_time": "",
                "end_time": "",
                "rooms_count": 0,
                "matched": False,
                "pref_label": room_preference_label(pref),
                "checks": [],
            }

            def add_check(label, ok, detail=""):
                payload["checks"].append({"label": label, "ok": bool(ok), "detail": str(detail or "")})

            try:
                self.emit("status", "体检中")
                self.emit("log", "开始真实接口体检：自动登录、Token、身份信息、批次、资源。", "info")
                auto_ok, auto_data = self.check_auto_login()
                payload["auto_login"] = auto_ok
                add_check("自动登录", auto_ok, "wxopid 可自动登录" if auto_ok else api_message(auto_data, "wxopid 不可自动登录"))

                login_data = self.login()
                payload["token"] = bool(self.account.token)
                expires = deep_get(login_data, "Expires") or ""
                add_check("Token", payload["token"], f"已获取访问令牌，过期时间 {expires}" if expires else "已获取访问令牌")

                self.fetch_student_info()
                payload["student"] = True
                payload["batch_open"] = self.account.batch_open
                payload["start_time"] = self.account.start_time
                payload["end_time"] = self.account.end_time
                add_check("身份信息", True, f"{self.account.college or '组织未知'} · {self.account.student_id or '编号未知'}")
                batch_detail = f"{self.account.start_time or '未知'} 至 {self.account.end_time or '未知'}"
                add_check("选床批次", self.account.batch_open, ("已开放，" if self.account.batch_open else "未开放，") + batch_detail)

                rooms = self.fetch_rooms()
                payload["rooms_count"] = len(rooms)
                match = self.pick_room(rooms, pref)
                payload["matched"] = bool(match)
                add_check("资源数量", len(rooms) > 0, f"接口正常，当前返回 {len(rooms)} 条资源")
                add_check(
                    "偏好匹配",
                    bool(match) or not rooms,
                    "已找到匹配类型" if match else ("当前无资源可匹配" if not rooms else f"暂无 {room_preference_label(pref)} 可用类型"),
                )

                ok = payload["auto_login"] and payload["token"] and payload["student"]
                self.emit("preflight", payload, "success" if ok else "warning")
                self.emit("status", "体检完成")
            except Exception as exc:
                add_check("接口体检", False, friendly_error(exc))
                self.emit("preflight", payload, "error")
                self.emit("error", friendly_error(exc), "error")
                self.emit("log", traceback.format_exc(), "debug")

        threading.Thread(target=worker, daemon=True).start()

    def refresh_snapshot(self):
        def worker():
            try:
                auto_ok, auto_data = self.check_auto_login()
                if not auto_ok:
                    raise RuntimeError(api_message(auto_data, "自动登录未通过：openid / wxopid 可能已失效，请重新扫码。", "自动登录接口"))
                self.login()
                self.fetch_student_info()
                self.fetch_rooms()
                self.emit("status", "就绪")
            except Exception as exc:
                self.emit("error", friendly_error(exc), "error")
                self.emit("log", traceback.format_exc(), "debug")

        threading.Thread(target=worker, daemon=True).start()

    def rehearse(self, pref=""):
        def worker():
            try:
                self.emit("status", "演练中")
                self.emit("log", "开始演练：只检查登录、身份信息、资源和偏好匹配，不会提交。", "info")
                self.login()
                self.fetch_student_info()
                rooms = self.fetch_rooms()
                match = self.pick_room(rooms, pref)
                payload = {
                    "rooms_count": len(rooms),
                    "matched": bool(match),
                    "room": match or {},
                    "pref_label": room_preference_label(pref),
                    "batch_open": self.account.batch_open,
                    "start_time": self.account.start_time,
                    "end_time": self.account.end_time,
                }
                self.emit("rehearsal", payload, "success" if match else "warning")
                self.emit("status", "演练完成")
            except Exception as exc:
                self.emit("error", friendly_error(exc), "error")
                self.emit("log", traceback.format_exc(), "debug")

        threading.Thread(target=worker, daemon=True).start()

    def start_grab(self, open_time="", pref=""):
        if self.running:
            self.emit("log", "任务已经在运行", "warning")
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._grab_worker, args=(open_time, pref), daemon=True)
        self.thread.start()

    def stop_grab(self):
        self.stop_event.set()
        self.emit("status", "正在停止")
        self.emit("log", "已请求停止任务", "warning")

    def wait_until_open(self, open_time):
        if not open_time:
            return
        try:
            target = datetime.strptime(open_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise RuntimeError("定时格式应为 YYYY-MM-DD HH:MM:SS")
        while not self.stop_event.is_set():
            remain = (target - datetime.now()).total_seconds()
            if remain <= 0:
                return
            self.emit("status", f"等待开放 T-{int(remain)}s")
            time.sleep(min(1, max(0.1, remain)))

    def pick_room(self, rooms, pref):
        ids = pref_ids(pref)
        candidates = []
        for room in rooms:
            rid = str(room.get("room_type_id") or room.get("roomTypeId") or "")
            beds = int(room.get("room_bed_num") or room.get("room_bed_count") or room.get("bed_num") or 0)
            if ids and rid not in ids:
                continue
            if beds <= 0:
                continue
            candidates.append(room)
        return candidates[0] if candidates else None

    def create_order(self, room):
        payload = {
            "student_id": self.account.student_id,
            "room_type_id": room.get("room_type_id"),
            "room_type": room.get("room_type"),
            "need_pay_money": room.get("room_charge"),
        }
        self.emit("status", "正在提交订单")
        data = request_json(self.session, room_api_path("CreateRoomOrder"), method="post", json=payload)
        ok, order_id, pay_url, msg = analyze_order_response(data)
        if not ok:
            raise RuntimeError(msg)
        if not pay_url:
            pay_data = request_json(self.session, room_api_path("GetPayUrl"), params={"order_id": order_id})
            pay_url = str(deep_get(pay_data, "pay_url", "payUrl", "PayUrl", "url", "Url") or "")
        return order_id, pay_url, msg

    def _grab_worker(self, open_time, pref):
        self.running = True
        self.emit("running", True)
        try:
            self.login()
            self.fetch_student_info()
            self.wait_until_open(open_time)
            if self.stop_event.is_set():
                return
            self.emit("log", f"开始任务：偏好 {room_preference_label(pref)}", "info")
            for attempt in range(1, MAX_ATTEMPTS + 1):
                if self.stop_event.is_set():
                    break
                self.emit("attempts", attempt)
                rooms = self.fetch_rooms()
                room = self.pick_room(rooms, pref)
                if room:
                    order_id, pay_url, msg = self.create_order(room)
                    self.emit("payment", {"room": room, "order_id": order_id, "pay_url": pay_url, "message": msg})
                    self.emit("status", "已锁定资源")
                    self.emit("log", "已创建确认单，请尽快处理", "success")
                    return
                self.emit("status", f"监控中，第 {attempt} 次")
                time.sleep(RETRY_INTERVAL)
            if self.stop_event.is_set():
                self.emit("status", "已停止")
            else:
                self.emit("status", "未抢到")
                self.emit("log", f"已尝试 {MAX_ATTEMPTS} 次，未发现可用资源", "warning")
        except Exception as exc:
            self.emit("error", friendly_error(exc), "error")
            self.emit("log", traceback.format_exc(), "debug")
        finally:
            self.running = False
            self.emit("running", False)


def run_real_smoke(wxopid: str, output_path: str = "exe_smoke_result.json") -> dict:
    result = {}
    try:
        session = make_session()
        login = request_json(session, auth_api_path("LoginByopenid"), params={"wxopid": wxopid})
        token = extract_token(login)
        result["login"] = {
            "code": login.get("code"),
            "msg": api_message(login, "登录接口未返回明确原因", "登录接口"),
            "token_present": bool(token),
            "token_type": type(token).__name__,
        }
        if not token:
            raise RuntimeError(result["login"]["msg"] or "登录接口没有返回 Token")

        session = make_session(token)
        student = request_json(session, batch_api_path("GetStepDetailByStudentId"))
        result["student"] = {
            "code": student.get("code"),
            "msg": api_message(student, "身份信息接口未返回明确原因", "身份信息接口"),
            "has_result": bool(student.get("result")),
        }

        rooms_data = request_json(session, room_api_path("GetRoomCosts"))
        rooms = rooms_data.get("result") or []
        result["rooms"] = {
            "code": rooms_data.get("code"),
            "msg": api_message(rooms_data, "资源接口未返回明确原因", "资源接口"),
            "count": len(rooms) if isinstance(rooms, list) else 0,
        }
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result
