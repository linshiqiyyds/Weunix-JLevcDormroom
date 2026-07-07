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
PAYMENT_FAST_POLL_INTERVAL = 1.0
PAYMENT_FAST_POLL_SECONDS = 30
PAYMENT_POLL_INTERVAL = 3.0
PAYMENT_POLL_SECONDS = 360
BLACKBOX_DIR = os.path.join("output", "blackbox")
ROOM_TYPE_ID_KEYS = ("room_type_id", "roomTypeId", "room_typeid", "roomTypeID", "type_id", "typeId", "id")
ROOM_TYPE_KEYS = ("room_type", "roomType", "room_type_name", "roomTypeName", "type_name", "typeName", "name", "title")
ROOM_BED_KEYS = ("room_bed_num", "room_bed_count", "roomBedNum", "roomBedCount", "bed_num", "bedNum", "remain", "surplus", "left_count", "available_count", "count")
ROOM_CHARGE_KEYS = ("room_charge", "roomCharge", "charge", "price", "amount", "money", "need_pay_money", "pay_money")


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

ROOM_PREF_OPTIONS = ("4人间、8人间", "4人间", "8人间", "不限")
_ROOM_PREF_TO_IDS = {
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
_IDS_TO_ROOM_PREF = {
    "1,2": "4人间、8人间",
    "1": "4人间",
    "2": "8人间",
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


def first_present(data, *keys):
    if not isinstance(data, dict):
        return None
    lower_map = {str(key).lower(): key for key in data.keys()}
    for key in keys:
        if key in data and data.get(key) not in (None, ""):
            return data.get(key)
        actual = lower_map.get(str(key).lower())
        if actual is not None and data.get(actual) not in (None, ""):
            return data.get(actual)
    return None


def iter_text_values(data, keys=None):
    if not isinstance(data, dict):
        return
    source_keys = keys or tuple(data.keys())
    for key in source_keys:
        value = first_present(data, key)
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
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text):
        return normalize_money_value(float(text))
    return text


def parse_money_from_text(text):
    return normalize_money_value(text)


def canonical_room_type(text) -> str:
    value = str(text or "").strip()
    if any(mark in value for mark in ("4人", "四人")):
        return "4人间"
    if any(mark in value for mark in ("8人", "八人")):
        return "8人间"
    return value


def room_type_id_value(room) -> str:
    value = first_present(room, *ROOM_TYPE_ID_KEYS)
    return str(value or "").strip()


def room_type_text(room) -> str:
    value = first_present(room, *ROOM_TYPE_KEYS)
    return canonical_room_type(str(value or "").strip())


def room_charge_value(room):
    direct = first_present(room, *ROOM_CHARGE_KEYS)
    parsed = normalize_money_value(direct)
    if parsed:
        return parsed
    for text in iter_text_values(room, ROOM_TYPE_KEYS):
        parsed = parse_money_from_text(text)
        if parsed and parsed != text:
            return parsed
    return ""


def room_charge_number(room):
    value = room_charge_value(room)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def room_bed_count_value(room):
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


def room_matches_preference(room, pref) -> bool:
    ids = pref_ids(pref)
    if not ids or ids == {"1", "2"}:
        return True
    rid = room_type_id_value(room)
    label = room_type_text(room)
    if rid and rid in ids:
        return True
    if "1" in ids and any(mark in label for mark in ("4", "四")):
        return True
    if "2" in ids and any(mark in label for mark in ("8", "八")):
        return True
    return False


def normalize_room_for_order(room):
    return {
        "room_type_id": room_type_id_value(room),
        "room_type": room_type_text(room),
        "room_charge": room_charge_value(room),
    }


def find_first_list(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ("result", "data", "rows", "list", "items", "records", "Data", "Result"):
            value = obj.get(key)
            found = find_first_list(value)
            if isinstance(found, list):
                return found
        for value in obj.values():
            found = find_first_list(value)
            if isinstance(found, list):
                return found
    return []


def mask_blackbox_value(value, key=""):
    lowered = str(key or "").lower()
    sensitive = (
        lowered in {"name", "student_name", "username", "user_name"}
        or any(part in lowered for part in ("openid", "wxopid", "token", "usercard", "id_number", "phone", "mobile", "card"))
    )
    if isinstance(value, dict):
        return {k: mask_blackbox_value(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_blackbox_value(item, key) for item in value[:20]]
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            return "<url>"
        if sensitive and len(value) > 8:
            return f"{value[:3]}...{value[-3:]}"
        if len(value) > 240:
            return value[:237] + "..."
    return value


def write_blackbox_snapshot(account_uid, event, payload):
    try:
        os.makedirs(BLACKBOX_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        safe_event = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(event or "event")).strip("_") or "event"
        safe_uid = re.sub(r"[^A-Za-z0-9_.-]+", "", str(account_uid or "global"))[:16] or "global"
        path = os.path.join(BLACKBOX_DIR, f"{stamp}_{safe_uid}_{safe_event}.json")
        data = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "event": safe_event,
            "account_uid": safe_uid,
            "payload": mask_blackbox_value(payload),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path
    except Exception:
        return ""


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


def extract_order_id(data):
    if isinstance(data, dict):
        order_id = deep_get(data, "order_id", "orderid", "OrderId", "OrderNo", "id")
        if order_id not in (None, ""):
            return str(order_id)
        result = data.get("result") or data.get("data") or data.get("Data") or data.get("Result")
        if isinstance(result, (str, int)) and str(result).strip():
            return str(result).strip()
        if isinstance(result, dict):
            nested = deep_get(result, "order_id", "orderid", "OrderId", "OrderNo", "id")
            return str(nested) if nested not in (None, "") else ""
    if isinstance(data, (str, int)) and str(data).strip():
        return str(data).strip()
    return ""


def extract_pay_url(data):
    if isinstance(data, str):
        text = data.strip()
        return text if text.startswith(("http://", "https://")) else ""
    if isinstance(data, dict):
        pay_url = deep_get(data, "pay_url", "payUrl", "PayUrl", "url", "Url", "pay_links")
        if pay_url:
            return str(pay_url)
        result = data.get("result") or data.get("data") or data.get("Data") or data.get("Result")
        if isinstance(result, str) and result.strip().startswith(("http://", "https://")):
            return result.strip()
        if isinstance(result, dict):
            return extract_pay_url(result)
    return ""


def coerce_int(value, default=None):
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def payment_state(record, has_order=False):
    if not isinstance(record, dict):
        return ("pending", "等待付款") if has_order else ("waiting", "等待订单")
    status = str(record.get("pay_status") if record.get("pay_status") is not None else "").strip()
    rest_seconds = coerce_int(record.get("rest_seconds"))
    if status == "1":
        return "paid", "支付成功"
    if status == "0":
        if rest_seconds is not None and rest_seconds <= 0:
            return "expired", "订单已过期"
        return "pending", "待支付"
    return "unknown", "状态未知"


def payment_record_payload(record=None, room=None, order_id="", pay_url="", message=""):
    record = record if isinstance(record, dict) else {}
    room = room if isinstance(room, dict) else {}
    order_id = str(record.get("id") or order_id or "")
    pay_url = extract_pay_url(record) or str(pay_url or "")
    state, label = payment_state(record if record else None, bool(order_id or pay_url))
    rest_seconds = coerce_int(record.get("rest_seconds"))
    return {
        "room": room,
        "order_id": order_id,
        "pay_url": pay_url,
        "message": message,
        "payment_state": state,
        "state_label": label,
        "pay_status": record.get("pay_status"),
        "rest_seconds": rest_seconds,
        "paid": state == "paid",
        "expired": state == "expired",
        "room_type": record.get("room_type") or room.get("room_type") or room.get("roomType") or room_type_text(room),
        "need_pay_money": record.get("need_pay_money") or room_charge_value(room),
        "pay_money": record.get("pay_money") or "",
        "order_create_time": record.get("order_create_time") or "",
        "order_end_time": record.get("order_end_time") or "",
        "pay_time": record.get("pay_time") or "",
        "valid_duration": coerce_int(record.get("valid_duration")),
        "room_no": record.get("room_no") or "",
        "bed_no": record.get("bed_no") or "",
        "bed_id": record.get("bed_id") or "",
    }


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
        order_id = extract_order_id(data)
        pay_url = extract_pay_url(data)
        if order_id or pay_url:
            return True, order_id, pay_url, "订单已创建"
        return False, "", "", "下单接口返回格式异常"
    code = data.get("code")
    message = data.get("msg") or data.get("ErrorReason") or data.get("message") or ""
    if code == -1:
        return False, "", "", message or "服务器拒绝下单"
    order_id = extract_order_id(data)
    pay_url = extract_pay_url(data)
    success_signal = code in (None, 1, 0) and not any(s in str(message) for s in ("失败", "错误", "未开放"))
    if success_signal or order_id or pay_url:
        return True, str(order_id or ""), str(pay_url or ""), message or "已提交订单"
    return False, "", "", message or "未能创建订单"


def default_config():
    return {"accounts": [], "open_time": "", "pref": "1", "mask_sensitive": True}


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
        data = {"accounts": [], "open_time": data.get("open_time", ""), "pref": data.get("pref", "1")}
    data.setdefault("open_time", "")
    data.setdefault("pref", "1")
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

    def record_blackbox(self, event, payload):
        threading.Thread(target=write_blackbox_snapshot, args=(self.account.uid, event, payload), daemon=True).start()

    def fetch_rooms(self, quiet=False):
        if not quiet:
            self.emit("status", "正在读取资源")
        data = request_json(self.session, room_api_path("GetroomCosts"))
        if data.get("code") != 1:
            data = request_json(self.session, room_api_path("GetRoomCosts"))
        if data.get("code") != 1:
            raise RuntimeError(api_message(data, "资源获取失败", "资源接口"))
        rooms = find_first_list(data)
        if not isinstance(rooms, list):
            rooms = []
        if rooms:
            self.record_blackbox("rooms_nonzero", {"count": len(rooms), "raw": data, "normalized": [normalize_room_for_order(room) for room in rooms[:10] if isinstance(room, dict)]})
        if not quiet or rooms:
            self.emit("rooms", rooms)
        if not quiet or rooms:
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
                snapshot = self.payment_snapshot(message="订单状态已同步")
                if snapshot.get("order_id"):
                    self.emit("payment", snapshot)
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
            if remain <= 2:
                time.sleep(min(0.05, max(0.005, remain)))
            else:
                time.sleep(min(0.5, max(0.05, remain)))

    def pick_room(self, rooms, pref):
        candidates = []
        for room in rooms:
            if not isinstance(room, dict):
                continue
            beds = room_bed_count_value(room)
            if beds is not None and beds <= 0:
                continue
            candidates.append(room)
            if not room_matches_preference(room, pref):
                continue
            return room
        ids = pref_ids(pref)
        priced = [(room_charge_number(room), room) for room in candidates]
        priced = [(price, room) for price, room in priced if price is not None]
        if len({price for price, _ in priced}) >= 2:
            priced.sort(key=lambda item: item[0])
            if ids == {"1"}:
                return priced[-1][1]
            if ids == {"2"}:
                return priced[0][1]
        return candidates[0] if candidates and (not ids or ids == {"1", "2"}) else None

    def order_student_id(self):
        return str(self.account.user_id or self.account.student_id or "").strip()

    def fetch_pay_records(self):
        student_id = self.order_student_id()
        if not student_id:
            return []
        data = request_json(self.session, room_api_path("Get_PayRecord"), params={"student_id": student_id})
        if data.get("code") != 1:
            return []
        records = data.get("result") or []
        return records if isinstance(records, list) else []

    def latest_unpaid_order(self):
        records = self.fetch_pay_records()
        for record in records:
            if isinstance(record, dict) and str(record.get("pay_status")) == "0":
                return record
        return None

    def find_payment_record(self, records, order_id=""):
        if not isinstance(records, list):
            return None
        order_id = str(order_id or "")
        if order_id:
            for record in records:
                if isinstance(record, dict) and str(record.get("id") or "") == order_id:
                    return record
        for record in records:
            if isinstance(record, dict) and str(record.get("pay_status")) == "0":
                return record
        return next((record for record in records if isinstance(record, dict)), None)

    def resolve_pay_url(self, order_id):
        if not order_id:
            return ""
        data = request_json(self.session, room_api_path("GetPayUrl"), params={"orderno": order_id})
        return extract_pay_url(data)

    def payment_snapshot(self, order_id="", room=None, pay_url="", message=""):
        records = self.fetch_pay_records()
        record = self.find_payment_record(records, order_id)
        payload = payment_record_payload(record, room, order_id, pay_url, message)
        payload["records_count"] = len(records) if isinstance(records, list) else 0
        return payload

    def watch_payment_status(self, order_id="", room=None, pay_url="", message=""):
        started = time.monotonic()
        deadline = time.monotonic() + PAYMENT_POLL_SECONDS
        self.emit("log", "已停止抢单请求，进入支付追踪：前 30 秒快速确认，之后低频轮询。", "info")
        while not self.stop_event.is_set():
            payload = self.payment_snapshot(order_id, room, pay_url, message)
            self.emit("payment", payload)
            state = payload.get("payment_state")
            if state == "paid":
                self.emit("status", "支付成功")
                detail = f"{payload.get('room_no') or '房间待同步'} · {payload.get('bed_no') or '床位待同步'}"
                self.emit("log", f"支付已确认：{detail}", "success")
                return
            if state == "expired":
                self.emit("status", "订单已过期")
                self.emit("log", "订单未在有效期内完成支付，已过期；如仍需选择，请重新启动任务。", "warning")
                return
            if time.monotonic() >= deadline:
                self.emit("status", "等待支付确认超时")
                self.emit("log", "已停止自动轮询支付状态；如已付款，请点击同步刷新订单结果。", "warning")
                return
            rest = payload.get("rest_seconds")
            if isinstance(rest, int) and rest > 0:
                self.emit("status", f"待支付，剩余 {rest}s")
            elif payload.get("pay_url"):
                self.emit("status", "待支付，等待完成付款")
            else:
                self.emit("status", "订单已创建，等待支付链接")
            interval = PAYMENT_FAST_POLL_INTERVAL if time.monotonic() - started < PAYMENT_FAST_POLL_SECONDS else PAYMENT_POLL_INTERVAL
            time.sleep(interval)

    def create_order(self, room):
        student_id = self.order_student_id()
        if not student_id:
            raise RuntimeError("缺少学生 UserId，无法创建订单。请先同步学生信息。")
        normalized_room = normalize_room_for_order(room)
        if not normalized_room["room_type_id"]:
            self.record_blackbox("room_structure_missing_id", {"source_room": room, "normalized": normalized_room})
            raise RuntimeError("房源结构缺少 room_type_id，已保存黑匣子快照，请检查开放瞬间返回。")
        payload = {
            "student_id": student_id,
            "room_type_id": normalized_room["room_type_id"],
            "room_type": normalized_room["room_type"],
            "need_pay_money": normalized_room["room_charge"],
        }
        self.record_blackbox("create_order_payload", {"payload": payload, "source_room": room})
        self.emit("status", "正在提交订单")
        data = request_json(self.session, room_api_path("CreateRoomOrder"), method="post", json=payload)
        self.record_blackbox("create_order_response", {"payload": payload, "response": data})
        ok, order_id, pay_url, msg = analyze_order_response(data)
        if not ok:
            raise RuntimeError(msg)
        unpaid = self.latest_unpaid_order()
        if unpaid:
            order_id = str(unpaid.get("id") or order_id or "")
            pay_url = extract_pay_url(unpaid) or pay_url
        if not pay_url:
            pay_url = self.resolve_pay_url(order_id)
        if not order_id and not pay_url:
            self.emit("log", "订单接口已返回成功，但未带订单号或支付链接。为避免重复提交，已停止抢单请求，请点击同步确认订单记录。", "warning")
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
                if attempt == 1 or attempt % 10 == 0:
                    self.emit("attempts", attempt)
                    self.emit("status", f"监控中，第 {attempt} 次")
                rooms = self.fetch_rooms(quiet=True)
                room = self.pick_room(rooms, pref)
                if room:
                    self.record_blackbox("selected_room", {"attempt": attempt, "room": room, "normalized": normalize_room_for_order(room), "pref": room_preference_label(pref)})
                    order_id, pay_url, msg = self.create_order(room)
                    self.emit("payment", self.payment_snapshot(order_id, room, pay_url, msg))
                    self.emit("status", "已锁定资源，停止抢单请求")
                    self.emit("log", "已创建确认单，不再继续提交抢单请求；请尽快扫码支付。", "success")
                    self.watch_payment_status(order_id, room, pay_url, msg)
                    return
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

        rooms_data = request_json(session, room_api_path("GetroomCosts"))
        if rooms_data.get("code") != 1:
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
