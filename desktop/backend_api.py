import json
import os
import queue
import select
import shutil
import socket
import sys
import threading
import time
from base64 import b64encode
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlparse

import qrcode
import requests

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only helper
    winreg = None

if os.environ.get("WEUNIX_WORKDIR"):
    ROOT = Path(os.environ["WEUNIX_WORKDIR"]).resolve()
elif getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parents[1]
ROOT.mkdir(parents=True, exist_ok=True)
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weunix_core import (  # noqa: E402
    Account,
    BASE,
    GrabberEngine,
    SERVICE_HOST,
    SERVICE_LABEL,
    api_message,
    auth_api_path,
    extract_openid_like,
    friendly_error,
    is_probably_wxopid,
    load_cfg,
    make_session,
    normalize_room_preference,
    request_json,
    room_preference_label,
    save_cfg,
    setting_api_path,
    service_view_path,
)


class OpidCaptureAssistant:
    def __init__(self, state):
        self.state = state
        self.lock = threading.RLock()
        self.httpd = None
        self.thread = None
        self.active = False
        self.port = 0
        self.started_at = ""
        self.last_url = ""
        self.last_target_url = ""
        self.captured_openid = ""
        self.imported_account = None
        self.error = ""
        self.proxy_backup = None
        self.upstream_proxy = ""
        self.mode = "idle"
        self.request_count = 0
        self.target_count = 0
        self.importing_openid = ""
        self.nickname = ""
        self.tag = ""

    def start(self, nickname="", tag="", mode="isolated"):
        if winreg is None:
            raise ValueError("自动取号助手仅支持 Windows 系统代理。")
        with self.lock:
            if self.active:
                if mode == "system" and self.proxy_backup is None:
                    self._enable_system_proxy(self.port)
                    self.mode = "system"
                    self.state.log("info", "自动取号助手已切换为临时接管系统代理。")
                return self.status()
            self.nickname = str(nickname or "").strip() or "扫码导入账号"
            self.tag = str(tag or "").strip() or "自动取号"
            self.error = ""
            self.captured_openid = ""
            self.imported_account = None
            self.last_url = ""
            self.last_target_url = ""
            self.request_count = 0
            self.target_count = 0
            self.importing_openid = ""
            self.upstream_proxy = self._current_system_proxy()
            self.mode = "system" if mode == "system" else "isolated"
            self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), OpidProxyHandler)
            self.httpd.assistant = self
            self.port = int(self.httpd.server_address[1])
            self.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if mode == "system":
                self._enable_system_proxy(self.port)
            self.active = True
            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()
            detail = "已临时接管系统代理" if mode == "system" else "独立监听，不修改系统代理"
            self.state.log("info", f"自动取号助手已启动：127.0.0.1:{self.port}，{detail}。")
            return self.status()

    def stop(self):
        with self.lock:
            self._stop_locked()
            return self.status()

    def _stop_locked(self):
        httpd = self.httpd
        was_active = self.active
        self.httpd = None
        self.thread = None
        self.active = False
        self.mode = "idle"
        try:
            self._restore_system_proxy()
        except Exception as exc:
            self.error = f"系统代理恢复失败：{exc}"
            self.state.log("error", self.error)
            raise
        if httpd:
            threading.Thread(target=self._shutdown_server, args=(httpd,), daemon=True).start()
        if was_active:
            self.state.log("info", "自动取号助手已停止，系统代理已恢复。")

    def _shutdown_server(self, httpd):
        try:
            httpd.shutdown()
        except Exception:
            pass
        try:
            httpd.server_close()
        except Exception:
            pass

    def status(self):
        with self.lock:
            return {
                "active": self.active,
                "port": self.port,
                "started_at": self.started_at,
                "last_url": self._mask_url(self.last_url),
                "last_target_url": self._mask_url(self.last_target_url),
                "captured_openid": self._mask(self.captured_openid),
                "captured_openid_raw": self.captured_openid,
                "imported": bool(self.imported_account),
                "account": self.imported_account,
                "error": self.error,
                "proxy_enabled": bool(self.proxy_backup is not None and self.active),
                "system_proxy_active": bool(self.proxy_backup is not None and self.active),
                "upstream_proxy": self.upstream_proxy,
                "mode": self.mode,
                "request_count": self.request_count,
                "target_count": self.target_count,
            }

    def on_request_url(self, url):
        parsed = urlparse(url)
        host = parsed.hostname or ""
        path = parsed.path or ""
        with self.lock:
            self.request_count += 1
            if host == SERVICE_HOST:
                self.last_target_url = url
                self.target_count += 1
        if host != SERVICE_HOST or f"{auth_api_path('')}/" not in path:
            return
        with self.lock:
            self.last_url = url
        openid = extract_openid_like(url)
        if not openid:
            return
        with self.lock:
            if self.importing_openid == openid:
                return
            if self.captured_openid == openid and self.imported_account:
                return
            self.captured_openid = openid
            self.importing_openid = openid
        self.state.log("success", f"自动取号助手已捕获 wxopid：{self._mask(openid)}")
        try:
            account = self.state.add_account(openid, self.nickname, self.tag, "")
            with self.lock:
                self.imported_account = account
                self.importing_openid = ""
            self.state.log("success", "自动取号助手已导入账号，并准备恢复系统代理。")
            threading.Thread(target=self.stop, daemon=True).start()
        except Exception as exc:
            message = str(exc)
            with self.lock:
                self.error = message
                self.importing_openid = ""
            if "已存在" in message:
                existing = self.state.find_account_by_openid(openid)
                if existing:
                    with self.lock:
                        self.imported_account = existing
                        self.error = ""
                    self.state.log("success", "自动取号助手捕获到已存在账号，已刷新账号列表并恢复系统代理。")
                else:
                    self.state.log("warning", "自动取号助手捕获到已存在账号，正在恢复系统代理。")
            else:
                self.state.log("error", f"自动取号助手导入失败：{message}")
            threading.Thread(target=self.stop, daemon=True).start()

    def _enable_system_proxy(self, port):
        backup = self._read_proxy_settings()
        self.upstream_proxy = self._proxy_from_settings(backup)
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"127.0.0.1:{port}")
            override = backup.get("ProxyOverride") or "<local>"
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, override)
        self.proxy_backup = backup
        self._refresh_proxy_settings()

    def _restore_system_proxy(self):
        if self.proxy_backup is None or winreg is None:
            return
        backup = self.proxy_backup
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            self._set_or_delete(key, "ProxyEnable", winreg.REG_DWORD, backup.get("ProxyEnable"))
            self._set_or_delete(key, "ProxyServer", winreg.REG_SZ, backup.get("ProxyServer"))
            self._set_or_delete(key, "ProxyOverride", winreg.REG_SZ, backup.get("ProxyOverride"))
        self.proxy_backup = None
        self._refresh_proxy_settings()

    def _read_proxy_settings(self):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        result = {}
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            for name in ("ProxyEnable", "ProxyServer", "ProxyOverride"):
                try:
                    result[name] = winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    result[name] = None
        return result

    def _current_system_proxy(self):
        if winreg is None:
            return ""
        return self._proxy_from_settings(self._read_proxy_settings())

    def _proxy_from_settings(self, settings):
        if not settings or int(settings.get("ProxyEnable") or 0) != 1:
            return ""
        proxy = str(settings.get("ProxyServer") or "").strip()
        if not proxy:
            return ""
        return proxy

    def requests_proxy(self):
        endpoint = self._proxy_endpoint(self.upstream_proxy)
        if not endpoint:
            return None
        host, port = endpoint
        if host in {"127.0.0.1", "localhost"} and int(port) == int(self.port or 0):
            return None
        proxy_url = f"http://{host}:{port}"
        return {"http": proxy_url, "https": proxy_url}

    def upstream_endpoint(self):
        endpoint = self._proxy_endpoint(self.upstream_proxy)
        if not endpoint:
            return None
        host, port = endpoint
        if host in {"127.0.0.1", "localhost"} and int(port) == int(self.port or 0):
            return None
        return endpoint

    def _proxy_endpoint(self, proxy):
        value = str(proxy or "").strip()
        if not value:
            return None
        parts = [part.strip() for part in value.split(";") if part.strip()]
        selected = ""
        for part in parts:
            if part.lower().startswith("https="):
                selected = part.split("=", 1)[1]
                break
        if not selected:
            for part in parts:
                if part.lower().startswith("http="):
                    selected = part.split("=", 1)[1]
                    break
        if not selected:
            selected = parts[0] if parts else value
            if "=" in selected:
                selected = selected.split("=", 1)[1]
        selected = selected.replace("http://", "").replace("https://", "").strip("/")
        host, sep, port = selected.partition(":")
        if not host or not sep:
            return None
        try:
            return host, int(port)
        except ValueError:
            return None

    def _set_or_delete(self, key, name, value_type, value):
        if value is None:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
            return
        winreg.SetValueEx(key, name, 0, value_type, value)

    def _refresh_proxy_settings(self):
        try:
            import ctypes
            internet = ctypes.windll.Wininet
            internet.InternetSetOptionW(0, 39, 0, 0)
            internet.InternetSetOptionW(0, 37, 0, 0)
        except Exception:
            pass

    def _mask(self, value):
        if not value:
            return ""
        return value[:8] + "..." + value[-5:] if len(value) > 14 else value[:4] + "..."

    def _mask_url(self, value):
        if not value:
            return ""
        openid = extract_openid_like(value)
        return value.replace(openid, self._mask(openid)) if openid else value


