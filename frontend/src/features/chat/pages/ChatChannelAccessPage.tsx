import { type ReactNode, useEffect, useMemo, useState } from "react";

import {
  createChannelCredential,
  getChannelAnalyticsSummary,
  getChannelInstructions,
  listChannelCredentials,
  revokeChannelCredential,
  rotateChannelCredential,
  type ChannelCredentialCreatePayload,
  type ChannelCredentialItem,
} from "../services/channelAccessApi";

function InputLabel({ children }: { children: ReactNode }) {
  return <label className="text-xs font-medium text-[var(--color-muted)]">{children}</label>;
}

function normalizeOrigin(raw: string): string {
  const value = raw.trim().toLowerCase();
  if (!value) return "";
  if (value.includes("*")) {
    throw new Error("Wildcard origin nem engedélyezett.");
  }
  const withScheme = value.includes("://") ? value : `https://${value}`;
  let parsed: URL;
  try {
    parsed = new URL(withScheme);
  } catch {
    throw new Error("Érvénytelen origin formátum. Használj domaint vagy protocol+host értéket.");
  }
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Origin protocol csak http vagy https lehet.");
  }
  if (parsed.pathname !== "/" || parsed.search || parsed.hash || parsed.username || parsed.password) {
    throw new Error("Origin csak protocol+host lehet (útvonal/query nélkül).");
  }
  return parsed.port ? `${parsed.protocol}//${parsed.hostname}:${parsed.port}` : `${parsed.protocol}//${parsed.hostname}`;
}

function parseOrigins(text: string): string[] {
  const unique = new Set<string>();
  for (const item of text.split(",")) {
    const normalized = normalizeOrigin(item);
    if (!normalized) continue;
    unique.add(normalized);
  }
  return Array.from(unique);
}

