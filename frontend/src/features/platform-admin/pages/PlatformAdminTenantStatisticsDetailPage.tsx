import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { fetchPlatformAdminTenantStatistics } from "../api";
import type { PlatformAdminTenantStatisticsDetail } from "../types";
import PlatformAdminLayout from "./PlatformAdminLayout";
import { formatBytes, formatDate, formatDateOnly, formatMoneyCents, formatNumber } from "./platformAdminStatsFormat";

type ChartKey = "training_chars" | "questions" | "usage_hours";

const LIMIT_LABELS: Record<string, { label: string; unit?: string; formatter?: (value: number) => string }> = {
  max_users: { label: "Felhasználók száma", unit: "fő" },
  users: { label: "Felhasználók száma", unit: "fő" },
  knowledge_bases: { label: "Tudástárak száma", unit: "db" },
  storage_gb: { label: "Tárhely", unit: "GB" },
  training_chars_available: { label: "Tanítási karakterkeret", unit: "karakter" },
  included_training_chars: { label: "Alap tanítási karakterkeret", unit: "karakter" },
  questions_monthly: { label: "Havi kérdéskeret", unit: "kérdés" },
  included_questions_monthly: { label: "Havi kérdéskeret", unit: "kérdés" },
};

function humanizeLimitKey(key: string): string {
  return LIMIT_LABELS[key]?.label ?? key.replace(/_/g, " ");
}

function formatLimitValue(key: string, value: unknown): string {
  if (value == null) return "-";
  if (typeof value === "boolean") return value ? "igen" : "nem";
  if (typeof value === "number") {
    const formatter = LIMIT_LABELS[key]?.formatter ?? formatNumber;
    const unit = LIMIT_LABELS[key]?.unit;
    return `${formatter(value)}${unit ? ` ${unit}` : ""}`;
  }
  if (typeof value === "string") return value;
  return "-";
}

function limitUsageText(key: string, detail: PlatformAdminTenantStatisticsDetail): string | null {
  const currentMonth = detail.monthly[detail.monthly.length - 1];
  switch (key) {
    case "max_users":
    case "users":
      return `Felhasználva: ${formatNumber(detail.usage.users)} fő`;
    case "knowledge_bases":
      return `Felhasználva: ${formatNumber(detail.usage.knowledge_bases)} db`;
    case "storage_gb":
      return `Felhasználva: ${formatBytes(detail.usage.storage_bytes)}`;
    case "training_chars_available":
    case "included_training_chars":
      return `Felhasználva: ${formatNumber(detail.usage.trained_chars)} karakter`;
    case "questions_monthly":
    case "included_questions_monthly":
      return `Felhasználva ebben a hónapban: ${formatNumber(currentMonth?.questions ?? 0)} kérdés`;
    default:
      return null;
  }
}