class OpidProxyHandler(BaseHTTPRequestHandler):
    timeout = 20

    def do_CONNECT(self):
        self._tunnel()

    def do_GET(self):
        self._forward_http()

    def do_POST(self):
        self._forward_http()

    def do_PUT(self):
        self._forward_http()

    def do_DELETE(self):
        self._forward_http()

    def do_OPTIONS(self):
        self._forward_http()

    def _forward_http(self):
        assistant = getattr(self.server, "assistant", None)
        url = self.path
        if not url.startswith(("http://", "https://")):
            host = self.headers.get("Host", "")
            url = f"http://{host}{self.path}"
        if assistant:
            assistant.on_request_url(url)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {
            key: value for key, value in self.headers.items()
            if key.lower() not in {"host", "proxy-connection", "connection", "keep-alive", "transfer-encoding"}
        }
        try:
            response = requests.request(
                self.command,
                url,
                data=body,
                headers=headers,
                timeout=20,
                allow_redirects=False,
                proxies=assistant.requests_proxy() if assistant else None,
            )
            self.send_response(response.status_code)
            for key, value in response.headers.items():
                if key.lower() in {"transfer-encoding", "connection", "content-encoding"}:
                    continue
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)
        except Exception:
            self.send_error(502, "WeUnix capture proxy forward failed")

    def _tunnel(self):
        host, _, port_text = self.path.partition(":")
        port = int(port_text or "443")
        remote = None
        try:
            upstream = getattr(getattr(self.server, "assistant", None), "upstream_endpoint", lambda: None)()
            if upstream:
                remote = socket.create_connection(upstream, timeout=15)
                connect_line = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\nProxy-Connection: keep-alive\r\n\r\n"
                remote.sendall(connect_line.encode("ascii", errors="ignore"))
                response = b""
                while b"\r\n\r\n" not in response and len(response) < 8192:
                    chunk = remote.recv(1024)
                    if not chunk:
                        break
                    response += chunk
                if b" 200 " not in response.split(b"\r\n", 1)[0]:
                    raise OSError("upstream proxy refused CONNECT")
            else:
                remote = socket.create_connection((host, port), timeout=15)
            self.send_response(200, "Connection Established")
            self.end_headers()
            sockets = [self.connection, remote]
            while True:
                readable, _, _ = select.select(sockets, [], [], 30)
                if not readable:
                    break
                for sock in readable:
                    data = sock.recv(8192)
                    if not data:
                        return
                    target = remote if sock is self.connection else self.connection
                    target.sendall(data)
        except Exception:
            try:
                self.send_error(502, "WeUnix capture proxy tunnel failed")
            except Exception:
                pass
        finally:
            if remote:
                try:
                    remote.close()
                except Exception:
                    pass

    def log_message(self, fmt, *args):
        return


