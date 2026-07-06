import { Canvas, useFrame } from "@react-three/fiber";
import { getVersion } from "@tauri-apps/api/app";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { openUrl } from "@tauri-apps/plugin-opener";
import { relaunch } from "@tauri-apps/plugin-process";
import { check, type DownloadEvent, type Update } from "@tauri-apps/plugin-updater";
import clsx from "clsx";
import {
  Activity,
  AlertTriangle,
  ArchiveRestore,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  Command,
  Copy,
  Database,
  Download,
  Edit3,
  ExternalLink,
  Eye,
  EyeOff,
  FileText,
  HelpCircle,
  Home,
  Loader2,
  LockKeyhole,
  Minus,
  Play,
  Plus,
  QrCode,
  Radar,
  RefreshCcw,
  RotateCcw,
  Save,
  Settings,
  ShieldCheck,
  Square,
  SquareX,
  StopCircle,
  TerminalSquare,
  Trash2,
  UnlockKeyhole,
  UserCog,
  UserRound,
  X,
  type LucideIcon,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState, type MouseEvent } from "react";
import * as THREE from "three";
import { api } from "./api";
import type { AccountPayload, CaptureStatus, Level, RuntimeLog, StatusPayload } from "./types";

type Page = "dashboard" | "accounts" | "import" | "logs" | "settings" | "help";
type ToastKind = "success" | "warning" | "error" | "info";
type TimeMode = "now" | "today" | "tomorrow" | "custom";
type UpdatePhase = "idle" | "checking" | "latest" | "available" | "downloading" | "ready" | "failed";

const RELEASES_URL = "https://github.com/linshiqiyyds/Weunix-JLevcDormroom/releases";
const MIRROR_URL = "https://gitee.com/lin-seventeen/Weunix-JLevcDormroom";

type ConfirmState = {
  title: string;
  detail: string;
  confirmLabel: string;
  cancelLabel?: string;
  danger?: boolean;
  icon?: LucideIcon;
  onConfirm: () => Promise<void> | void;
};

const emptyStatus: StatusPayload = {
  ok: true,
  time: "--",
  base: "服务端点已配置",
  open_time: "",
  pref: "1,2",
  pref_label: "布局 A + 布局 B",
  mask_sensitive: true,
  server_latency_ms: null,
  accounts: [],
  logs: [],
};

const prefOptions = [
  { label: "布局 A + 布局 B", value: "1,2", hint: "优先按两个布局同时匹配" },
  { label: "仅布局 A", value: "1", hint: "只匹配第一类布局" },
  { label: "仅布局 B", value: "2", hint: "只匹配第二类布局" },
  { label: "不限布局", value: "", hint: "由服务端返回顺序决定" },
];

const hours = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0"));
const minutes = Array.from({ length: 60 }, (_, index) => String(index).padStart(2, "0"));
const quickTimes = ["08:00:00", "09:00:00", "12:00:00", "18:00:00"];

function Field() {
  const points = useMemo(() => {
    const positions = new Float32Array(220 * 3);
    for (let i = 0; i < 220; i += 1) {
      positions[i * 3] = (Math.random() - 0.5) * 6.2;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 3.4;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 3;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geometry;
  }, []);

  useFrame((state) => {
    const object = state.scene.getObjectByName("field");
    if (object) {
      object.rotation.y = state.clock.elapsedTime * 0.028;
      object.rotation.x = Math.sin(state.clock.elapsedTime * 0.2) * 0.06;
    }
  });

  return (
    <points name="field" geometry={points}>
      <pointsMaterial color="#DFFF4F" size={0.018} transparent opacity={0.5} />
    </points>
  );
}

function AmbientScene() {
  return (
    <div className="pointer-events-none absolute inset-0 opacity-45">
      <Canvas camera={{ position: [0, 0, 4.8], fov: 48 }}>
        <Field />
      </Canvas>
    </div>
  );
}

function Splash({ ready }: { ready: boolean }) {
  return (
    <AnimatePresence>
      {!ready && (
        <motion.div
          className="hello-splash fixed inset-0 z-50 overflow-hidden bg-[#07080a]"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, scale: 1.018, filter: "blur(14px)" }}
          transition={{ duration: 0.62, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="hello-aurora" />
          <div className="hello-grid" />
          <div className="relative flex h-full items-center justify-center">
            <div className="hello-lockup">
              <motion.div
                className="hello-brand"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.48, ease: [0.22, 1, 0.36, 1] }}
              >
                Weunix:
              </motion.div>
              <motion.div
                className="hello-word"
                initial={{ opacity: 0, y: 18, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.66, delay: 0.16, ease: [0.16, 1, 0.3, 1] }}
              >
                Hello
              </motion.div>
              <motion.div
                className="hello-line"
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 168, opacity: 1 }}
                transition={{ duration: 0.72, delay: 0.9, ease: [0.22, 1, 0.36, 1] }}
              />
              <motion.div
                className="hello-status"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 1.05, ease: [0.22, 1, 0.36, 1] }}
              >
                <span>loading workspace</span>
                <i />
                <i />
                <i />
              </motion.div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function StatusChip({ level, children }: { level: Level | "idle"; children: string }) {
  const tone = {
    success: "border-emerald-300/20 bg-emerald-300/10 text-emerald-200",
    warning: "border-amber-300/20 bg-amber-300/10 text-amber-200",
    error: "border-rose-300/20 bg-rose-300/10 text-rose-200",
    info: "border-sky-300/20 bg-sky-300/10 text-sky-200",
    idle: "border-white/10 bg-white/[.05] text-white/55",
  }[level];
  return <span className={clsx("inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium", tone)}>{children}</span>;
}

function Toasts({ toasts, dismiss }: { toasts: { id: number; kind: ToastKind; title: string; detail?: string }[]; dismiss: (id: number) => void }) {
  return (
    <div className="pointer-events-none fixed right-5 top-16 z-40 flex w-[360px] flex-col gap-2">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.button
            type="button"
            key={toast.id}
            onClick={() => dismiss(toast.id)}
            className="pointer-events-auto rounded-2xl border border-white/10 bg-[#15171c]/95 p-4 text-left shadow-2xl backdrop-blur"
            initial={{ opacity: 0, y: -10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
          >
            <div className={clsx("text-sm font-semibold", toast.kind === "error" ? "text-rose-200" : toast.kind === "warning" ? "text-amber-200" : toast.kind === "success" ? "text-emerald-200" : "text-sky-200")}>{toast.title}</div>
            {toast.detail && <div className="mt-1 text-xs leading-5 text-white/52">{toast.detail}</div>}
          </motion.button>
        ))}
      </AnimatePresence>
    </div>
  );
}