function formatThousandChars(value: number): string {
  const thousands = Number(value || 0) / 1000;
  const formatted = thousands.toLocaleString("hu-HU", { maximumFractionDigits: thousands >= 10 ? 0 : 1 });
  return `${formatted} e`;
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm">
      <p className="text-sm text-[var(--color-muted)]">{label}</p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
      {hint ? <p className="mt-2 text-xs text-[var(--color-muted)]">{hint}</p> : null}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm">
      <h2 className="mb-4 text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function AreaChart({
  title,
  unit,
  data,
  valueKey,
  formatter,
}: {
  title: string;
  unit: string;
  data: PlatformAdminTenantStatisticsDetail["monthly"];
  valueKey: ChartKey;
  formatter: (value: number) => string;
}) {
  const width = 640;
  const height = 220;
  const padX = 64;
  const padY = 24;
  const values = data.map((item) => Number(item[valueKey] || 0));
  const maxValue = Math.max(1, ...values);
  const yTicks = [maxValue, maxValue * 0.75, maxValue * 0.5, maxValue * 0.25, 0];
  const step = data.length > 1 ? (width - padX * 2) / (data.length - 1) : 0;
  const points = values.map((value, index) => {
    const x = padX + index * step;
    const y = height - padY - (value / maxValue) * (height - padY * 2);
    return { x, y, value, month: data[index]?.month ?? "" };
  });
  const line = points.map((point) => `${point.x},${point.y}`).join(" ");
  const area = `${padX},${height - padY} ${line} ${width - padX},${height - padY}`;

  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">{title}</h3>
          <p className="text-xs text-[var(--color-muted)]">Utolsó 12 hónap, mérték: {unit}</p>
        </div>
        <p className="text-sm font-semibold text-[var(--color-muted)]">Max: {formatter(maxValue)}</p>
      </div>
      <div className="mt-4 overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} className="min-w-[560px]">
          <defs>
            <linearGradient id={`${valueKey}-fill`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="var(--color-primary)" stopOpacity="0.35" />
              <stop offset="100%" stopColor="var(--color-primary)" stopOpacity="0.04" />
            </linearGradient>
          </defs>
          {yTicks.map((tick) => {
            const y = height - padY - (tick / maxValue) * (height - padY * 2);
            return (
              <g key={`${valueKey}-tick-${tick}`}>
                <line x1={padX} x2={width - padX} y1={y} y2={y} stroke="var(--color-border)" strokeWidth="1" strokeOpacity="0.55" />
                <text x={padX - 10} y={y + 4} textAnchor="end" fontSize="10" fill="var(--color-muted)">
                  {formatter(Math.round(tick))}
                </text>
              </g>
            );
          })}
          <polyline points={`${padX},${padY} ${padX},${height - padY} ${width - padX},${height - padY}`} fill="none" stroke="var(--color-border)" strokeWidth="1" />
          <polygon points={area} fill={`url(#${valueKey}-fill)`} />
          <polyline points={line} fill="none" stroke="var(--color-primary)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          {points.map((point) => (
            <g key={`${valueKey}-${point.month}`}>
              <circle cx={point.x} cy={point.y} r="4" fill="var(--color-primary)" />
              <title>{`${point.month}: ${formatter(point.value)}`}</title>
            </g>
          ))}
          {points.map((point, index) => (
            <text key={`${valueKey}-label-${point.month}`} x={point.x} y={height - 6} textAnchor="middle" fontSize="10" fill="var(--color-muted)">
              {index % 2 === 0 ? point.month.slice(5) : ""}
            </text>
          ))}
        </svg>
      </div>
    </div>
  );
}