class RuntimeState:
    def __init__(self):
        self.lock = threading.RLock()
        self.queue = queue.Queue()
        self.logs = []
        self.rooms = {}
        self.preflight = {}
        self.rehearsals = {}
        self.payments = {}
        self.attempts = {}
        self.statuses = {}
        self.running = {}
        self.cfg = load_cfg()
        self.pref = self.cfg.get("pref", "1,2")
        self.open_time = self.cfg.get("open_time", "")
        self.mask_sensitive = bool(self.cfg.get("mask_sensitive", True))
        raw_accounts = [Account.from_dict(a) for a in self.cfg.get("accounts", []) if a.get("openid")]
        self.accounts = [acc for acc in raw_accounts if is_probably_wxopid(acc.openid)]
        if len(self.accounts) != len(raw_accounts):
            self.log("warning", "已忽略 wxce/appid 等非 wxopid 账号，请重新扫码获取 o... 开头的 opid。")
            self.save()
        self.server_latency_ms = None
        self.last_ping_at = 0.0
        self.engines = {acc.uid: GrabberEngine(acc, self.queue) for acc in self.accounts}
        self.capture = OpidCaptureAssistant(self)
        self._closing = False
        threading.Thread(target=self._consume_events, daemon=True).start()

    def snapshot(self):
        with self.lock:
            return {
                "ok": True,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "base": SERVICE_LABEL,
                "open_time": self.open_time,
                "pref": self.pref,
                "pref_label": room_preference_label(self.pref),
                "mask_sensitive": self.mask_sensitive,
                "server_latency_ms": self.server_latency_ms,
                "capture": self.capture.status(),
                "accounts": [self._account_payload(acc) for acc in self.accounts],
                "logs": self.logs[-160:],
            }

    def _account_payload(self, acc):
        account_data = acc.to_dict()
        account_data.pop("user_host", None)
        account_data.pop("control_scope", None)
        return {
            **account_data,
            "display_name": acc.display_name,
            "running": bool(self.running.get(acc.uid)),
            "status": self.statuses.get(acc.uid, "运行中" if self.running.get(acc.uid) else "就绪"),
            "attempts": int(self.attempts.get(acc.uid, 0) or 0),
            "rooms": self.rooms.get(acc.uid, []),
            "preflight": self.preflight.get(acc.uid),
            "rehearsal": self.rehearsals.get(acc.uid),
            "payment": self.payments.get(acc.uid),
        }

    def save(self):
        with self.lock:
            save_cfg({
                "accounts": [a.to_dict() for a in self.accounts],
                "open_time": self.open_time,
                "pref": self.pref,
                "mask_sensitive": self.mask_sensitive,
            })

    def update_config(self, payload):
        open_time = str(payload.get("open_time", self.open_time) or "").strip()
        pref = normalize_room_preference(payload.get("pref", self.pref))
        mask_sensitive = payload.get("mask_sensitive", self.mask_sensitive)
        if open_time:
            try:
                datetime.strptime(open_time, "%Y-%m-%d %H:%M:%S")
            except ValueError as exc:
                raise ValueError("开放时间格式应为 YYYY-MM-DD HH:MM:SS") from exc
        with self.lock:
            self.open_time = open_time
            self.pref = pref
            self.mask_sensitive = bool(mask_sensitive)
            self.save()
            self.log("success", f"策略已保存：{room_preference_label(self.pref)} / {self.open_time or '立即'}")
            return self.snapshot()

    def add_account(self, raw_openid, nickname="", tag="", college=""):
        openid = extract_openid_like(raw_openid)
        if not openid:
            raise ValueError("未识别到有效 openid / wxopid")
        if not is_probably_wxopid(openid):
            raise ValueError("这不是可登录的 wxopid/opid。wxce... 是公众号 appid，不能用于自动登录；请粘贴 o... 开头的 opid，或粘贴带 code= 的微信回调链接让程序换取。")
        auto_data = request_json(make_session(), auth_api_path("IsAutoLogin"), params={"wxopid": openid})
        if not (auto_data.get("code") == 1 and bool(auto_data.get("result"))):
            raise ValueError(api_message(auto_data, "自动登录未通过：这个 opid 不能用于当前服务，请重新获取 o... 开头的 wxopid。", "自动登录接口"))
        with self.lock:
            if any(a.openid == openid for a in self.accounts):
                raise ValueError("账号已存在")
            acc = Account(openid=openid, nickname=nickname.strip(), tag=tag.strip(), college=college.strip())
            self.accounts.append(acc)
            self.engines[acc.uid] = GrabberEngine(acc, self.queue)
            self.save()
            self.log("success", f"已添加账号：{acc.display_name}")
            return self._account_payload(acc)

    def find_account_by_openid(self, raw_openid):
        openid = extract_openid_like(raw_openid)
        if not openid:
            return None
        with self.lock:
            account = next((acc for acc in self.accounts if acc.openid == openid), None)
            return self._account_payload(account) if account else None

    def update_account(self, uid, payload):
        with self.lock:
            account = next((acc for acc in self.accounts if acc.uid == uid), None)
            if not account:
                raise ValueError("账号不存在")
            if "nickname" in payload:
                account.nickname = str(payload.get("nickname") or "").strip()
            if "tag" in payload:
                account.tag = str(payload.get("tag") or "").strip()
            self.save()
            self.log("success", f"账号备注已更新：{account.display_name}")
            return self._account_payload(account)

    def remove_account(self, uid):
        with self.lock:
            engine = self.engines.pop(uid, None)
            if engine:
                engine.stop_grab()
            self.accounts = [a for a in self.accounts if a.uid != uid]
            self.rooms.pop(uid, None)
            self.preflight.pop(uid, None)
            self.rehearsals.pop(uid, None)
            self.payments.pop(uid, None)
            self.attempts.pop(uid, None)
            self.statuses.pop(uid, None)
            self.running.pop(uid, None)
            self.save()
            self.log("warning", f"已移除账号：{uid}")

    def refresh(self, uid):
        engine = self.engines.get(uid)
        if not engine:
            raise ValueError("账号不存在")
        self.log("info", f"开始同步：{engine.account.display_name}")
        engine.refresh_snapshot()

    def preflight_account(self, uid):
        engine = self.engines.get(uid)
        if not engine:
            raise ValueError("账号不存在")
        self.log("info", f"开始体检：{engine.account.display_name}")
        engine.preflight_network(self.pref)

    def rehearse_account(self, uid):
        engine = self.engines.get(uid)
        if not engine:
            raise ValueError("账号不存在")
        self.log("info", f"开始演练：{engine.account.display_name}")
        engine.rehearse(self.pref)

    def start_account(self, uid):
        engine = self.engines.get(uid)
        if not engine:
            raise ValueError("账号不存在")
        if engine.running:
            self.log("warning", f"{engine.account.display_name}: 任务已在运行")
            return
        self.log("info", f"启动任务：{engine.account.display_name}")
        engine.start_grab(self.open_time, self.pref)

    def stop_account(self, uid):
        engine = self.engines.get(uid)
        if not engine:
            raise ValueError("账号不存在")
        engine.stop_grab()

    def account_ids(self):
        with self.lock:
            return [acc.uid for acc in self.accounts]

    def action_all(self, action):
        ids = self.account_ids()
        if not ids:
            raise ValueError("没有可操作的账号")
        for uid in ids:
            if action == "refresh":
                self.refresh(uid)
            elif action == "preflight":
                self.preflight_account(uid)
            elif action == "rehearse":
                self.rehearse_account(uid)
            elif action == "start":
                self.start_account(uid)
            elif action == "stop":
                self.stop_account(uid)
        return {"count": len(ids)}

    def backup_config(self):
        self.save()
        source = ROOT / "grabber_config.json"
        if not source.exists():
            raise ValueError("当前还没有配置文件")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = ROOT / f"grabber_config.json.{stamp}.bak"
        shutil.copy2(source, target)
        self.log("success", f"配置已备份：{target.name}")
        return {"file": target.name}

    def restore_config(self):
        backup = ROOT / "grabber_config.json.bak"
        if not backup.exists():
            raise ValueError("未找到 grabber_config.json.bak")
        current = ROOT / "grabber_config.json"
        if current.exists():
            shutil.copy2(current, ROOT / "grabber_config.json.before-restore.bak")
        shutil.copy2(backup, current)
        with self.lock:
            self.cfg = load_cfg()
            for engine in self.engines.values():
                engine.stop_grab()
            self.accounts = [Account.from_dict(a) for a in self.cfg.get("accounts", []) if a.get("openid")]
            self.pref = self.cfg.get("pref", "1,2")
            self.open_time = self.cfg.get("open_time", "")
            self.mask_sensitive = bool(self.cfg.get("mask_sensitive", True))
            self.engines = {acc.uid: GrabberEngine(acc, self.queue) for acc in self.accounts}
            self.rooms.clear()
            self.preflight.clear()
            self.rehearsals.clear()
            self.payments.clear()
            self.attempts.clear()
            self.statuses.clear()
            self.running.clear()
        self.log("warning", "配置已从上一次备份恢复")
        return self.snapshot()

    def diagnostic(self, uid=""):
        with self.lock:
            acc = next((a for a in self.accounts if a.uid == uid), None) if uid else None
            preflight = self.preflight.get(uid) if uid else None
            payment = self.payments.get(uid) if uid else None
            status = self.statuses.get(uid, "待诊断") if uid else "全部账号"
            openid = self._mask(acc.openid) if acc else f"{len(self.accounts)} 个账号"
            result = "还没有运行记录，请先同步、体检或演练一次。"
            if payment:
                result = f"已创建订单：{payment.get('message') or payment.get('order_id') or '待支付'}"
            elif preflight:
                result = f"体检完成：资源 {preflight.get('rooms_count', 0)} 条，匹配={bool(preflight.get('matched'))}"
            elif status:
                result = status
            text = "；".join([
                f"账号：{acc.display_name if acc else '全部账号'}",
                f"标签：{acc.tag if acc else '无'}",
                f"openid：{openid}",
                f"步骤：{status}",
                f"结果：{result}",
                f"建议：{self._diagnostic_suggestion(result)}",
                f"开抢时间：{self.open_time or '立即'}",
                f"房型偏好：{room_preference_label(self.pref)}",
                f"服务器延迟：{self.server_latency_ms if self.server_latency_ms is not None else '--'} ms",
                f"诊断时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ])
        return {"text": text}

    def _diagnostic_suggestion(self, result):
        text = str(result or "")
        if "code" in text and ("过期" in text or "使用" in text):
            return "二维码 code 已使用或过期，请重新扫码获取。"
        if "Token" in text or "登录" in text or "认证" in text:
            return "重新同步账号，必要时重新扫码获取 wxopid。"
        if "资源 0" in text or "0 条" in text:
            return "接口正常但当前无可用资源，请等待开放或调整偏好。"
        if "超时" in text or "timeout" in text.lower():
            return "检查网络与代理，稍后重试。"
        return "先执行体检；如仍失败，把本诊断文本发给维护者。"

    def _mask(self, value):
        if not value or not self.mask_sensitive:
            return value or "未知"
        return value[:8] + "..." + value[-5:] if len(value) > 14 else value[:4] + "..."

    def resolve_wxcode(self, wxcode):
        data = request_json(make_session(), auth_api_path("GetWxOpenidByWxCode"), params={"wxcode": wxcode})
        if data.get("code") != 1:
            message = api_message(data, "wxcode 换取 openid 失败", "微信授权")
            if "40163" in json.dumps(data, ensure_ascii=False):
                message = "二维码 code 已使用或过期，请重新扫码。"
            raise ValueError(message)
        result = data.get("result") or {}
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                result = {"openid": result}
        openid = result.get("openid") or result.get("wxopid") or result.get("OpenId") or result.get("WxOpenId")
        openid = extract_openid_like(str(openid or ""))
        if not openid:
            raise ValueError("接口未返回可用 openid")
        if not is_probably_wxopid(openid):
            raise ValueError("微信接口返回的不是可登录 opid。wxce... 是 appid，不能用于自动登录；请确认复制的是带 code= 的回调链接，不是页面里的 result/appid。")
        return {"openid": openid, "raw": data}

    def wx_params(self):
        data = request_json(make_session(), auth_api_path("GetWxParams"))
        appid = ""
        result = data.get("result") if isinstance(data, dict) else None
        if isinstance(result, str):
            appid = result
        elif isinstance(result, dict):
            appid = result.get("appid") or result.get("AppId") or ""
        official_redirect = f"{BASE}{service_view_path('#/ValidateOpenId')}"
        capture_redirect = f"{BASE}{auth_api_path('GetWxParams')}"
        authorize_url = ""
        official_authorize_url = ""
        qrcode_data_url = ""
        if appid:
            # Use a same-domain API endpoint for the QR callback so WeChat leaves
            # the returned ?code=... in the address bar for non-technical users.
            authorize_url = (
                "https://open.weixin.qq.com/connect/oauth2/authorize"
                f"?appid={quote(appid)}"
                f"&redirect_uri={quote(capture_redirect, safe='')}"
                "&response_type=code&scope=snsapi_userinfo&state=weunix_capture#wechat_redirect"
            )
            official_authorize_url = (
                "https://open.weixin.qq.com/connect/oauth2/authorize"
                f"?appid={quote(appid)}"
                f"&redirect_uri={quote(official_redirect, safe='')}"
                "&response_type=code&scope=snsapi_userinfo&state=weunix#wechat_redirect"
            )
            image = qrcode.make(authorize_url)
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            qrcode_data_url = "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")
        return {
            "raw": data,
            "appid": appid,
            "redirect_uri": capture_redirect,
            "official_redirect_uri": official_redirect,
            "authorize_url": authorize_url,
            "official_authorize_url": official_authorize_url,
            "qrcode": qrcode_data_url,
        }

    def emo(self):
        fallback = "保持清醒，等风来，也等系统给出答案。"
        sources = [
            ("https://api.zxki.cn/api/wrwa", None),
            ("https://api.mir6.com/api/yulu", {"txt": "4", "type": "json"}),
            ("https://uapis.cn/api/v1/saying", None),
        ]
        errors = []
        for url, params in sources:
            try:
                response = requests.get(url, params=params, timeout=6)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "json" in content_type.lower():
                    data = response.json()
                    text = str(
                        data.get("text")
                        or data.get("content")
                        or data.get("msg")
                        or data.get("data")
                        or fallback
                    ).strip()
                    if text:
                        return {"text": text, "raw": data}
                else:
                    text = response.text.strip()
                    if text:
                        return {"text": text}
            except Exception as exc:
                errors.append(friendly_error(exc))
        return {"text": fallback, "error": "；".join(errors[-2:]) if errors else ""}

    def ping(self):
        now = time.time()
        if now - self.last_ping_at < 10 and self.server_latency_ms is not None:
            return {"latency_ms": self.server_latency_ms, "cached": True}
        start = time.time()
        try:
            requests.get(f"{BASE}{setting_api_path('GetAppBlock')}", timeout=4)
            latency = int((time.time() - start) * 1000)
        except Exception:
            latency = -1
        with self.lock:
            self.server_latency_ms = latency
            self.last_ping_at = now
        return {"latency_ms": latency, "cached": False}

    def log(self, level, message):
        with self.lock:
            self.logs.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": level,
                "message": str(message),
            })
            self.logs = self.logs[-500:]

    def _consume_events(self):
        while not self._closing:
            try:
                uid, kind, data, _color = self.queue.get(timeout=0.25)
            except queue.Empty:
                continue
            with self.lock:
                acc = next((a for a in self.accounts if a.uid == uid), None)
                name = acc.display_name if acc else uid
                if kind == "log":
                    self.log("info", data)
                elif kind == "error":
                    self.log("error", f"{name}: {data}")
                    self.running[uid] = False
                elif kind == "student":
                    self.save()
                    self.log("success", f"{name}: 身份信息已同步")
                elif kind == "rooms":
                    self.rooms[uid] = data if isinstance(data, list) else []
                    self.log("success", f"{name}: 资源返回 {len(self.rooms[uid])} 条")
                elif kind == "preflight":
                    self.preflight[uid] = data
                    self.log("success", f"{name}: 体检完成")
                elif kind == "rehearsal":
                    self.rehearsals[uid] = data
                    self.log("success", f"{name}: 演练完成")
                elif kind == "payment":
                    self.payments[uid] = data if isinstance(data, dict) else {}
                    self.log("success", f"{name}: 已创建订单")
                elif kind == "attempts":
                    self.attempts[uid] = int(data or 0)
                elif kind == "running":
                    self.running[uid] = bool(data)
                elif kind == "status":
                    self.statuses[uid] = str(data)
                    self.log("info", f"{name}: {data}")


