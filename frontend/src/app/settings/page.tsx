"use client";

import { useEffect, useState } from "react";
import { ConventionToggle } from "@/components/ConventionToggle";
import { LoginGate } from "@/components/LoginGate";

const TOKEN_KEY = "comad_stock_token";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

type Usage = { date: string; memo: { used: number; limit: number }; ask: { used: number; limit: number } };
type Status = {
  configured_server_side: boolean;
  anthropic: boolean;
  openai: boolean;
  anthropic_hint: string | null;
  openai_hint: string | null;
  is_admin: boolean;
  server_fallback_usage: Usage;
};
type OrgMember = {
  user_id: string;
  role: string;
  created_at: string | null;
};
type OrgInvite = {
  id: string;
  email: string;
  role: string;
  status: string;
  token: string | null;
  created_at: string | null;
  accepted_at: string | null;
};
type Organization = {
  id: string;
  name: string;
  slug: string;
  created_at: string | null;
  members: OrgMember[];
};

export default function SettingsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [anthropic, setAnthropic] = useState("");
  const [openai, setOpenai] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const t = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
    setToken(t);
    if (t) loadStatus(t);
  }, []);

  async function loadStatus(t: string) {
    try {
      const r = await fetch(`${API}/api/byok/status`, { headers: { Authorization: `Bearer ${t}` } });
      if (r.ok) setStatus(await r.json());
    } catch {}
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      // Anthropic 키 유효성 검증 먼저
      if (anthropic.trim()) {
        const v = await fetch(`${API}/api/byok/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ anthropic_key: anthropic.trim() }),
        });
        if (!v.ok) {
          const d = await v.json().catch(() => ({}));
          throw new Error(d.detail || "Anthropic 키 검증 실패");
        }
      }

      const body: Record<string, string | null> = {};
      if (anthropic.trim()) body.anthropic_key = anthropic.trim();
      if (openai.trim()) body.openai_key = openai.trim();
      const r = await fetch(`${API}/api/byok/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      setMsg("저장됨. 이제 AI 호출은 내 키로 실행됩니다.");
      setAnthropic("");
      setOpenai("");
      loadStatus(token);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  }

  async function clearKeys() {
    if (!token) return;
    if (!confirm("등록된 모든 API 키를 삭제합니다. 계속?")) return;
    const r = await fetch(`${API}/api/byok/`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (r.ok) {
      setMsg("키 삭제됨");
      loadStatus(token);
    }
  }

  if (!token) {
    return (
      <LoginGate
        title="설정 페이지는 로그인이 필요합니다."
        hint="본인 API 키(BYOK) 등록, 가격 색상 관습, 이상 공시 알림 채널을 이 페이지에서 관리합니다."
        next="/settings"
      />
    );
  }

  return (
    <main className="mx-auto max-w-[720px] px-8 py-20">
      <p className="mono text-[12px] text-fg-3 uppercase tracking-wider">SETTINGS · BYOK</p>
      <h1 className="mt-3 font-serif text-[40px] leading-[1.1] tracking-[-0.01em]">내 API 키</h1>
      <p className="mt-4 text-[15px] text-fg-2 leading-[1.7]">
        본인의 Anthropic Claude 키를 등록하면 DD 메모·자연어 질의 시 <em>내 키</em>로 과금됩니다.
        서버 관리자 키는 fallback이며 일일 한도 적용. 키는 Fernet 암호화 저장.
      </p>

      {status?.is_admin && (
        <div className="mt-6 border border-accent/50 bg-accent-dim/20 px-4 py-3 text-[13px]">
          <span className="mono text-[11px] text-accent uppercase tracking-wider">ADMIN</span>{" "}
          <span className="text-fg-2">운영자 계정 — 서버 키 쿼터 면제</span>
        </div>
      )}

      {status && (
        <section className="mt-10 border-t border-border/50 pt-6 text-[14px] space-y-1">
          <h2 className="mono text-[11px] uppercase tracking-wider text-fg-3 mb-3">현재 상태</h2>
          <p>
            서버측 암호화 키:{" "}
            <span className={status.configured_server_side ? "text-accent" : "text-sev-high"}>
              {status.configured_server_side ? "구성됨" : "미구성 — FIELD_ENCRYPTION_KEY 필요"}
            </span>
          </p>
          <p>
            내 Anthropic 키:{" "}
            {status.anthropic ? (
              <span className="text-accent">
                등록됨 <span className="mono text-fg-3 ml-2">{status.anthropic_hint}</span>
              </span>
            ) : (
              <span className="text-fg-3">미등록 (서버 키 fallback)</span>
            )}
          </p>
          <p>
            내 OpenAI 키:{" "}
            {status.openai ? (
              <span className="text-accent">
                등록됨 <span className="mono text-fg-3 ml-2">{status.openai_hint}</span>
              </span>
            ) : (
              <span className="text-fg-3">미등록</span>
            )}
          </p>

          {!status.is_admin && !status.anthropic && (
            <div className="mt-4 pt-3 border-t border-border/30 text-[12px] text-fg-3">
              <p className="mono uppercase tracking-wider mb-1">오늘 서버 키 사용</p>
              <p>
                메모 {status.server_fallback_usage.memo.used}/{status.server_fallback_usage.memo.limit || "∞"} ·{" "}
                ask {status.server_fallback_usage.ask.used}/{status.server_fallback_usage.ask.limit || "∞"}
              </p>
            </div>
          )}
        </section>
      )}

      <form onSubmit={save} className="mt-12 space-y-6">
        <div>
          <label className="mono text-[12px] text-fg-3 uppercase tracking-wider block mb-2">
            Anthropic Claude API key
          </label>
          <input
            type="password"
            value={anthropic}
            onChange={(e) => setAnthropic(e.target.value)}
            placeholder="sk-ant-api03-…"
            autoComplete="off"
            spellCheck={false}
            className="w-full bg-bg-2 border border-border px-4 py-3 mono text-[13px] focus:border-accent focus:outline-none"
          />
          <p className="mt-1 text-[11px] text-fg-3">
            발급:{" "}
            <a
              href="https://console.anthropic.com/settings/keys"
              target="_blank"
              rel="noreferrer"
              className="border-b border-fg-3 hover:text-accent hover:border-accent"
            >
              console.anthropic.com/settings/keys
            </a>{" "}
            · 저장 전 1-토큰 테스트로 유효성 검증
          </p>
        </div>

        <div>
          <label className="mono text-[12px] text-fg-3 uppercase tracking-wider block mb-2">
            OpenAI API key (선택)
          </label>
          <input
            type="password"
            value={openai}
            onChange={(e) => setOpenai(e.target.value)}
            placeholder="sk-proj-…"
            autoComplete="off"
            spellCheck={false}
            className="w-full bg-bg-2 border border-border px-4 py-3 mono text-[13px] focus:border-accent focus:outline-none"
          />
        </div>

        <div className="flex gap-4">
          <button
            type="submit"
            disabled={saving || !(anthropic || openai)}
            className="mono text-[13px] text-accent border border-accent px-5 py-2 hover:bg-accent-dim transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {saving ? "검증·저장 중…" : "저장"}
          </button>
          {status && (status.anthropic || status.openai) && (
            <button
              type="button"
              onClick={clearKeys}
              className="mono text-[12px] text-fg-3 hover:text-sev-high"
            >
              모든 키 삭제
            </button>
          )}
        </div>

        {msg && <p className="text-[13px] text-accent">{msg}</p>}
        {err && <p className="text-[13px] text-sev-high">⚠ {err}</p>}
      </form>

      <OrganizationSection token={token} />

      <section className="mt-20 border-t border-border/50 pt-10">
        <p className="mono text-[12px] text-fg-3 uppercase tracking-wider">DISPLAY</p>
        <h2 className="mt-2 font-serif text-[28px] leading-[1.15]">표시 설정</h2>
        <p className="mt-3 text-[13px] text-fg-2 leading-[1.7]">
          한국 증권 UI는 상승이 빨강·하락이 파랑. 미국식은 반대. 본인 관습을 선택하세요. 가격·스파크라인에 적용됩니다.
        </p>
        <div className="mt-6">
          <ConventionToggle />
        </div>
      </section>

      <AlertsSection token={token} />
    </main>
  );
}

function OrganizationSection({ token }: { token: string }) {
  const [org, setOrg] = useState<Organization | null>(null);
  const [invites, setInvites] = useState<OrgInvite[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "analyst" | "viewer">("analyst");
  const [latestToken, setLatestToken] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function loadOrg(): Promise<boolean> {
    try {
      const r = await fetch(`${API}/api/orgs/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Error(`조직 정보 로드 실패 (HTTP ${r.status})`);
      setOrg(await r.json());
      return true;
    } catch (e) {
      setErr(e instanceof Error ? e.message : "조직 정보를 불러오지 못했습니다.");
      return false;
    }
  }

  async function loadInvites(): Promise<boolean> {
    try {
      const r = await fetch(`${API}/api/orgs/invitations`, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Error(`초대 목록 로드 실패 (HTTP ${r.status})`);
      setInvites((await r.json()).invitations ?? []);
      return true;
    } catch (e) {
      setErr(e instanceof Error ? e.message : "초대 목록을 불러오지 못했습니다.");
      return false;
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function loadOrganizationState() {
      const ok = await loadOrg();
      if (ok && !cancelled) {
        await loadInvites();
      }
    }
    void loadOrganizationState();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLatestToken(null);
    setSaving(true);
    try {
      const r = await fetch(`${API}/api/orgs/invitations`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ email: email.trim(), role }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      setLatestToken(data.token);
      setEmail("");
      await loadInvites();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "초대 생성 실패");
    } finally {
      setSaving(false);
    }
  }

  const inviteUrl = latestToken && typeof window !== "undefined"
    ? `${window.location.origin}/invite?token=${encodeURIComponent(latestToken)}`
    : null;

  return (
    <section className="mt-20 border-t border-border/50 pt-10">
      <p className="mono text-[12px] text-fg-3 uppercase tracking-wider">ORGANIZATION</p>
      <h2 className="mt-2 font-serif text-[28px] leading-[1.15]">팀 워크스페이스</h2>

      {org && (
        <div className="mt-6 border border-border/50 bg-bg-2/40 p-4">
          <p className="text-[15px] text-fg">{org.name}</p>
          <p className="mono mt-1 text-[11px] text-fg-3">org={org.id} · {org.slug}</p>
          <div className="mt-5 border-t border-border/40">
            {org.members.map((m) => (
              <div key={m.user_id} className="flex items-center justify-between border-b border-border/40 py-2 gap-4">
                <span className="mono text-[12px] text-fg-2 truncate">{m.user_id}</span>
                <span className="mono text-[11px] text-fg-3 uppercase">{m.role}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={invite} className="mt-8 space-y-3">
        <div className="flex flex-wrap gap-3">
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="초대할 이메일"
            type="email"
            className="flex-1 min-w-[240px] bg-bg-2 border border-border px-3 py-2 text-[13px] focus:border-accent focus:outline-none"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as typeof role)}
            className="bg-bg-2 border border-border px-3 py-2 mono text-[13px] focus:border-accent focus:outline-none"
          >
            <option value="analyst">Analyst</option>
            <option value="viewer">Viewer</option>
            <option value="admin">Admin</option>
          </select>
          <button
            type="submit"
            disabled={saving || email.trim().length < 5}
            className="mono text-[13px] text-accent border border-accent px-4 py-2 hover:bg-accent-dim transition-colors disabled:opacity-40"
          >
            {saving ? "creating…" : "invite"}
          </button>
        </div>
        {err && <p className="text-[13px] text-sev-high">⚠ {err}</p>}
        {inviteUrl && (
          <div className="border border-accent/40 bg-accent-dim/20 px-3 py-2">
            <p className="mono text-[11px] text-accent uppercase tracking-wider">Invite link</p>
            <p className="mono mt-1 text-[12px] text-fg-2 break-all">{inviteUrl}</p>
          </div>
        )}
      </form>

      <ul className="mt-8 border-t border-border/40">
        {invites.length === 0 && (
          <li className="py-5 text-[13px] text-fg-3">대기 중인 초대 없음</li>
        )}
        {invites.map((invite) => (
          <li key={invite.id} className="flex items-center justify-between border-b border-border/40 py-3 gap-4">
            <div className="min-w-0">
              <p className="text-[13px] text-fg truncate">{invite.email}</p>
              <p className="mono mt-1 text-[11px] text-fg-3 uppercase">
                {invite.role} · {invite.status}
              </p>
            </div>
            {invite.token && <span className="mono text-[11px] text-fg-3 truncate max-w-[180px]">{invite.token}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

type Alert = {
  id: string;
  channel: string;
  target: string;
  severity: string;
  active: boolean;
};

function AlertsSection({ token }: { token: string }) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [channel, setChannel] = useState<"telegram" | "slack" | "discord">("telegram");
  const [target, setTarget] = useState("");
  const [severity, setSeverity] = useState<"high" | "med" | "low">("med");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    const r = await fetch(`${API}/api/alerts/`, { headers: { Authorization: `Bearer ${token}` } });
    if (r.ok) setAlerts(await r.json());
  }
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/alerts/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ channel, channel_target: target.trim(), severity_threshold: severity }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      setTarget("");
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "실패");
    } finally {
      setLoading(false);
    }
  }

  async function remove(id: string) {
    await fetch(`${API}/api/alerts/${id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
    load();
  }

  const placeholder = {
    telegram: "@username 또는 chat_id (예: -1001234567890)",
    slack: "https://hooks.slack.com/services/…",
    discord: "https://discord.com/api/webhooks/…",
  }[channel];

  return (
    <section className="mt-20 border-t border-border/50 pt-10">
      <p className="mono text-[12px] text-fg-3 uppercase tracking-wider">ALERTS</p>
      <h2 className="mt-2 font-serif text-[28px] leading-[1.15]">이상 공시 알림</h2>
      <p className="mt-3 text-[14px] text-fg-2 leading-[1.7]">
        설정한 심각도 이상의 공시(유상증자·합병·소송 등)가 감지되면 선택한 채널로 전송됩니다.
        Telegram은 bot token 등록 후 chat_id, Slack·Discord는 incoming webhook URL 사용.
      </p>

      <form onSubmit={add} className="mt-8 space-y-3">
        <div className="flex flex-wrap gap-3">
          <select
            value={channel}
            onChange={(e) => setChannel(e.target.value as typeof channel)}
            className="bg-bg-2 border border-border px-3 py-2 mono text-[13px] focus:border-accent focus:outline-none"
          >
            <option value="telegram">Telegram</option>
            <option value="slack">Slack</option>
            <option value="discord">Discord</option>
          </select>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as typeof severity)}
            className="bg-bg-2 border border-border px-3 py-2 mono text-[13px] focus:border-accent focus:outline-none"
          >
            <option value="high">심각도 높음만</option>
            <option value="med">중간 이상</option>
            <option value="low">모든 공시</option>
          </select>
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder={placeholder}
            className="flex-1 min-w-[260px] bg-bg-2 border border-border px-3 py-2 mono text-[13px] focus:border-accent focus:outline-none"
          />
          <button
            type="submit"
            disabled={loading || target.trim().length < 5}
            className="mono text-[13px] text-accent border border-accent px-4 py-2 hover:bg-accent-dim transition-colors disabled:opacity-40"
          >
            {loading ? "…" : "추가"}
          </button>
        </div>
        {err && <p className="text-[13px] text-sev-high">⚠ {err}</p>}
      </form>

      <ul className="mt-8 border-t border-border/40">
        {alerts.length === 0 && (
          <li className="py-6 text-[13px] text-fg-3">설정된 알림 없음</li>
        )}
        {alerts.map((a) => (
          <li key={a.id} className="flex items-center justify-between border-b border-border/40 py-3 gap-4">
            <div className="min-w-0">
              <p className="mono text-[12px] text-fg-3 uppercase tracking-wider">
                {a.channel} · {a.severity}
              </p>
              <p className="text-[13px] text-fg truncate">{a.target}</p>
            </div>
            <button
              onClick={() => remove(a.id)}
              className="mono text-[12px] text-fg-3 hover:text-sev-high shrink-0"
              aria-label={`${a.channel} 알림 제거`}
            >
              remove
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
