import type { CaptureStatus, StatusPayload } from "./types";

const API_BASE = "http://127.0.0.1:8765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data?.ok === false) {
    throw new Error(data?.error || `HTTP ${response.status}`);
  }
  return data as T;
}

export const api = {
  status: () => request<StatusPayload>("/api/status"),
  saveConfig: (payload: { open_time: string; pref: string; mask_sensitive?: boolean }) =>
    request<StatusPayload>("/api/config", { method: "POST", body: JSON.stringify(payload) }),
  backupConfig: () => request<{ ok: true; file: string }>("/api/config/backup", { method: "POST", body: "{}" }),
  restoreConfig: () => request<StatusPayload>("/api/config/restore", { method: "POST", body: "{}" }),
  addAccount: (payload: { openid: string; nickname?: string; tag?: string; college?: string }) =>
    request("/api/accounts", { method: "POST", body: JSON.stringify(payload) }),
  updateAccount: (uid: string, payload: { nickname?: string; tag?: string }) =>
    request(`/api/accounts/${uid}/update`, { method: "POST", body: JSON.stringify(payload) }),
  refresh: (uid: string) => request(`/api/accounts/${uid}/refresh`, { method: "POST", body: "{}" }),
  preflight: (uid: string) => request(`/api/accounts/${uid}/preflight`, { method: "POST", body: "{}" }),
  rehearse: (uid: string) => request(`/api/accounts/${uid}/rehearse`, { method: "POST", body: "{}" }),
  start: (uid: string) => request(`/api/accounts/${uid}/start`, { method: "POST", body: "{}" }),
  stop: (uid: string) => request(`/api/accounts/${uid}/stop`, { method: "POST", body: "{}" }),
  remove: (uid: string) => request(`/api/accounts/${uid}/delete`, { method: "POST", body: "{}" }),
  refreshAll: () => request<{ ok: true; count: number }>("/api/actions/refresh-all", { method: "POST", body: "{}" }),
  preflightAll: () => request<{ ok: true; count: number }>("/api/actions/preflight-all", { method: "POST", body: "{}" }),
  rehearseAll: () => request<{ ok: true; count: number }>("/api/actions/rehearse-all", { method: "POST", body: "{}" }),
  startAll: () => request<{ ok: true; count: number }>("/api/actions/start-all", { method: "POST", body: "{}" }),
  stopAll: () => request<{ ok: true; count: number }>("/api/actions/stop-all", { method: "POST", body: "{}" }),
  diagnostic: (uid?: string) => request<{ ok: true; text: string }>(`/api/diagnostic${uid ? `?uid=${encodeURIComponent(uid)}` : ""}`),
  resolveWxcode: (wxcode: string) =>
    request<{ ok: true; openid: string; raw: unknown }>("/api/wx/resolve", {
      method: "POST",
      body: JSON.stringify({ wxcode }),
    }),
  captureStart: (payload: { nickname?: string; tag?: string; mode?: "isolated" | "system" }) =>
    request<CaptureStatus & { ok: true }>("/api/capture/start", { method: "POST", body: JSON.stringify(payload) }),
  captureStop: () => request<CaptureStatus & { ok: true }>("/api/capture/stop", { method: "POST", body: "{}" }),
  captureStatus: () => request<CaptureStatus & { ok: true }>("/api/capture/status"),
  wxParams: () =>
    request<{
      raw: unknown;
      appid?: string;
      redirect_uri?: string;
      official_redirect_uri?: string;
      authorize_url?: string;
      official_authorize_url?: string;
      qrcode?: string;
    }>("/api/wx/params"),
  emo: () => request<{ ok: true; text: string; raw?: unknown; error?: string }>("/api/emo"),
};