export default function ChatChannelAccessPage() {
  const [items, setItems] = useState<ChannelCredentialItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [createdSecret, setCreatedSecret] = useState<string>("");
  const [instructions, setInstructions] = useState<Record<string, unknown> | null>(null);
  const [analytics, setAnalytics] = useState<Record<string, unknown> | null>(null);
  const [form, setForm] = useState<ChannelCredentialCreatePayload>({
    channel_type: "widget",
    name: "",
    allowed_kb_uuids: [],
    daily_limit: 200,
    per_minute_limit: 30,
    allowed_origins: [],
  });
  const [originsText, setOriginsText] = useState("");
  const [kbText, setKbText] = useState("");

  const hasItems = items.length > 0;
  const widgetOriginMissing = form.channel_type === "widget" && originsText.trim().length === 0;

  async function refreshData() {
    setLoading(true);
    setError("");
    try {
      const [credentials, summary] = await Promise.all([listChannelCredentials(), getChannelAnalyticsSummary(14)]);
      setItems(credentials);
      setAnalytics(summary);
    } catch (err) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Nem sikerült betölteni az adatokat.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshData();
  }, []);

  const summaryText = useMemo(() => {
    if (!analytics) return "Nincs analitika adat.";
    const total = Number(analytics.total_requests || 0);
    const avgMs = Number(analytics.avg_total_ms || 0);
    const helpful = Number(analytics.feedback_helpful || 0);
    const notHelpful = Number(analytics.feedback_not_helpful || 0);
    return `Kérések: ${total} | Átlag válaszidő: ${avgMs.toFixed(0)} ms | Pozitív feedback: ${helpful} | Negatív feedback: ${notHelpful}`;
  }, [analytics]);

  async function onCreate(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const normalizedOrigins = parseOrigins(originsText);
      if (form.channel_type === "widget" && normalizedOrigins.length === 0) {
        throw new Error("Widget credentialhez legalább egy allowed origin kötelező.");
      }
      const payload: ChannelCredentialCreatePayload = {
        ...form,
        name: form.name.trim(),
        allowed_kb_uuids: kbText
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        allowed_origins: normalizedOrigins,
      };
      const created = await createChannelCredential(payload);
      setCreatedSecret(created.secret || "");
      await refreshData();
    } catch (err) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Létrehozás sikertelen.");
    }
  }

  async function onRotate(id: number) {
    setError("");
    try {
      const rotated = await rotateChannelCredential(id);
      setCreatedSecret(rotated.secret || "");
      await refreshData();
    } catch (err) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Rotáció sikertelen.");
    }
  }

  async function onRevoke(id: number) {
    setError("");
    try {
      await revokeChannelCredential(id);
      await refreshData();
    } catch (err) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Visszavonás sikertelen.");
    }
  }

  async function onInstructions(id: number) {
    setError("");
    try {
      const data = await getChannelInstructions(id);
      setInstructions(data as Record<string, unknown>);
    } catch (err) {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Instrukciók lekérése sikertelen.");
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 p-4 text-[var(--color-foreground)]">
      <h1 className="text-xl font-semibold">AI Widget / API hozzáférés</h1>
      <p className="text-sm text-[var(--color-muted)]">
        Itt tudsz widget vagy API hozzáférést generálni, tudástár-scope-ot és limiteket beállítani, valamint az analitikát követni.
      </p>

      <div className="rounded-xl border border-[var(--color-border)] p-3 text-sm">{summaryText}</div>

      <form onSubmit={onCreate} className="grid gap-3 rounded-xl border border-[var(--color-border)] p-4 md:grid-cols-2">
        <div className="flex flex-col gap-1">
          <InputLabel>Csatorna típus</InputLabel>
          <select
            value={form.channel_type}
            onChange={(event) => setForm((prev) => ({ ...prev, channel_type: event.target.value as "widget" | "api" }))}
            className="rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
          >
            <option value="widget">Widget</option>
            <option value="api">API</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <InputLabel>Név</InputLabel>
          <input
            value={form.name}
            onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            className="rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
            placeholder="Példa: PartnerX Widget"
          />
        </div>
        <div className="flex flex-col gap-1">
          <InputLabel>Napi kérdéslimit</InputLabel>
          <input
            type="number"
            value={form.daily_limit}
            onChange={(event) => setForm((prev) => ({ ...prev, daily_limit: Number(event.target.value || 0) }))}
            className="rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <InputLabel>Percenkénti limit</InputLabel>
          <input
            type="number"
            value={form.per_minute_limit}
            onChange={(event) => setForm((prev) => ({ ...prev, per_minute_limit: Number(event.target.value || 0) }))}
            className="rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1 md:col-span-2">
          <InputLabel>Allowed origin hostok (vesszővel)</InputLabel>
          <input
            value={originsText}
            onChange={(event) => setOriginsText(event.target.value)}
            className="rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
            placeholder="pelda.hu,www.pelda.hu"
          />
          <div className="text-xs text-[var(--color-muted)]">
            Widgetnél kötelező. A rendszer protocol+host formára normalizál (pl. <code>https://pelda.hu</code>).
          </div>
        </div>
        <div className="flex flex-col gap-1 md:col-span-2">
          <InputLabel>Elérhető KB UUID-k (vesszővel, üres = tenant scope)</InputLabel>
          <input
            value={kbText}
            onChange={(event) => setKbText(event.target.value)}
            className="rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
            placeholder="kb-uuid-1,kb-uuid-2"
          />
        </div>
        <div className="md:col-span-2">
          <button
            type="submit"
            disabled={widgetOriginMissing}
            className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-[var(--color-on-primary)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            Hozzáférés létrehozása
          </button>
          {widgetOriginMissing ? (
            <div className="mt-2 text-xs text-amber-300">Widget credential csak allowed originnel hozható létre.</div>
          ) : null}
        </div>
      </form>

      {createdSecret ? (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
          <div className="mb-1 font-semibold">Új secret (csak most látható):</div>
          <code className="break-all">{createdSecret}</code>
        </div>
      ) : null}

      {error ? <div className="rounded-lg border border-red-500/40 bg-red-500/5 p-3 text-sm">{error}</div> : null}

      <div className="rounded-xl border border-[var(--color-border)] p-4">
        <h2 className="mb-3 text-base font-semibold">Generált hozzáférések</h2>
        {loading ? <div className="text-sm text-[var(--color-muted)]">Betöltés...</div> : null}
        {!loading && !hasItems ? <div className="text-sm text-[var(--color-muted)]">Még nincs létrehozott credential.</div> : null}
        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.id} className="rounded-lg border border-[var(--color-border)] p-3 text-sm">
              <div className="font-medium">
                #{item.id} - {item.name} ({item.channel_type})
              </div>
              <div className="text-[var(--color-muted)]">
                prefix: <code>{item.key_prefix}</code> | státusz: {item.status} | daily: {item.daily_limit} | rpm: {item.per_minute_limit}
              </div>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={() => void onInstructions(item.id)}
                  className="rounded border border-[var(--color-border)] px-3 py-1 text-xs"
                >
                  Beépítési leírás
                </button>
                <button
                  type="button"
                  onClick={() => void onRotate(item.id)}
                  className="rounded border border-[var(--color-border)] px-3 py-1 text-xs"
                >
                  Secret rotáció
                </button>
                <button
                  type="button"
                  onClick={() => void onRevoke(item.id)}
                  className="rounded border border-[var(--color-border)] px-3 py-1 text-xs text-red-300"
                >
                  Visszavonás
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {instructions ? (
        <div className="rounded-xl border border-[var(--color-border)] p-4 text-sm">
          <h2 className="mb-2 text-base font-semibold">Beépítési útmutató</h2>
          <div className="mb-2">
            <div className="text-xs text-[var(--color-muted)]">Endpoint</div>
            <code className="break-all">{String(instructions.endpoint || "")}</code>
          </div>
          <div className="mb-2">
            <div className="text-xs text-[var(--color-muted)]">Widget snippet</div>
            <pre className="overflow-auto rounded-lg border border-[var(--color-border)] p-2 text-xs">{String(instructions.widget_embed_snippet || "")}</pre>
          </div>
          <div>
            <div className="text-xs text-[var(--color-muted)]">API példa (curl)</div>
            <pre className="overflow-auto rounded-lg border border-[var(--color-border)] p-2 text-xs">
              {String((instructions.api_example as { curl?: string } | undefined)?.curl || "")}
            </pre>
          </div>
        </div>
      ) : null}
    </div>
  );
}