STATE = RuntimeState()


class Handler(BaseHTTPRequestHandler):
    server_version = "WeunixBackend/0.1"

    def do_OPTIONS(self):
        self._send_json({"ok": True})

    def do_GET(self):
        try:
            path = urlparse(self.path).path
            if path == "/api/status":
                STATE.ping()
                return self._send_json(STATE.snapshot())
            if path == "/api/wx/params":
                return self._send_json(STATE.wx_params())
            if path == "/api/capture/status":
                return self._send_json({"ok": True, **STATE.capture.status()})
            if path == "/api/emo":
                return self._send_json({"ok": True, **STATE.emo()})
            if path == "/api/ping":
                return self._send_json({"ok": True, **STATE.ping()})
            if path.startswith("/api/diagnostic"):
                parsed = urlparse(self.path)
                uid = ""
                if parsed.query.startswith("uid="):
                    uid = parsed.query[4:]
                return self._send_json({"ok": True, **STATE.diagnostic(uid)})
            return self._send_json({"ok": False, "error": "Not found"}, 404)
        except Exception as exc:
            return self._send_json({"ok": False, "error": str(exc)}, 500)

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            payload = self._read_json()
            if path == "/api/accounts":
                account = STATE.add_account(
                    payload.get("openid") or payload.get("wxopid") or "",
                    payload.get("nickname") or "",
                    payload.get("tag") or "",
                    payload.get("college") or "",
                )
                return self._send_json({"ok": True, "account": account})
            if path == "/api/wx/resolve":
                return self._send_json({"ok": True, **STATE.resolve_wxcode(payload.get("wxcode") or "")})
            if path == "/api/capture/start":
                return self._send_json({"ok": True, **STATE.capture.start(payload.get("nickname") or "", payload.get("tag") or "", payload.get("mode") or "isolated")})
            if path == "/api/capture/stop":
                return self._send_json({"ok": True, **STATE.capture.stop()})
            if path == "/api/config":
                return self._send_json(STATE.update_config(payload))
            if path == "/api/config/backup":
                return self._send_json({"ok": True, **STATE.backup_config()})
            if path == "/api/config/restore":
                return self._send_json(STATE.restore_config())
            if path.startswith("/api/actions/"):
                action = path.rsplit("/", 1)[-1]
                action_map = {
                    "refresh-all": "refresh",
                    "preflight-all": "preflight",
                    "rehearse-all": "rehearse",
                    "start-all": "start",
                    "stop-all": "stop",
                }
                if action in action_map:
                    return self._send_json({"ok": True, **STATE.action_all(action_map[action])})
            if path.startswith("/api/accounts/"):
                parts = [p for p in path.split("/") if p]
                uid = parts[2] if len(parts) >= 3 else ""
                action = parts[3] if len(parts) >= 4 else ""
                if action == "refresh":
                    STATE.refresh(uid)
                    return self._send_json({"ok": True})
                if action == "preflight":
                    STATE.preflight_account(uid)
                    return self._send_json({"ok": True})
                if action == "rehearse":
                    STATE.rehearse_account(uid)
                    return self._send_json({"ok": True})
                if action == "start":
                    STATE.start_account(uid)
                    return self._send_json({"ok": True})
                if action == "stop":
                    STATE.stop_account(uid)
                    return self._send_json({"ok": True})
                if action == "update":
                    account = STATE.update_account(uid, payload)
                    return self._send_json({"ok": True, "account": account})
                if action == "delete":
                    STATE.remove_account(uid)
                    return self._send_json({"ok": True})
            return self._send_json({"ok": False, "error": "Not found"}, 404)
        except Exception as exc:
            return self._send_json({"ok": False, "error": str(exc)}, 400)

    def log_message(self, fmt, *args):
        return

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    port = int(os.environ.get("WEUNIX_BACKEND_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(json.dumps({"ok": True, "port": port, "pid": os.getpid()}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        STATE._closing = True
        try:
            STATE.capture.stop()
        except Exception:
            pass
        server.server_close()


if __name__ == "__main__":
    main()
