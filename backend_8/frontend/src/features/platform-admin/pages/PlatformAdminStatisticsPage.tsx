import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { fetchPlatformAdminStatistics } from "../api";
import type { PlatformAdminStatisticsResponse } from "../types";
import PlatformAdminLayout from "./PlatformAdminLayout";
import { formatBytes, formatDate, formatNumber } from "./platformAdminStatsFormat";

const TENANT_BATCH_SIZE = 25;

function Card({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm">
      <p className="text-sm text-[var(--color-muted)]">{label}</p>
      <p className="mt-2 text-3xl font-bold">{value}</p>
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

export default function PlatformAdminStatisticsPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<PlatformAdminStatisticsResponse | null>(null);
  const [visibleCount, setVisibleCount] = useState(TENANT_BATCH_SIZE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchPlatformAdminStatistics()
      .then((overview) => {
        if (!cancelled) {
          setData(overview);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(getApiErrorMessage(err) ?? "Nem sikerült betölteni a platform statisztikát.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setVisibleCount(TENANT_BATCH_SIZE);
  }, [data]);

  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node) return;
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      setVisibleCount((current) => Math.min((data?.tenants.length ?? 0), current + TENANT_BATCH_SIZE));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [data?.tenants.length]);

  const summary = data?.summary;
  const allTenants = data?.tenants ?? [];
  const visibleTenants = allTenants.slice(0, visibleCount);

  return (
    <PlatformAdminLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--color-muted)]">Platform statisztika</p>
            <h1 className="mt-2 text-3xl font-bold">Tenant használat és csomagok</h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--color-muted)]">
              Összesített platform nézet és tenantonkénti lista. A részletek külön oldalon töltődnek be, amikor rákattintasz egy tenant sorára.
            </p>
          </div>
        </div>

        {loading ? <p className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">Statisztika betöltése...</p> : null}
        {error ? <p className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700">{error}</p> : null}

        {!loading && !error && summary ? (
          <>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Card label="Tenantok" value={formatNumber(summary.tenants)} hint={`${formatNumber(summary.active_tenants)} aktív`} />
              <Card label="Lekérdezések" value={formatNumber(summary.questions)} hint="Billing és tudástár lekérdezések alapján" />
              <Card label="Tanítás" value={formatNumber(summary.training_runs)} hint={`${formatNumber(summary.training_items)} feldolgozott elem`} />
              <Card label="Tárhely összesen" value={formatBytes(summary.storage_bytes)} hint={`${formatNumber(summary.knowledge_bases)} tudástár`} />
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Card label="Fájlméret" value={formatBytes(summary.file_bytes)} hint="Feltöltött tanítási fájlok" />
              <Card label="DB méret" value={formatBytes(summary.database_bytes)} hint="PostgreSQL tenant sémák" />
              <Card label="Qdrant méret" value={formatBytes(summary.qdrant_bytes)} hint={`${formatNumber(summary.qdrant_points)} pont`} />
              <Card label="Qdrant vektorok" value={formatNumber(summary.qdrant_vectors)} />
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Card label="Felhasználók" value={formatNumber(summary.users)} />
              <Card label="Tanított karakter" value={formatNumber(summary.trained_chars)} />
              <Card label="Aldomainek" value={formatNumber(summary.domains)} hint={`${formatNumber(summary.verified_domains)} ellenőrzött`} />
              <Card label="Tudástárak" value={formatNumber(summary.knowledge_bases)} />
            </div>

            <Section title="Tenantonkénti bontás">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
                    <tr>
                      <th className="py-3 pr-4">Tenant</th>
                      <th className="py-3 pr-4">Csomag</th>
                      <th className="py-3 pr-4 text-right">Lekérdezés</th>
                      <th className="py-3 pr-4 text-right">Tanítás</th>
                      <th className="py-3 pr-4 text-right">User</th>
                      <th className="py-3 pr-4 text-right">KB</th>
                      <th className="py-3 pr-4 text-right">Fájl</th>
                      <th className="py-3 pr-4 text-right">DB</th>
                      <th className="py-3 pr-4 text-right">Qdrant</th>
                      <th className="py-3 pr-4 text-right">Domain</th>
                      <th className="py-3 pr-4">Utolsó aktivitás</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleTenants.map((tenant) => (
                      <tr
                        key={tenant.id}
                        className="cursor-pointer border-b border-[var(--color-border)]/60 hover:bg-[var(--color-card-muted)]"
                        onClick={() => navigate(`/platform-admin/statistics/tenants/${tenant.id}`)}
                      >
                        <td className="py-3 pr-4">
                          <p className="font-semibold">{tenant.name}</p>
                          <p className="text-xs text-[var(--color-muted)]">{tenant.slug}</p>
                        </td>
                        <td className="py-3 pr-4">
                          <p>{tenant.package_name || tenant.package_code || "free"}</p>
                          <p className="text-xs text-[var(--color-muted)]">{tenant.subscription_status || "-"}</p>
                        </td>
                        <td className="py-3 pr-4 text-right font-semibold">{formatNumber(tenant.usage.questions)}</td>
                        <td className="py-3 pr-4 text-right">{formatNumber(tenant.usage.training_runs)}</td>
                        <td className="py-3 pr-4 text-right">{formatNumber(tenant.usage.users)}</td>
                        <td className="py-3 pr-4 text-right">{formatNumber(tenant.usage.knowledge_bases)}</td>
                        <td className="py-3 pr-4 text-right">{formatBytes(tenant.usage.file_bytes)}</td>
                        <td className="py-3 pr-4 text-right">{formatBytes(tenant.usage.database_bytes)}</td>
                        <td className="py-3 pr-4 text-right">
                          <p>{formatBytes(tenant.usage.qdrant_bytes)}</p>
                          <p className="text-xs text-[var(--color-muted)]">{formatNumber(tenant.usage.qdrant_points)} pont</p>
                        </td>
                        <td className="py-3 pr-4 text-right">
                          {formatNumber(tenant.domain_count)} / {formatNumber(tenant.verified_domain_count)}
                        </td>
                        <td className="py-3 pr-4 text-xs text-[var(--color-muted)]">
                          Lekérdezés: {formatDate(tenant.usage.last_query_at)}
                          <br />
                          Tanítás: {formatDate(tenant.usage.last_training_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div ref={loadMoreRef} className="py-4 text-center text-xs text-[var(--color-muted)]">
                  {visibleCount < allTenants.length
                    ? "További tenantok betöltése..."
                    : `${formatNumber(allTenants.length)} tenant megjelenítve`}
                </div>
              </div>
            </Section>
          </>
        ) : null}
      </div>
    </PlatformAdminLayout>
  );
}