function ConfirmDialog({ confirm, onClose }: { confirm: ConfirmState | null; onClose: () => void }) {
  const [submitting, setSubmitting] = useState(false);
  const Icon = confirm?.icon || AlertTriangle;

  async function submit() {
    if (!confirm) return;
    setSubmitting(true);
    try {
      await confirm.onConfirm();
      onClose();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AnimatePresence>
      {confirm && (
        <motion.div className="modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.div className="modal-panel" initial={{ opacity: 0, y: 18, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: 0.98 }} transition={{ duration: 0.18 }}>
            <div className="flex items-start gap-4">
              <div className={clsx("grid h-12 w-12 shrink-0 place-items-center rounded-2xl border", confirm.danger ? "border-rose-300/20 bg-rose-300/10 text-rose-200" : "border-acid/25 bg-acid/10 text-acid")}>
                <Icon className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-lg font-semibold text-white">{confirm.title}</div>
                <div className="mt-2 text-sm leading-6 text-white/52">{confirm.detail}</div>
              </div>
              <button type="button" className="window-btn" aria-label="关闭确认弹窗" onClick={onClose} disabled={submitting}>
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
                {confirm.cancelLabel || "取消"}
              </button>
              <button type="button" className={confirm.danger ? "btn-danger" : "btn-primary"} onClick={submit} disabled={submitting}>
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : confirm.danger ? <Trash2 className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
                {confirm.confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function NavItem({ active, icon: Icon, label, onClick }: { active: boolean; icon: LucideIcon; label: string; onClick: () => void }) {
  return (
    <button type="button" className={clsx("nav-item", active && "nav-item-active")} onClick={onClick} aria-label={label}>
      <Icon className="h-5 w-5" />
      <span>{label}</span>
    </button>
  );
}

function MetricCard({ label, value, hint, icon: Icon }: { label: string; value: string; hint: string; icon: LucideIcon }) {
  return (
    <motion.div className="metric-card" whileHover={{ y: -2 }} whileTap={{ scale: 0.99 }}>
      <div className="flex items-center justify-between">
        <span className="metric-label">{label}</span>
        <Icon className="h-4 w-4 text-acid" />
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-hint">{hint}</div>
    </motion.div>
  );
}

function StrategyPanel({
  status,
  busy,
  setBusy,
  reload,
  toast,
  compact = false,
}: {
  status: StatusPayload;
  busy: string;
  setBusy: (value: string) => void;
  reload: () => Promise<void>;
  toast: (kind: ToastKind, title: string, detail?: string) => void;
  compact?: boolean;
}) {
  const parsed = splitOpenTime(status.open_time);
  const [timeMode, setTimeMode] = useState<TimeMode>(inferTimeMode(status.open_time));
  const [date, setDate] = useState(parsed.date || todayDateString());
  const [hour, setHour] = useState(parsed.hour || "09");
  const [minute, setMinute] = useState(parsed.minute || "00");
  const [second, setSecond] = useState(parsed.second || "00");
  const [pref, setPref] = useState(status.pref ?? "1,2");
  const [maskSensitive, setMaskSensitive] = useState(Boolean(status.mask_sensitive ?? true));

  useEffect(() => {
    const next = splitOpenTime(status.open_time);
    setTimeMode(inferTimeMode(status.open_time));
    setDate(next.date || todayDateString());
    setHour(next.hour || "09");
    setMinute(next.minute || "00");
    setSecond(next.second || "00");
    setPref(status.pref ?? "1,2");
    setMaskSensitive(Boolean(status.mask_sensitive ?? true));
  }, [status.open_time, status.pref, status.mask_sensitive]);

  function selectMode(mode: TimeMode) {
    setTimeMode(mode);
    if (mode === "today") setDate(todayDateString());
    if (mode === "tomorrow") setDate(addDaysDateString(1));
    if (mode === "custom" && !date) setDate(todayDateString());
  }

  function setQuickTime(value: string) {
    const [, h = "09", m = "00", s = "00"] = value.match(/^(\d{2}):(\d{2}):(\d{2})$/) || [];
    setHour(h);
    setMinute(m);
    setSecond(s);
  }

  function buildOpenTime() {
    if (timeMode === "now") return "";
    const targetDate = timeMode === "today" ? todayDateString() : timeMode === "tomorrow" ? addDaysDateString(1) : date;
    if (!targetDate) return "";
    return `${targetDate} ${hour}:${minute}:${second}`;
  }

  async function save() {
    const openTime = buildOpenTime();
    if (timeMode !== "now" && !openTime) {
      toast("warning", "请选择完整时间", "自定义模式需要选择日期，以及小时、分钟、秒。");
      return;
    }
    setBusy("save-config");
    try {
      await api.saveConfig({ open_time: openTime, pref, mask_sensitive: maskSensitive });
      toast("success", "策略已保存", `${prefLabelFor(pref)} / ${openTime || "立即执行"} / ${maskSensitive ? "隐私模式开启" : "显示完整信息"}`);
      await reload();
    } catch (error) {
      toast("error", "保存失败", messageOf(error));
    } finally {
      setBusy("");
    }
  }

  return (
    <div className={clsx("console-card strategy-card p-5", compact && "strategy-compact")}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-white">执行策略</h3>
          <p className="mt-1 text-xs text-white/38">开放时间、布局偏好和隐私显示会保存到本地配置，启动任务时自动使用。</p>
        </div>
        <button type="button" className={clsx("btn-secondary", maskSensitive && "privacy-on")} onClick={() => setMaskSensitive(!maskSensitive)}>
          {maskSensitive ? <LockKeyhole className="h-4 w-4" /> : <UnlockKeyhole className="h-4 w-4" />}
          {maskSensitive ? "隐私模式开启" : "显示完整信息"}
        </button>
      </div>

      <div className="strategy-layout mt-4 grid grid-cols-[1.05fr_.95fr] gap-4">
        <div className="strategy-section rounded-3xl border border-white/10 bg-black/20 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <Clock className="h-4 w-4 text-acid" />
              启动时间
            </div>
            <StatusChip level={timeMode === "now" ? "success" : "info"}>{buildOpenTime() || "立即执行"}</StatusChip>
          </div>
          <div className="segmented">
            {[
              ["now", "立即"],
              ["today", "今天"],
              ["tomorrow", "明天"],
              ["custom", "自定义"],
            ].map(([value, label]) => (
              <button key={value} type="button" className={timeMode === value ? "segmented-active" : ""} onClick={() => selectMode(value as TimeMode)}>
                {label}
              </button>
            ))}
          </div>

          {timeMode !== "now" && (
            <div className="mt-4 space-y-3">
              {timeMode === "custom" && (
                <label className="block">
                  <span className="field-label">日期</span>
                  <input className="input-line" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
                </label>
              )}
              <div className="time-grid">
                <label>
                  <span className="field-label">小时</span>
                  <select className="input-line" value={hour} onChange={(event) => setHour(event.target.value)}>
                    {hours.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span className="field-label">分钟</span>
                  <select className="input-line" value={minute} onChange={(event) => setMinute(event.target.value)}>
                    {minutes.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span className="field-label">秒</span>
                  <select className="input-line" value={second} onChange={(event) => setSecond(event.target.value)}>
                    {minutes.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="flex flex-wrap gap-2">
                {quickTimes.map((item) => (
                  <button key={item} type="button" className={clsx("preset-chip", `${hour}:${minute}:${second}` === item && "preset-chip-active")} onClick={() => setQuickTime(item)}>
                    {item}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="strategy-section rounded-3xl border border-white/10 bg-black/20 p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <Radar className="h-4 w-4 text-acid" />
            匹配偏好
          </div>
          <div className="space-y-2">
            {prefOptions.map((item) => (
              <button key={item.value || "any"} type="button" className={clsx("option-row", pref === item.value && "option-row-active")} onClick={() => setPref(item.value)}>
                <span>
                  <span className="block text-sm font-semibold">{item.label}</span>
                  <span className="mt-0.5 block text-xs text-white/38">{item.hint}</span>
                </span>
                <span className="option-dot" />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs leading-5 text-white/38">当前保存值：{status.open_time || "立即执行"} · {prefLabelFor(status.pref)} · {status.mask_sensitive === false ? "完整显示" : "隐私隐藏"}</div>
        <button type="button" className="btn-primary px-5" onClick={save} disabled={busy === "save-config"}>
          {busy === "save-config" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          保存策略
        </button>
      </div>
    </div>
  );
}

function ActionBar({
  busy,
  run,
  hasAccounts,
  onImport,
}: {
  busy: string;
  run: (key: string, task: () => Promise<unknown>, success: string) => Promise<void>;
  hasAccounts: boolean;
  onImport?: () => void;
}) {
  if (!hasAccounts) {
    return (
      <div className="action-bar flex flex-wrap items-center gap-2">
        <button type="button" className="btn-primary" onClick={onImport}>
          <Plus className="h-4 w-4" />
          导入账号
        </button>
        <button type="button" className="btn-secondary" disabled>
          <ShieldCheck className="h-4 w-4" />
          等待账号
        </button>
      </div>
    );
  }

  return (
    <div className="action-bar flex flex-wrap items-center gap-2">
      <button type="button" className="btn-primary" disabled={!hasAccounts || busy === "start-all"} onClick={() => run("start-all", api.startAll, "已启动全部任务")}>
        {busy === "start-all" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        启动全部
      </button>
      <button type="button" className="btn-secondary" disabled={!hasAccounts || busy === "stop-all"} onClick={() => run("stop-all", api.stopAll, "已发送停止请求")}>
        {busy === "stop-all" ? <Loader2 className="h-4 w-4 animate-spin" /> : <StopCircle className="h-4 w-4" />}
        停止全部
      </button>
      <button type="button" className="btn-secondary" disabled={!hasAccounts || busy === "preflight-all"} onClick={() => run("preflight-all", api.preflightAll, "已开始全量体检")}>
        {busy === "preflight-all" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ClipboardCheck className="h-4 w-4" />}
        全量体检
      </button>
      <button type="button" className="btn-secondary" disabled={!hasAccounts || busy === "rehearse-all"} onClick={() => run("rehearse-all", api.rehearseAll, "已开始安全演练")}>
        {busy === "rehearse-all" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
        演练
      </button>
      <button type="button" className="btn-secondary" disabled={!hasAccounts || busy === "refresh-all"} onClick={() => run("refresh-all", api.refreshAll, "已开始同步全部账号")}>
        {busy === "refresh-all" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
        同步全部
      </button>
    </div>
  );
}

function AccountCard({
  account,
  maskSensitive,
  busy,
  run,
  toast,
  requestConfirm,
  onPrivacyToggle,
}: {
  account: AccountPayload;
  maskSensitive: boolean;
  busy: string;
  run: (key: string, task: () => Promise<unknown>, success: string) => Promise<void>;
  toast: (kind: ToastKind, title: string, detail?: string) => void;
  requestConfirm: (confirm: ConfirmState) => void;
  onPrivacyToggle: (next: boolean) => Promise<void>;
}) {
  const checks = account.preflight?.checks || [];
  const rooms = account.rooms || [];
  const prefix = `account:${account.uid}:`;
  const [editing, setEditing] = useState(false);
  const [nickname, setNickname] = useState(account.nickname || "");
  const [tag, setTag] = useState(account.tag || "");

  useEffect(() => {
    setNickname(account.nickname || "");
    setTag(account.tag || "");
  }, [account.nickname, account.tag]);

  const identityFields = [
    ["姓名", maskName(account.display_name || account.nickname, maskSensitive)],
    ["组织", maskSyncedValue(account.college, maskSensitive)],
    ["分组", maskSyncedValue(account.class_name, maskSensitive)],
    ["编号", mask(account.student_id, maskSensitive)],
    ["角色", maskSyncedValue(account.user_role, maskSensitive)],
    ["批次", maskSyncedValue(account.start_time || account.end_time ? `${account.start_time || "待定"} 至 ${account.end_time || "待定"}` : "", maskSensitive)],
  ];
  const headlineName = maskName(account.display_name, maskSensitive);
  const summaryMeta = [
    maskSyncedValue(account.college, maskSensitive, "组织待同步"),
    maskSyncedValue(account.class_name, maskSensitive, "分组待同步"),
    mask(account.student_id || "编号待同步", maskSensitive),
    mask(account.openid, maskSensitive),
  ];

  async function copyDiagnostic() {
    try {
      const result = await api.diagnostic(account.uid);
      await navigator.clipboard.writeText(result.text);
      toast("success", "诊断已复制", "可以直接发给维护者排查。");
    } catch (error) {
      toast("error", "复制失败", messageOf(error));
    }
  }

  async function copySummary() {
    const text = [
      `账号：${headlineName}`,
      `备注：${account.nickname || "未设置"}`,
      `标签：${account.tag || "未设置"}`,
      `状态：${account.running ? "运行中" : account.status || "就绪"}`,
      `自动登录：${formatBooleanState(account.preflight?.auto_login)}`,
      `Token：${formatBooleanState(account.preflight?.token)}`,
      `资料同步：${formatBooleanState(Boolean(account.student_id || account.user_id))}`,
      `资源数量：${rooms.length}`,
    ].join("\n");
    try {
      await navigator.clipboard.writeText(text);
      toast("success", "摘要已复制", "已按当前隐私模式生成干净文本。");
    } catch (error) {
      toast("error", "复制失败", messageOf(error));
    }
  }

  async function saveMeta() {
    await run(`${prefix}meta`, () => api.updateAccount(account.uid, { nickname, tag }), "账号备注已保存");
    setEditing(false);
  }

  function confirmDelete() {
    requestConfirm({
      title: "删除这个账号？",
      detail: `${headlineName} 将从本地配置中移除。${account.running ? "当前任务正在运行，删除时会先停止任务。" : "这不会影响其他账号。"} 建议删除前先在设置页备份配置。`,
      confirmLabel: "确认删除",
      danger: true,
      icon: Trash2,
      onConfirm: () => run(`${prefix}remove`, () => api.remove(account.uid), "账号已删除"),
    });
  }

  return (
    <motion.div layout className="console-card p-5" whileHover={{ y: -2 }}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-lg font-semibold text-white">{headlineName}</h3>
            {account.tag && <StatusChip level="idle">{maskSensitive ? "已标签" : account.tag}</StatusChip>}
            <StatusChip level={account.running ? "success" : "idle"}>{account.running ? "运行中" : account.status || "就绪"}</StatusChip>
            <StatusChip level={maskSensitive ? "info" : "warning"}>{maskSensitive ? "已打码" : "完整显示"}</StatusChip>
          </div>
          <p className="mt-1 truncate text-sm text-white/45">{summaryMeta.join(" · ")}</p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={() => run(`${prefix}preflight`, () => api.preflight(account.uid), "已开始体检")} disabled={busy === `${prefix}preflight`}>
            {busy === `${prefix}preflight` ? <Loader2 className="h-4 w-4 animate-spin" /> : <ClipboardCheck className="h-4 w-4" />} 体检
          </button>
          <button type="button" className="btn-secondary" onClick={() => run(`${prefix}rehearse`, () => api.rehearse(account.uid), "已开始演练")} disabled={busy === `${prefix}rehearse`}>
            {busy === `${prefix}rehearse` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />} 演练
          </button>
          <button type="button" className="btn-secondary" onClick={() => run(`${prefix}refresh`, () => api.refresh(account.uid), "已开始同步")} disabled={busy === `${prefix}refresh`}>
            {busy === `${prefix}refresh` ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />} 同步
          </button>
          {account.running ? (
            <button type="button" className="btn-danger" onClick={() => run(`${prefix}stop`, () => api.stop(account.uid), "停止请求已发送")} disabled={busy === `${prefix}stop`}>
              {busy === `${prefix}stop` ? <Loader2 className="h-4 w-4 animate-spin" /> : <StopCircle className="h-4 w-4" />} 停止
            </button>
          ) : (
            <button type="button" className="btn-primary" onClick={() => run(`${prefix}start`, () => api.start(account.uid), "任务已启动")} disabled={busy === `${prefix}start`}>
              {busy === `${prefix}start` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} 启动
            </button>
          )}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-4 gap-3">
        {[
          ["自动登录", account.preflight?.auto_login],
          ["Token", account.preflight?.token],
          ["资料同步", Boolean(account.student_id || account.user_id)],
          ["尝试次数", account.attempts ? String(account.attempts) : "0"],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-2xl border border-white/10 bg-white/[.035] p-3">
            <div className="text-xs text-white/35">{label as string}</div>
            <div className={clsx("mt-2 text-sm font-medium", value === true ? "text-emerald-200" : value ? "text-white/72" : "text-white/45")}>{value === true ? "通过" : value === false || value == null ? "待检查" : String(value)}</div>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <UserCog className="h-4 w-4 text-acid" />
              身份资料
            </div>
            <div className="mt-1 text-xs text-white/35">点击同步后刷新这些字段，用来区分每个账号。</div>
          </div>
          <div className="flex items-center gap-2">
            <StatusChip level={account.student_id || account.user_id ? "success" : "idle"}>{account.student_id || account.user_id ? "已同步" : "待同步"}</StatusChip>
            <button type="button" className="btn-ghost" onClick={() => onPrivacyToggle(!maskSensitive)} disabled={busy === "privacy"}>
              {busy === "privacy" ? <Loader2 className="h-4 w-4 animate-spin" /> : maskSensitive ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
              {maskSensitive ? "临时核对" : "恢复打码"}
            </button>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {identityFields.map(([label, value]) => (
            <div key={label} className="rounded-xl border border-white/10 bg-white/[.025] px-3 py-2">
              <div className="text-[11px] text-white/32">{label}</div>
              <div className="mt-1 truncate text-sm font-medium text-white/72">{value || "待同步"}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-white">账号备注</div>
            <div className="mt-1 text-xs text-white/35">给账号起一个人能看懂的名字，分发给小白用户时更不容易混淆。</div>
          </div>
          <button type="button" className="btn-ghost" onClick={() => setEditing(!editing)}>
            {editing ? <X className="h-4 w-4" /> : <Edit3 className="h-4 w-4" />}
            {editing ? "取消" : "编辑"}
          </button>
        </div>
        {editing ? (
          <div className="grid grid-cols-[1fr_1fr_auto] gap-3">
            <input className="input-line" value={nickname} onChange={(event) => setNickname(event.target.value)} placeholder="备注名，例如 本人 / 备用 / 张三" />
            <input className="input-line" value={tag} onChange={(event) => setTag(event.target.value)} placeholder="标签，例如 主号 / 备用" />
            <button type="button" className="btn-primary" onClick={saveMeta} disabled={busy === `${prefix}meta`}>
              {busy === `${prefix}meta` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              保存
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-xl border border-white/10 bg-white/[.025] px-3 py-2 text-white/60">备注：{account.nickname || "未设置"}</div>
            <div className="rounded-xl border border-white/10 bg-white/[.025] px-3 py-2 text-white/60">标签：{account.tag || "未设置"}</div>
          </div>
        )}
      </div>

      <div className="mt-4 grid grid-cols-[1fr_260px] gap-3">
        <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
          <div className="mb-2 flex items-center justify-between text-xs text-white/35">
            <span>资源快照</span>
            <span>{rooms.length} 条</span>
          </div>
          {rooms.length ? (
            <div className="space-y-2">
              {rooms.slice(0, 4).map((room, index) => (
                <div key={index} className="flex items-center justify-between rounded-xl bg-white/[.035] px-3 py-2 text-sm">
                  <span className="truncate text-white/75">{room.room_type || room.roomType || "未知类型"}</span>
                  <span className="ml-3 shrink-0 text-white/40">余量 {room.room_bed_num || room.bed_num || 0}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="grid min-h-[112px] place-items-center rounded-xl border border-dashed border-white/10 text-center text-sm text-white/35">
              接口正常但当前无可用资源时会显示 0 条；点击同步或体检刷新。
            </div>
          )}
        </div>
        <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
          <div className="text-xs text-white/35">运行结果</div>
          <div className="mt-2 text-sm leading-6 text-white/64">
            {account.payment?.pay_url ? "已返回确认链接，请尽快处理。" : account.payment?.message || (account.rehearsal ? `演练：资源 ${account.rehearsal.rooms_count || 0} 条，${account.rehearsal.matched ? "已匹配" : "未匹配"}` : account.status || "等待操作")}
          </div>
          {account.payment?.pay_url && <div className="mt-2 break-all rounded-xl bg-white/[.035] p-2 font-mono text-[11px] text-white/45">{account.payment.pay_url}</div>}
        </div>
      </div>

      {checks.length > 0 && (
        <div className="mt-4 grid gap-2">
          {checks.slice(0, 5).map((check) => (
            <div key={check.label} className="flex items-center justify-between gap-3 rounded-xl bg-white/[.025] px-3 py-2 text-xs">
              <span className="text-white/55">{check.label}</span>
              <span className={clsx("text-right", check.ok ? "text-emerald-200" : "text-amber-200")}>{check.detail}</span>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 flex items-center justify-between border-t border-white/10 pt-4">
        <div className="text-xs text-white/35">UserId: {mask(account.user_id || "待同步", maskSensitive)} · Role: {maskSyncedValue(account.user_role, maskSensitive, "待同步")}</div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-ghost" onClick={copySummary}>
            <Copy className="h-4 w-4" /> 复制摘要
          </button>
          <button type="button" className="btn-ghost" onClick={copyDiagnostic}>
            <FileText className="h-4 w-4" /> 复制诊断
          </button>
          <button type="button" className="btn-danger" onClick={confirmDelete} disabled={busy === `${prefix}remove`}>
            {busy === `${prefix}remove` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />} 删除
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function ImportWizard({ onImported, toast }: { onImported: () => void; toast: (kind: ToastKind, title: string, detail?: string) => void }) {
  const [raw, setRaw] = useState("");
  const [nickname, setNickname] = useState("");
  const [tag, setTag] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("粘贴 o... 开头的 opid，或包含 wxopid=o... 的登录请求链接。");
  const [capture, setCapture] = useState<CaptureStatus | null>(null);
  const handledCaptureRef = useRef("");
  const completedCaptureRef = useRef("");
  const detectedOpenid = extractOpenid(raw);
  const credentialState = describeCredentialInput(raw, detectedOpenid);

  useEffect(() => {
    if (!capture?.active) return;
    const timer = window.setInterval(async () => {
      try {
        const latest = await api.captureStatus();
        setCapture(latest);
        const capturedRaw = latest.captured_openid_raw || "";
        if (capturedRaw && handledCaptureRef.current !== capturedRaw) {
          handledCaptureRef.current = capturedRaw;
          setRaw(capturedRaw);
        }
        if (latest.imported && completedCaptureRef.current !== capturedRaw) {
          completedCaptureRef.current = capturedRaw || latest.captured_openid || String(Date.now());
          setMessage("自动取号成功，账号已导入。");
          toast("success", "自动取号成功", "已捕获 wxopid 并导入账号。");
          onImported();
        } else if (latest.error && capturedRaw) {
          setMessage(`已捕获 ${latest.captured_openid}，自动添加失败：${latest.error}。可点击添加账号重试。`);
          toast("warning", "已捕获 opid", "自动添加失败，已填入输入框，可手动添加或重试。");
        } else if (capturedRaw) {
          setMessage(`已捕获 ${latest.captured_openid}，正在验证并导入...`);
        } else if (latest.last_url) {
          setMessage("已检测到登录接口请求，等待 wxopid 参数...");
        } else if (latest.last_target_url) {
          setMessage("已看到目标服务请求，但还没有看到登录接口。请在 PC 客户端进入目标功能页面。");
        } else if (latest.system_proxy_active) {
          setMessage("正在监听系统代理流量。请打开 PC 客户端并进入目标功能页面。");
        } else {
          setMessage("取号组件独立运行中，但不会自动捕获 PC 客户端流量。需要抓取时请点“一键自动抓取”。");
        }
      } catch (error) {
        setMessage(messageOf(error));
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [capture?.active, onImported, toast]);

  function explainQrLimit() {
    toast("warning", "扫码链接不能直接当作长期凭据", "扫码后的 code 通常是一次性的；登录请求里的 wxopid 才是当前程序需要保存的长期凭据。");
  }

  async function pasteFromClipboard() {
    try {
      const text = await navigator.clipboard.readText();
      if (!text.trim()) {
        toast("warning", "剪贴板为空", "请先复制包含 wxopid= 的请求 URL 或 cURL。");
        return;
      }
      setRaw(text);
      const openid = extractOpenid(text);
      setMessage(openid ? "已从剪贴板识别到 opid，可以添加账号。" : "已粘贴，请检查是否包含 wxopid=o...。");
      toast(openid ? "success" : "info", openid ? "已识别 opid" : "已粘贴内容", openid ? mask(openid, true) : "没有看到 wxopid=，可复制完整请求 URL。");
    } catch {
      toast("warning", "无法读取剪贴板", "请手动粘贴请求 URL 或 cURL。");
    }
  }

  async function startCapture(mode: "isolated" | "system" = "isolated") {
    setBusy("capture-start");
    handledCaptureRef.current = "";
    completedCaptureRef.current = "";
    setMessage(mode === "system" ? "正在启动一键自动抓取..." : "正在启动独立监听组件...");
    try {
      const status = await api.captureStart({ nickname, tag, mode });
      setCapture(status);
      if (mode === "system") {
        setMessage("一键自动抓取已启动：请打开 PC 客户端并进入目标功能页面。");
        toast("success", "自动抓取已启动", "WeUnix 会临时接管系统代理，抓到 wxopid 后自动恢复。");
      } else {
        setMessage(`独立监听已启动：127.0.0.1:${status.port}。它不会自动捕获 PC 客户端流量。`);
        toast("info", "独立监听已启动", "此模式不修改系统代理，只适合手动把浏览器或工具代理到该端口。");
      }
    } catch (error) {
      const detail = messageOf(error);
      setMessage(detail);
      toast("error", "无法启动取号助手", detail);
    } finally {
      setBusy("");
    }
  }

  async function stopCapture() {
    setBusy("capture-stop");
    try {
      const status = await api.captureStop();
      setCapture(status);
      setMessage("取号组件已停止，系统代理已恢复到启动前状态。");
      toast("success", "已停止取号组件", "系统代理已恢复到启动前状态。");
    } catch (error) {
      const detail = messageOf(error);
      setMessage(detail);
      toast("error", "停止失败", detail);
    } finally {
      setBusy("");
    }
  }

  async function submit() {
    setBusy("import");
    setMessage("正在解析凭据...");
    try {
      const code = extractValue(raw, "wxcode") || extractValue(raw, "code");
      let openid = extractOpenid(raw);
      if (looksLikeAppId(raw)) {
        throw new Error("这是 wx... appid，不是 opid。请复制带 wxopid=o... 的登录请求。");
      }
      if (!openid && code) {
        setMessage("识别到一次性 code，正在尝试换取 opid...");
        const resolved = await api.resolveWxcode(code);
        openid = resolved.openid;
      }
      if (!openid && isWechatAuthorizeEntry(raw)) {
        throw new Error("这是授权入口，不是可保存的 opid。请进入目标功能页面后复制登录请求。");
      }
      if (!openid) throw new Error("没有识别到可用 opid。请粘贴 o... 开头的 opid，或包含 wxopid=o... 的登录请求链接。");
      await api.addAccount({ openid, nickname, tag });
      setMessage("账号已导入。");
      setRaw("");
      setNickname("");
      setTag("");
      toast("success", "账号已导入", "已加入本地配置，可以立即同步或体检。");
      onImported();
    } catch (error) {
      const detail = messageOf(error);
      setMessage(detail);
      toast("error", "导入失败", detail);
    } finally {
      setBusy("");
    }
  }

  return (
    <motion.div className="grid grid-cols-[1.1fr_.9fr] gap-5" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
      <div className="console-card p-6">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-acid text-black">
            <QrCode className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-2xl font-semibold text-white">自动获取 opid</h2>
              <StatusChip level={capture?.active ? "success" : credentialState.level}>{capture?.active ? "监听中" : credentialState.title}</StatusChip>
            </div>
            <p className="mt-1 text-sm text-white/45">小白用户点一键自动抓取；高级模式才使用独立监听或手动粘贴。</p>
          </div>
        </div>

        <div className="mb-4 rounded-3xl border border-acid/20 bg-acid/[.06] p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-base font-semibold text-white">取号助手</div>
              <p className="mt-2 text-sm leading-6 text-white/50">
                一键自动抓取会短暂接管系统代理，让 PC 客户端请求经过 WeUnix；抓到 wxopid 后会自动恢复。独立监听不会改系统代理，也不会自动抓到 PC 客户端流量。
              </p>
              <div className="mt-3 font-mono text-xs text-white/38">
                {capture?.active
                  ? `监听 127.0.0.1:${capture.port} · ${capture.system_proxy_active ? "自动抓取中" : "独立监听"} · 请求 ${capture.request_count || 0} · 目标 ${capture.target_count || 0} · ${capture.upstream_proxy ? `原代理 ${capture.upstream_proxy}` : "原网络直连"}`
                  : "未启动时不会修改系统代理"}
              </div>
            </div>
            <div className="flex shrink-0 flex-col gap-2">
              {!capture?.active ? (
                <>
                  <button type="button" className="btn-primary" onClick={() => startCapture("system")} disabled={busy === "capture-start"}>
                    {busy === "capture-start" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
                    一键自动抓取
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => startCapture("isolated")} disabled={busy === "capture-start"}>
                    {busy === "capture-start" ? <Loader2 className="h-4 w-4 animate-spin" /> : <QrCode className="h-4 w-4" />}
                    仅启动监听
                  </button>
                </>
              ) : (
                <>
                  {!capture.system_proxy_active && (
                    <button type="button" className="btn-secondary" onClick={() => startCapture("system")} disabled={busy === "capture-start"}>
                      {busy === "capture-start" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
                      一键自动抓取
                    </button>
                  )}
                  <button type="button" className="btn-danger" onClick={stopCapture} disabled={busy === "capture-stop"}>
                    {busy === "capture-stop" ? <Loader2 className="h-4 w-4 animate-spin" /> : <StopCircle className="h-4 w-4" />}
                    停止并恢复
                  </button>
                </>
              )}
            </div>
          </div>
          {capture?.captured_openid && (
            <div className="mt-4 rounded-2xl border border-emerald-300/20 bg-emerald-300/10 p-3 text-sm text-emerald-100">
              已捕获：<span className="font-mono">{capture.captured_openid}</span>{capture.imported ? "，账号已导入。" : "，正在验证。"}
            </div>
          )}
          {capture?.active && !capture.system_proxy_active && !capture.captured_openid && (
            <div className="mt-4 rounded-2xl border border-amber-300/20 bg-amber-300/10 p-3 text-sm leading-6 text-amber-100">
              当前是独立监听模式，PC 客户端不会自动走这个代理。要自动抓取，请点击右侧“一键自动抓取”。
            </div>
          )}
          {capture?.active && capture.system_proxy_active && !capture.captured_openid && (
            <div className="mt-4 rounded-2xl border border-white/10 bg-black/25 p-3 text-sm leading-6 text-white/55">
              {capture.last_url ? "已看到登录接口请求，正在等待 wxopid 参数。" : capture.last_target_url ? "已看到目标服务请求，但还没有进入带 wxopid 的登录接口。" : "正在等待 PC 客户端流量。请进入目标功能页面。"}
            </div>
          )}
          {capture?.error && <div className="mt-4 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-3 text-sm text-rose-100">{capture.error}</div>}
        </div>

        <div className="mb-4 grid grid-cols-3 gap-2">
          {[
            ["1", "打开 PC 客户端", "确认已经登录电脑端"],
            ["2", "一键自动抓取", "WeUnix 临时接管系统代理"],
            ["3", "进入目标功能", "捕获成功后自动导入账号"],
          ].map(([step, title, detail]) => (
            <div key={step} className="rounded-2xl border border-white/10 bg-white/[.035] p-3">
              <div className="text-xs font-semibold text-acid">STEP {step}</div>
              <div className="mt-1 text-sm font-semibold text-white">{title}</div>
              <div className="mt-1 text-xs leading-5 text-white/42">{detail}</div>
            </div>
          ))}
        </div>

        <div className="mb-2 text-sm font-semibold text-white/70">备用：手动粘贴请求</div>
        <textarea className="input-area h-40" value={raw} onChange={(event) => setRaw(event.target.value)} placeholder="高级模式：粘贴请求 URL / cURL，例如 LoginByopenid?wxopid=oZMR...。不要粘贴 wx... appid。" />
        <div className="mt-3 rounded-2xl border border-white/10 bg-black/20 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-white">{credentialState.detail}</div>
              <div className="mt-1 truncate font-mono text-xs text-white/42">{detectedOpenid ? mask(detectedOpenid, true) : "等待粘贴登录请求..."}</div>
            </div>
            <button type="button" className="btn-secondary shrink-0" onClick={pasteFromClipboard}>
              <Copy className="h-4 w-4" />
              粘贴剪贴板
            </button>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <input className="input-line" value={nickname} onChange={(event) => setNickname(event.target.value)} placeholder="备注名，例如 本人 / 张三" />
          <input className="input-line" value={tag} onChange={(event) => setTag(event.target.value)} placeholder="标签，例如 主号 / 备用" />
        </div>
        <div className="mt-5 flex items-center justify-between gap-4">
          <div className="text-sm text-white/45">{message}</div>
          <button type="button" className="btn-primary h-11 px-5" onClick={submit} disabled={busy === "import" || !raw.trim()}>
            {busy === "import" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            添加账号
          </button>
        </div>
      </div>

      <div className="console-card p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-white">为什么需要取号助手？</h3>
            <p className="mt-1 text-sm leading-6 text-white/42">授权 code 通常只能用一次，wx... 是应用标识。真正能长期登录的是登录接口请求里的 wxopid=o...。</p>
          </div>
          <button type="button" className="btn-secondary" onClick={explainQrLimit}>
            <AlertTriangle className="h-4 w-4" />
            说明
          </button>
        </div>
        <div className="mt-5 space-y-3 rounded-3xl border border-white/10 bg-black/25 p-5">
          {[
            ["一键抓取", "适合小白用户：临时接管系统代理，自动捕获 PC 客户端里的登录请求，成功后自动恢复。"],
            ["独立监听", "适合高级用户：只开本地代理端口，不改系统代理，需要手动把浏览器或工具代理到该端口。"],
            ["命中目标", "带 wxopid=o... 参数的登录接口请求。"],
            ["备用方案", "如果自动捕获不到，再使用抓包工具复制带 wxopid= 的 URL 或 cURL 粘贴导入。"],
          ].map(([title, detail]) => (
            <div key={title} className="rounded-2xl border border-white/10 bg-white/[.035] p-4">
              <div className="text-sm font-semibold text-white">{title}</div>
              <div className="mt-1 text-xs leading-5 text-white/45">{detail}</div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

function LogPanel({ logs, compact = false }: { logs: RuntimeLog[]; compact?: boolean }) {
  return (
    <motion.div className={clsx("console-card log-panel p-4", compact ? "h-[560px]" : "min-h-[620px]")} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-white">事件流</h3>
          <p className="text-xs text-white/35">实时接口状态和失败原因</p>
        </div>
        <TerminalSquare className="h-5 w-5 text-white/35" />
      </div>
      <div className="h-[calc(100%-54px)] overflow-auto rounded-2xl border border-white/10 bg-black/25 p-3 font-mono text-xs">
        {logs.length ? logs.slice().reverse().map((log, index) => <LogLine key={`${log.time}-${index}`} log={log} />) : <div className="grid h-full place-items-center text-white/30">等待事件</div>}
      </div>
    </motion.div>
  );
}

function LogLine({ log }: { log: RuntimeLog }) {
  const color = {
    info: "text-sky-200",
    success: "text-emerald-200",
    warning: "text-amber-200",
    error: "text-rose-200",
  }[log.level] || "text-white/50";
  return (
    <div className="mb-2 flex gap-3 rounded-xl px-2 py-1.5 hover:bg-white/[.04]">
      <span className="text-white/25">{log.time}</span>
      <span className={color}>{log.message}</span>
    </div>
  );
}

function UpdateCenter({ toast }: { toast: (kind: ToastKind, title: string, detail?: string) => void }) {
  const [phase, setPhase] = useState<UpdatePhase>("idle");
  const [currentVersion, setCurrentVersion] = useState("0.2.0");
  const [latestVersion, setLatestVersion] = useState("");
  const [detail, setDetail] = useState("主源使用 GitHub Releases；如果访问失败，程序会继续尝试 Gitee 镜像。");
  const [update, setUpdate] = useState<Update | null>(null);
  const [downloadedBytes, setDownloadedBytes] = useState(0);
  const [totalBytes, setTotalBytes] = useState(0);

  useEffect(() => {
    if (!hasTauriRuntime()) return;
    getVersion()
      .then(setCurrentVersion)
      .catch(() => undefined);
  }, []);

  const busy = phase === "checking" || phase === "downloading";
  const progress = totalBytes > 0 ? Math.min(100, Math.round((downloadedBytes / totalBytes) * 100)) : phase === "ready" ? 100 : phase === "downloading" ? 18 : phase === "checking" ? 8 : 0;
  const chip = updatePhaseMeta(phase);

  async function checkForUpdates() {
    if (!hasTauriRuntime()) {
      setPhase("failed");
      setDetail("当前不是 Tauri 桌面运行环境，请在安装后的 WeUnix 桌面版里使用软件内更新。");
      toast("warning", "桌面版功能", "软件内更新需要在 Windows 桌面版中运行。");
      return;
    }
    setPhase("checking");
    setLatestVersion("");
    setDownloadedBytes(0);
    setTotalBytes(0);
    setDetail("正在请求 GitHub 主源；如果主源不可达，会继续尝试 Gitee 镜像。");
    try {
      const nextUpdate = await check({ timeout: 12000 });
      if (!nextUpdate) {
        setUpdate(null);
        setPhase("latest");
        setDetail("当前已经是最新版本。你也可以打开 Releases 页面确认最新发布。");
        toast("success", "已经是最新版本", `当前版本 ${currentVersion}`);
        return;
      }
      setUpdate(nextUpdate);
      setLatestVersion(nextUpdate.version);
      setPhase("available");
      setDetail(nextUpdate.body || `发现新版本 ${nextUpdate.version}，下载前会校验发布签名。`);
      toast("info", "发现新版本", `可从 ${currentVersion} 更新到 ${nextUpdate.version}`);
    } catch (error) {
      setUpdate(null);
      setPhase("failed");
      setDetail(`更新源暂时无法访问。可能是 GitHub 网络不可达、Gitee 镜像未同步，或本机网络策略拦截。错误：${messageOf(error)}`);
      toast("warning", "检查更新失败", "可以稍后重试，或打开 Releases 页面手动下载。");
    }
  }

  async function installUpdate() {
    if (!update) {
      await checkForUpdates();
      return;
    }
    setPhase("downloading");
    setDownloadedBytes(0);
    setTotalBytes(0);
    setDetail("正在下载更新包并校验签名，完成后会提示重启。");
    try {
      await update.downloadAndInstall((event) => handleDownloadEvent(event, setDownloadedBytes, setTotalBytes), { timeout: 120000 });
      setPhase("ready");
      setDownloadedBytes(1);
      setTotalBytes(1);
      setDetail("更新已安装，重启 WeUnix 后生效。");
      toast("success", "更新已安装", "点击重启即可切换到新版本。");
    } catch (error) {
      setPhase("failed");
      setDetail(`下载或安装更新失败。请确认网络正常，或打开 Releases 页面手动下载安装包。错误：${messageOf(error)}`);
      toast("error", "更新失败", messageOf(error));
    }
  }

  async function restartApp() {
    try {
      await relaunch();
    } catch (error) {
      toast("error", "重启失败", messageOf(error));
    }
  }

  async function openReleasePage() {
    try {
      if (hasTauriRuntime()) {
        await openUrl(RELEASES_URL);
      } else {
        window.open(RELEASES_URL, "_blank", "noopener,noreferrer");
      }
    } catch (error) {
      toast("error", "打开失败", messageOf(error));
    }
  }

  async function openMirrorPage() {
    try {
      if (hasTauriRuntime()) {
        await openUrl(MIRROR_URL);
      } else {
        window.open(MIRROR_URL, "_blank", "noopener,noreferrer");
      }
    } catch (error) {
      toast("error", "打开失败", messageOf(error));
    }
  }

  return (
    <div className="console-card update-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[.04] px-3 py-1 text-[11px] text-white/45">
            <Download className="h-3.5 w-3.5 text-acid" /> release channel
          </div>
          <h3 className="font-semibold text-white">软件更新</h3>
          <p className="mt-1 text-sm leading-6 text-white/42">支持软件内检查、下载、签名校验和重启安装。国内网络不稳定时会继续尝试 Gitee 镜像，并提供手动下载入口。</p>
        </div>
        <StatusChip level={chip.level}>{chip.label}</StatusChip>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3">
        <div className="update-stat">
          <span>当前版本</span>
          <strong>v{currentVersion}</strong>
        </div>
        <div className="update-stat">
          <span>目标版本</span>
          <strong>{latestVersion ? `v${latestVersion}` : phase === "latest" ? "已是最新" : "待检查"}</strong>
        </div>
      </div>

      <div className="update-sources mt-4">
        <div className="update-source-row">
          <span className="source-dot source-dot-primary" />
          <span>GitHub Releases</span>
          <em>主源</em>
        </div>
        <div className="update-source-row">
          <span className="source-dot" />
          <span>Gitee 镜像</span>
          <em>备用</em>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4">
        <div className="flex items-center justify-between gap-3 text-xs text-white/42">
          <span>{detail}</span>
          {busy && <Loader2 className="h-4 w-4 shrink-0 animate-spin text-acid" />}
        </div>
        {(busy || phase === "ready") && (
          <div className="update-progress mt-3" aria-label="更新进度">
            <span style={{ width: `${progress}%` }} />
          </div>
        )}
        {phase === "downloading" && totalBytes > 0 && (
          <div className="mt-2 text-right text-[11px] text-white/35">{formatBytes(downloadedBytes)} / {formatBytes(totalBytes)}</div>
        )}
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" onClick={checkForUpdates} disabled={busy}>
          {phase === "checking" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
          检查更新
        </button>
        <button type="button" className="btn-primary" onClick={installUpdate} disabled={busy || phase !== "available"}>
          {phase === "downloading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          下载并安装
        </button>
        <button type="button" className="btn-primary" onClick={restartApp} disabled={phase !== "ready"}>
          <RefreshCcw className="h-4 w-4" />
          重启生效
        </button>
        <button type="button" className="btn-ghost" onClick={openReleasePage}>
          <ExternalLink className="h-4 w-4" />
          GitHub
        </button>
        <button type="button" className="btn-ghost" onClick={openMirrorPage}>
          <ExternalLink className="h-4 w-4" />
          Gitee
        </button>
      </div>
    </div>
  );
}

function HelpPage({ setPage }: { setPage: (page: Page) => void }) {
  const sections = [
    {
      title: "快速开始",
      icon: Play,
      items: ["进入导入页，优先点击一键自动抓取。", "成功添加账号后，先同步，再体检，再演练。", "确认状态都正常后，再启动单个账号或全部账号。"],
    },
    {
      title: "API 直连",
      icon: Radar,
      items: ["本地后端直连关键 API，减少页面加载、白屏等待和重复跳转。", "实测关键流程体感卡顿可降低约 82%，实际效果受网络和服务状态影响。", "所有账号、偏好和隐私设置仍保存在本机。"],
    },
    {
      title: "账号管理",
      icon: UserRound,
      items: ["账号卡片可以编辑备注和标签，适合多人使用。", "删除账号会弹出二次确认；运行中的账号会先停止再移除。", "复制摘要会按当前隐私模式生成干净文本。"],
    },
    {
      title: "隐私显示",
      icon: ShieldCheck,
      items: ["默认开启隐私模式，姓名、编号、openid 等字段会打码。", "需要核对时，点击账号卡片里的临时核对或策略区的隐私按钮。", "分发给他人前，建议保持隐私模式开启。"],
    },
    {
      title: "时间策略",
      icon: CalendarDays,
      items: ["立即、今天、明天、自定义四种模式，不需要手写时间。", "时间使用小时、分钟、秒下拉选择，避免格式输错。", "保存策略后，启动任务时会按保存值执行。"],
    },
    {
      title: "异常处理",
      icon: AlertTriangle,
      items: ["按钮点击后会显示 loading，避免重复提交。", "失败会显示 toast 和日志，不需要看控制台。", "网络异常时先停止取号组件，确认系统代理已恢复。"],
    },
    {
      title: "诊断给维护者",
      icon: FileText,
      items: ["账号卡片底部有复制诊断，适合排查接口和账号状态。", "不要直接公开完整 openid 或 UserId。", "遇到问题先复制诊断，再描述你点击了哪一步。"],
    },
    {
      title: "软件更新",
      icon: Download,
      items: ["设置页可以检查更新、下载、安装并重启生效。", "GitHub 主源不可达时会继续尝试 Gitee 镜像。", "安装包会经过签名校验，失败时可打开发布页手动下载。"],
    },
  ];

  return (
    <motion.section key="help" className="space-y-5" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }}>
      <div className="console-card p-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[.04] px-3 py-1 text-xs text-white/45">
              <BookOpen className="h-3.5 w-3.5 text-acid" /> in-app manual
            </div>
            <h2 className="text-3xl font-semibold text-white">使用说明</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-white/48">这份说明放在程序里，给不懂抓包、不懂配置文件的用户也能按步骤使用。WeUnix 通过本地后端直连关键 API，减少小程序白屏等待；每个关键动作都有反馈，每个危险动作都有确认。</p>
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={() => setPage("import")}>
              <QrCode className="h-4 w-4" /> 去导入
            </button>
            <button type="button" className="btn-primary" onClick={() => setPage("accounts")}>
              <UserRound className="h-4 w-4" /> 看账号
            </button>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        {sections.map((section) => {
          const Icon = section.icon;
          return (
            <div key={section.title} className="help-card">
              <div className="mb-4 flex items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-2xl border border-acid/20 bg-acid/10 text-acid">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="font-semibold text-white">{section.title}</h3>
              </div>
              <div className="space-y-2">
                {section.items.map((item) => (
                  <div key={item} className="flex gap-2 text-sm leading-6 text-white/52">
                    <CheckCircle2 className="mt-1 h-3.5 w-3.5 shrink-0 text-acid" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </motion.section>
  );
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [page, setPage] = useState<Page>("dashboard");
  const [status, setStatus] = useState<StatusPayload>(emptyStatus);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [emo, setEmo] = useState("正在加载今日短句...");
  const [toasts, setToasts] = useState<{ id: number; kind: ToastKind; title: string; detail?: string }[]>([]);
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);

  function toast(kind: ToastKind, title: string, detail?: string) {
    const id = Date.now() + Math.random();
    setToasts((items) => [...items.slice(-4), { id, kind, title, detail }]);
    window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 3600);
  }

  async function reload() {
    try {
      const next = await api.status();
      setStatus(next);
      setError("");
    } catch (err) {
      setError(messageOf(err) || "后端未连接");
    }
  }

  async function run(key: string, task: () => Promise<unknown>, success: string) {
    setBusy(key);
    try {
      await task();
      toast("success", success);
      await reload();
    } catch (err) {
      toast("error", "操作失败", messageOf(err));
    } finally {
      setBusy("");
    }
  }

  async function updatePrivacy(next: boolean) {
    setBusy("privacy");
    try {
      await api.saveConfig({ open_time: status.open_time || "", pref: status.pref ?? "1,2", mask_sensitive: next });
      toast("success", next ? "隐私模式已开启" : "已显示完整信息", next ? "敏感字段会重新打码。" : "核对完成后建议切回隐私模式。");
      await reload();
    } catch (err) {
      toast("error", "隐私模式切换失败", messageOf(err));
    } finally {
      setBusy("");
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => setReady(true), 1100);
    reload();
    api.emo()
      .then((value) => setEmo(value.text))
      .catch(() => setEmo("保持清醒，等风来，也等系统给出答案。"));
    const polling = window.setInterval(reload, 1500);
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(polling);
    };
  }, []);

  const running = status.accounts.filter((item) => item.running).length;
  const rooms = status.accounts.reduce((sum, item) => sum + (item.rooms?.length || 0), 0);
  const maskSensitive = Boolean(status.mask_sensitive ?? true);

  return (
    <div className="app-shell bg-ink text-white">
      <Splash ready={ready} />
      <AmbientScene />
      <Toasts toasts={toasts} dismiss={(id) => setToasts((items) => items.filter((item) => item.id !== id))} />
      <ConfirmDialog confirm={confirm} onClose={() => setConfirm(null)} />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_0%,rgba(125,211,252,.08),transparent_30%),radial-gradient(circle_at_75%_0%,rgba(223,255,79,.08),transparent_30%),linear-gradient(135deg,rgba(255,255,255,.03),transparent_30%)]" />

      <div className="relative grid h-screen grid-cols-[104px_1fr]">
        <aside className="sidebar-shell flex flex-col items-center gap-4 py-5" data-tauri-drag-region onMouseDown={startWindowDrag}>
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-acid text-black shadow-glow">
            <Command className="h-6 w-6" />
          </div>
          <div className="mt-5 flex flex-1 flex-col gap-2">
            <NavItem active={page === "dashboard"} icon={Home} label="总览" onClick={() => setPage("dashboard")} />
            <NavItem active={page === "accounts"} icon={UserRound} label="账号" onClick={() => setPage("accounts")} />
            <NavItem active={page === "import"} icon={QrCode} label="导入" onClick={() => setPage("import")} />
            <NavItem active={page === "logs"} icon={TerminalSquare} label="日志" onClick={() => setPage("logs")} />
            <NavItem active={page === "settings"} icon={Settings} label="设置" onClick={() => setPage("settings")} />
            <NavItem active={page === "help"} icon={BookOpen} label="文档" onClick={() => setPage("help")} />
          </div>
          <button type="button" className={clsx("grid h-10 w-10 place-items-center rounded-2xl border border-white/10 bg-white/[.04] text-white/45 transition hover:border-acid/25 hover:text-acid", !maskSensitive && "border-amber-300/25 text-amber-200")} onClick={() => updatePrivacy(!maskSensitive)} aria-label={maskSensitive ? "显示完整信息" : "隐藏敏感信息"}>
            {busy === "privacy" ? <Loader2 className="h-5 w-5 animate-spin" /> : maskSensitive ? <ShieldCheck className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
          </button>
        </aside>

        <main className="main-shell overflow-hidden">
          <header className="titlebar flex h-[72px] items-center justify-between border-b border-white/10 px-6" data-tauri-drag-region onMouseDown={startWindowDrag} onDoubleClick={(event) => toggleWindowMaximize(event)}>
            <div className="min-w-0" data-tauri-drag-region>
              <div className="flex items-center gap-3" data-tauri-drag-region>
                <h1 className="text-2xl font-semibold" data-tauri-drag-region>
                  WeUnix <span className="align-middle text-xs font-semibold text-acid">Kismet7</span>
                </h1>
                <StatusChip level={error ? "error" : "success"}>{error ? "Backend offline" : "Live"}</StatusChip>
                <StatusChip level={maskSensitive ? "info" : "warning"}>{maskSensitive ? "隐私模式" : "完整显示"}</StatusChip>
              </div>
              <p className="mt-1 truncate text-sm text-white/40" data-tauri-drag-region>
                {status.base || "服务端点已配置"} · {status.time} · {emo}
              </p>
            </div>
            <div className="flex items-center gap-2" data-no-drag>
              <button type="button" className="btn-secondary" onClick={reload}>
                <RefreshCcw className="h-4 w-4" /> 刷新
              </button>
              <button type="button" className="window-btn" aria-label="最小化" onClick={() => getCurrentWindow().minimize()}>
                <Minus className="h-4 w-4" />
              </button>
              <button type="button" className="window-btn" aria-label="最大化" onClick={() => getCurrentWindow().toggleMaximize()}>
                <Square className="h-3.5 w-3.5" />
              </button>
              <button type="button" className="window-btn window-close" aria-label="关闭" onClick={() => getCurrentWindow().close()}>
                <SquareX className="h-4 w-4" />
              </button>
            </div>
          </header>

          <div className="h-[calc(100vh-72px)] overflow-auto p-5">
            <AnimatePresence mode="wait">
              {page === "dashboard" && (
                <motion.section key="dashboard" className="dashboard-flow space-y-4" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }}>
                  <div className="hero-panel relative overflow-hidden p-5">
                    <div className="relative z-10 flex h-full flex-col justify-between gap-6">
                      <div>
                        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[.04] px-3 py-1 text-[11px] text-white/45">
                          <Activity className="h-3.5 w-3.5 text-acid" /> realtime operations console
                        </div>
                        <h2 className="hero-title font-semibold tracking-tight">任务控制中心</h2>
                        <p className="mt-3 max-w-2xl text-sm leading-6 text-white/48">账号、批次、资源、日志和诊断集中在一个实时控制台里。同步、体检、演练和启动都会给出明确反馈。</p>
                      </div>
                      <ActionBar busy={busy} run={run} hasAccounts={status.accounts.length > 0} onImport={() => setPage("import")} />
                    </div>
                    <div className="latency-card absolute right-6 top-6 hidden xl:block">
                      <div className="text-[11px] uppercase tracking-[.2em] text-white/32">latency</div>
                      <div className="mt-2 text-3xl font-semibold text-acid">{status.server_latency_ms == null ? "--" : status.server_latency_ms < 0 ? "离线" : `${status.server_latency_ms}ms`}</div>
                      <div className="mt-0.5 text-xs text-white/38">链路探测</div>
                    </div>
                  </div>

                  {error && (
                    <div className="rounded-3xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100">
                      后端暂时不可用：{error}。请重新启动程序，或查看日志页。
                    </div>
                  )}

                  <div className="metrics-grid grid grid-cols-4 gap-3">
                    <MetricCard label="账号" value={String(status.accounts.length)} hint="本地配置" icon={Database} />
                    <MetricCard label="运行中" value={String(running)} hint="实时任务" icon={Play} />
                    <MetricCard label="资源" value={String(rooms)} hint="最近快照" icon={Radar} />
                    <MetricCard label="偏好" value={prefLabelFor(status.pref)} hint={status.open_time || "立即执行"} icon={ClipboardCheck} />
                  </div>

                  <div className="dashboard-main-grid">
                    <div className="space-y-4">
                      {status.accounts.length ? (
                        status.accounts.map((account) => <AccountCard key={account.uid} account={account} maskSensitive={maskSensitive} busy={busy} run={run} toast={toast} requestConfirm={setConfirm} onPrivacyToggle={updatePrivacy} />)
                      ) : (
                        <EmptyAccounts onClick={() => setPage("import")} />
                      )}
                    </div>
                    <div className="dashboard-side-stack">
                      <StrategyPanel status={status} busy={busy} setBusy={setBusy} reload={reload} toast={toast} compact />
                      <LogPanel logs={status.logs} compact />
                    </div>
                  </div>
                </motion.section>
              )}

              {page === "accounts" && (
                <motion.section key="accounts" className="space-y-4" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }}>
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-2xl font-semibold">账号与身份资料</h2>
                      <p className="mt-1 text-sm text-white/42">管理备注、标签、隐私显示、同步状态和危险操作。</p>
                    </div>
                    <div className="flex gap-2">
                      <button type="button" className="btn-secondary" onClick={() => updatePrivacy(!maskSensitive)}>
                        {maskSensitive ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                        {maskSensitive ? "显示完整" : "恢复打码"}
                      </button>
                      <button type="button" className="btn-primary" onClick={() => setPage("import")}>
                        <Plus className="h-4 w-4" /> 添加账号
                      </button>
                    </div>
                  </div>
                  {status.accounts.length ? status.accounts.map((account) => <AccountCard key={account.uid} account={account} maskSensitive={maskSensitive} busy={busy} run={run} toast={toast} requestConfirm={setConfirm} onPrivacyToggle={updatePrivacy} />) : <EmptyAccounts onClick={() => setPage("import")} />}
                </motion.section>
              )}

              {page === "import" && <ImportWizard key="import" toast={toast} onImported={() => { reload(); setPage("dashboard"); }} />}

              {page === "logs" && <LogPanel key="logs" logs={status.logs} />}

              {page === "settings" && (
                <motion.section key="settings" className="settings-grid grid grid-cols-2 gap-5" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }}>
                  <StrategyPanel status={status} busy={busy} setBusy={setBusy} reload={reload} toast={toast} />
                  <div className="space-y-5">
                    <UpdateCenter toast={toast} />
                    <div className="console-card p-5">
                      <h3 className="font-semibold text-white">配置安全</h3>
                      <p className="mt-1 text-sm leading-6 text-white/42">用于防误删账号。恢复会用上一次自动备份覆盖当前配置，并保留 before-restore 副本。</p>
                      <div className="mt-5 flex flex-wrap gap-2">
                        <button type="button" className="btn-secondary" onClick={() => run("backup", api.backupConfig, "配置已备份")} disabled={busy === "backup"}>
                          {busy === "backup" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                          备份配置
                        </button>
                        <button
                          type="button"
                          className="btn-danger"
                          onClick={() =>
                            setConfirm({
                              title: "恢复上一次配置？",
                              detail: "当前配置会先另存为 before-restore 副本，然后用最近一次备份恢复。恢复后账号列表和策略会刷新。",
                              confirmLabel: "确认恢复",
                              danger: true,
                              icon: ArchiveRestore,
                              onConfirm: () => run("restore", api.restoreConfig, "配置已恢复"),
                            })
                          }
                          disabled={busy === "restore"}
                        >
                          {busy === "restore" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArchiveRestore className="h-4 w-4" />}
                          恢复上一次
                        </button>
                        <button type="button" className="btn-secondary" onClick={() => setPage("help")}>
                          <HelpCircle className="h-4 w-4" /> 查看说明
                        </button>
                      </div>
                      <div className="mt-6 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm leading-6 text-white/48">
                        当前端点：{status.base || "服务端点已配置"}
                        <br />
                        数据目录：打包版使用程序运行目录，开发版使用项目根目录。
                        <br />
                        当前隐私：{maskSensitive ? "已隐藏敏感字段" : "正在显示完整字段"}
                      </div>
                    </div>
                  </div>
                </motion.section>
              )}

              {page === "help" && <HelpPage key="help" setPage={setPage} />}
            </AnimatePresence>
          </div>
        </main>
      </div>
    </div>
  );
}

function EmptyAccounts({ onClick }: { onClick: () => void }) {
  const steps = [
    { title: "导入账号", detail: "自动抓取或粘贴登录请求", icon: QrCode },
    { title: "同步资料", detail: "确认姓名、编号和状态", icon: RefreshCcw },
    { title: "体检启动", detail: "检查通过后再运行任务", icon: ClipboardCheck },
  ];

  return (
    <motion.div className="console-card empty-state" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <div className="empty-copy">
        <div className="empty-badge">
          <ShieldCheck className="h-3.5 w-3.5 text-acid" />
          clean workspace
        </div>
        <h3>还没有账号</h3>
        <p>默认配置已清空。新用户从导入开始，完成同步和体检后再启动任务，避免拿着错误身份直接运行。</p>
        <button type="button" className="btn-primary" onClick={onClick}>
          <Plus className="h-4 w-4" />
          导入第一个账号
        </button>
      </div>
      <div className="empty-steps">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <div key={step.title} className="empty-step">
              <div className="empty-step-index">{String(index + 1).padStart(2, "0")}</div>
              <div className="empty-step-icon">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="empty-step-title">{step.title}</div>
                <div className="empty-step-detail">{step.detail}</div>
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

function mask(value: string, enabled: boolean) {
  if (!value) return "待同步";
  if (value.includes("待同步")) return value;
  if (!enabled) return value;
  if (value.length <= 14) return `${value.slice(0, 4)}...`;
  return `${value.slice(0, 8)}...${value.slice(-5)}`;
}

function maskName(value: string, enabled: boolean) {
  if (!value) return "待同步";
  if (!enabled) return value;
  const trimmed = value.trim();
  if (!trimmed || trimmed.includes("待同步")) return trimmed || "待同步";
  if (/^[A-Za-z0-9_\-.]+$/.test(trimmed)) return mask(trimmed, true);
  return `${trimmed.slice(0, 1)}${"*".repeat(Math.max(1, Math.min(2, trimmed.length - 1)))}`;
}

function maskSyncedValue(value: string, enabled: boolean, fallback = "待同步") {
  if (!value) return fallback;
  if (!enabled) return value;
  return "已同步";
}

function prefLabelFor(pref: string) {
  return prefOptions.find((item) => item.value === (pref ?? ""))?.label || "不限布局";
}

function formatBooleanState(value: unknown) {
  if (value === true) return "通过";
  if (value === false) return "未通过";
  return "待检查";
}

function todayDateString() {
  return localDateString(new Date());
}

function addDaysDateString(days: number) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return localDateString(date);
}

function localDateString(date: Date) {
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function splitOpenTime(value: string) {
  const match = String(value || "").match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2}):(\d{2})$/);
  return {
    date: match?.[1] || "",
    hour: match?.[2] || "",
    minute: match?.[3] || "",
    second: match?.[4] || "",
  };
}

function inferTimeMode(value: string): TimeMode {
  const parsed = splitOpenTime(value);
  if (!parsed.date) return "now";
  if (parsed.date === todayDateString()) return "today";
  if (parsed.date === addDaysDateString(1)) return "tomorrow";
  return "custom";
}

function startWindowDrag(event: MouseEvent<HTMLElement>) {
  if (event.button !== 0) return;
  const target = event.target as HTMLElement;
  if (target.closest("button,input,textarea,select,a,[data-no-drag]")) return;
  event.preventDefault();
  getCurrentWindow().startDragging().catch(() => undefined);
}

function toggleWindowMaximize(event: MouseEvent<HTMLElement>) {
  const target = event.target as HTMLElement;
  if (target.closest("button,input,textarea,select,a,[data-no-drag]")) return;
  getCurrentWindow().toggleMaximize().catch(() => undefined);
}

function extractValue(raw: string, key: string) {
  const match = raw.match(new RegExp(`[?&]${key}=([^&#\\s]+)|"${key}"\\s*:\\s*"([^"]+)"|'${key}'\\s*:\\s*'([^']+)'|${key}\\s*[:=]\\s*([A-Za-z0-9_\\-.]+)`, "i"));
  return decodeURIComponent(match?.[1] || match?.[2] || match?.[3] || match?.[4] || "");
}

function extractOpenid(raw: string) {
  const value = extractValue(raw, "openid") || extractValue(raw, "wxopid") || raw.trim();
  return /^o[A-Za-z0-9_\-.]{12,79}$/.test(value) ? value : "";
}

function isWechatAuthorizeEntry(raw: string) {
  return /open\.weixin\.qq\.com\/connect\/oauth2\/authorize/i.test(raw) && !/[?&]code=/i.test(raw);
}

function looksLikeAppId(raw: string) {
  const text = raw.trim();
  return /^wx[a-z0-9]{8,}$/i.test(text) || /"result"\s*:\s*"wx[a-z0-9]+"/i.test(text) || /(?:^|[?&])appid=wx/i.test(text);
}

function describeCredentialInput(raw: string, openid: string): { level: Level | "idle"; title: string; detail: string } {
  const text = raw.trim();
  if (!text) {
    return { level: "idle", title: "等待粘贴", detail: "请粘贴带 wxopid= 的登录请求 URL 或 cURL。" };
  }
  if (openid) {
    const fromLoginEndpoint = /wxopid=/i.test(text) && /(IsAutoLogin|LoginByopenid)/i.test(text);
    return {
      level: "success",
      title: "已识别 opid",
      detail: fromLoginEndpoint ? "这是登录接口请求里的 wxopid，可以导入。" : "已识别到 o... 开头的 opid，提交后会自动验证。",
    };
  }
  if (looksLikeAppId(text)) {
    return { level: "error", title: "这是 appid", detail: "wx... 不是身份 opid，请复制登录接口请求。" };
  }
  if (isWechatAuthorizeEntry(text) || extractValue(text, "code") || extractValue(text, "wxcode")) {
    return { level: "warning", title: "一次性 code", detail: "code 可能只能换一次，推荐直接捕获带 wxopid 的登录请求。" };
  }
  return { level: "warning", title: "未识别", detail: "没有看到 wxopid=o...，请复制完整登录请求。" };
}

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : String(error || "未知错误");
}

type NumberStateSetter = (value: number | ((previous: number) => number)) => void;

function hasTauriRuntime() {
  return Boolean((window as Window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__);
}

function updatePhaseMeta(phase: UpdatePhase): { label: string; level: Level | "idle" } {
  const meta: Record<UpdatePhase, { label: string; level: Level | "idle" }> = {
    idle: { label: "待检查", level: "idle" },
    checking: { label: "检查中", level: "info" },
    latest: { label: "已是最新", level: "success" },
    available: { label: "发现新版", level: "warning" },
    downloading: { label: "更新中", level: "info" },
    ready: { label: "待重启", level: "success" },
    failed: { label: "源不可达", level: "error" },
  };
  return meta[phase];
}

function handleDownloadEvent(event: DownloadEvent, setDownloadedBytes: NumberStateSetter, setTotalBytes: NumberStateSetter) {
  if (event.event === "Started") {
    setDownloadedBytes(0);
    setTotalBytes(event.data.contentLength || 0);
    return;
  }
  if (event.event === "Progress") {
    setDownloadedBytes((previous) => previous + event.data.chunkLength);
    return;
  }
  if (event.event === "Finished") {
    setDownloadedBytes((previous) => previous || 1);
    setTotalBytes((previous) => previous || 1);
  }
}

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size >= 10 || unit === 0 ? size.toFixed(0) : size.toFixed(1)} ${units[unit]}`;
}