export default function PlatformAdminTenantStatisticsDetailPage() {
  const navigate = useNavigate();
  const params = useParams();
  const tenantId = Number(params.tenantId);
  const [detail, setDetail] = useState<PlatformAdminTenantStatisticsDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(tenantId) || tenantId <= 0) {
      setError("Érvénytelen tenant azonosító.");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchPlatformAdminTenantStatistics(tenantId)
      .then((result) => {
        if (!cancelled) {
          setDetail(result);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(getApiErrorMessage(err) ?? "Nem sikerült betölteni a tenant részleteit.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  return (
    <PlatformAdminLayout>
      <div className="space-y-6">
        <button
          type="button"
          className="rounded-xl border border-[var(--color-border)] px-3 py-2 text-sm hover:bg-[var(--color-card-muted)]"
          onClick={() => navigate("/platform-admin/statistics")}
        >
          Vissza a statisztikához
        </button>

        {loading ? <p className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">Tenant részletek betöltése...</p> : null}
        {error ? <p className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700">{error}</p> : null}

        {!loading && !error && detail ? (
          <>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--color-muted)]">Tenant részletek</p>
              <h1 className="mt-2 text-3xl font-bold">{detail.tenant.name}</h1>
              <p className="mt-1 text-sm text-[var(--color-muted)]">Slug: {detail.tenant.slug}</p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Státusz" value={detail.billing.status || "-"} hint={detail.tenant.is_active ? "Aktív tenant" : "Inaktív tenant"} />
              <StatCard label="Regisztráció ideje" value={formatDate(detail.tenant.created_at)} />
              <StatCard
                label="Aktuális időszak"
                value={`${formatDateOnly(detail.billing.current_period?.start_iso)} - ${formatDateOnly(detail.billing.current_period?.end_iso)}`}
                hint={detail.billing.billing_period || "monthly"}
              />
              <StatCard label="Eddig fizetett számlák" value={formatMoneyCents(detail.billing.paid_total_cents)} hint={`${formatNumber(detail.billing.paid_invoice_count)} db fizetett számla`} />
              <StatCard label="Lekérdezések" value={`${formatNumber(detail.usage.questions)} kérdés`} />
              <StatCard label="Tanítás" value={`${formatNumber(detail.usage.trained_chars)} karakter`} hint={`${formatNumber(detail.usage.training_runs)} futás`} />
              <StatCard label="Fájlméret" value={formatBytes(detail.usage.file_bytes)} />
              <StatCard label="DB + Qdrant" value={`${formatBytes(detail.usage.database_bytes)} / ${formatBytes(detail.usage.qdrant_bytes)}`} />
            </div>

            <div className="grid gap-4">
              <AreaChart title="Tanítás havonta" unit="e" data={detail.monthly} valueKey="training_chars" formatter={formatThousandChars} />
              <AreaChart title="Kérdések száma havonta" unit="kérdés" data={detail.monthly} valueKey="questions" formatter={(value) => `${formatNumber(value)} kérdés`} />
              <AreaChart title="Használati órák havonta" unit="óra" data={detail.monthly} valueKey="usage_hours" formatter={(value) => `${formatNumber(value)} óra`} />
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <Section title="Limitek">
                <div className="grid gap-2 text-sm">
                  {Object.entries(detail.limits).map(([key, value]) => (
                    <div key={key} className="flex justify-between gap-4 border-b border-[var(--color-border)]/60 pb-2 last:border-b-0">
                      <span className="text-[var(--color-muted)]">{humanizeLimitKey(key)}</span>
                      <span className="text-right">
                        <span className="block font-semibold">{formatLimitValue(key, value)}</span>
                        {limitUsageText(key, detail) ? (
                          <span className="block text-xs text-[var(--color-muted)]">{limitUsageText(key, detail)}</span>
                        ) : null}
                      </span>
                    </div>
                  ))}
                  {Object.keys(detail.limits).length === 0 ? <p className="text-[var(--color-muted)]">Nincs limit adat.</p> : null}
                </div>
              </Section>

              <Section title="Tenant és csomag adatok">
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between gap-4 border-b border-[var(--color-border)] pb-2">
                    <span className="text-[var(--color-muted)]">Tenant név</span>
                    <span className="font-semibold">{detail.tenant.name}</span>
                  </div>
                  <div className="flex justify-between gap-4 border-b border-[var(--color-border)] pb-2">
                    <span className="text-[var(--color-muted)]">Slug</span>
                    <span>{detail.tenant.slug}</span>
                  </div>
                  <div className="flex justify-between gap-4 border-b border-[var(--color-border)] pb-2">
                    <span className="text-[var(--color-muted)]">Csomag</span>
                    <span className="text-right">
                      <span className="block font-semibold">{detail.billing.package_name || detail.billing.package_code || "free"}</span>
                    </span>
                  </div>
                  <div className="flex justify-between gap-4 border-b border-[var(--color-border)] pb-2">
                    <span className="text-[var(--color-muted)]">Utolsó kérdés</span>
                    <span>{formatDate(detail.usage.last_query_at)}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-[var(--color-muted)]">Utolsó tanítás</span>
                    <span>{formatDate(detail.usage.last_training_at)}</span>
                  </div>
                </div>
              </Section>
            </div>

            <Section title="Aldomainek">
              <div className="grid gap-2 md:grid-cols-2">
                {detail.domains.map((domain) => (
                  <div key={domain.domain} className="flex items-center justify-between gap-4 rounded-xl border border-[var(--color-border)] p-3">
                    <div>
                      <p className="font-medium">{domain.domain}</p>
                      <p className="text-xs text-[var(--color-muted)]">Létrehozva: {formatDate(domain.created_at)}</p>
                    </div>
                    <span className={domain.verified ? "text-sm font-semibold text-green-600" : "text-sm font-semibold text-amber-600"}>
                      {domain.verified ? "Ellenőrzött" : "Nincs ellenőrizve"}
                    </span>
                  </div>
                ))}
                {detail.domains.length === 0 ? <p className="text-sm text-[var(--color-muted)]">Nincs domain rekord.</p> : null}
              </div>
            </Section>
          </>
        ) : null}
      </div>
    </PlatformAdminLayout>
  );
}

