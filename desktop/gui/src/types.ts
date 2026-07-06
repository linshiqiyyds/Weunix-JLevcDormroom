export type Level = "info" | "success" | "warning" | "error";

export interface RuntimeLog {
  time: string;
  level: Level;
  message: string;
}

export interface PreflightCheck {
  label: string;
  ok: boolean;
  detail: string;
}

export interface PreflightPayload {
  auto_login?: boolean;
  token?: boolean;
  student?: boolean;
  batch_open?: boolean;
  rooms_count?: number;
  matched?: boolean;
  pref_label?: string;
  start_time?: string;
  end_time?: string;
  checks?: PreflightCheck[];
}

export interface RoomPayload {
  room_type?: string;
  roomType?: string;
  room_charge?: string | number;
  room_bed_num?: string | number;
  bed_num?: string | number;
  room_type_id?: string | number;
}

export interface PaymentPayload {
  room?: RoomPayload;
  order_id?: string;
  pay_url?: string;
  message?: string;
}

export interface RehearsalPayload {
  rooms_count?: number;
  matched?: boolean;
  room?: RoomPayload;
  pref_label?: string;
  batch_open?: boolean;
  start_time?: string;
  end_time?: string;
}

export interface AccountPayload {
  uid: string;
  openid: string;
  nickname: string;
  tag: string;
  college: string;
  class_name: string;
  student_id: string;
  user_id: string;
  user_role: string;
  batch_open: boolean;
  start_time: string;
  end_time: string;
  display_name: string;
  running: boolean;
  status?: string;
  attempts?: number;
  rooms: RoomPayload[];
  preflight?: PreflightPayload;
  rehearsal?: RehearsalPayload;
  payment?: PaymentPayload;
}

export interface CaptureStatus {
  active: boolean;
  port: number;
  started_at: string;
  last_url: string;
  last_target_url?: string;
  captured_openid: string;
  captured_openid_raw?: string;
  imported: boolean;
  account?: AccountPayload | null;
  error?: string;
  proxy_enabled?: boolean;
  system_proxy_active?: boolean;
  upstream_proxy?: string;
  mode?: "idle" | "isolated" | "system";
  request_count?: number;
  target_count?: number;
}

export interface StatusPayload {
  ok: boolean;
  time: string;
  base: string;
  open_time: string;
  pref: string;
  pref_label: string;
  mask_sensitive?: boolean;
  server_latency_ms?: number | null;
  capture?: CaptureStatus;
  accounts: AccountPayload[];
  logs: RuntimeLog[];
}
