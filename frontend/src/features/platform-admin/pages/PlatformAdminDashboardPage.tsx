import { useEffect, useState } from "react";

import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { fetchPlatformAdminStatistics } from "../api";
import { usePlatformAdminStore } from "../state";
import type { PlatformAdminStatisticsResponse, PlatformAdminStatisticsTenant } from "../types";
import PlatformAdminLayout from "./PlatformAdminLayout";

function formatNumber(value: unknown): string {
  return new Intl.NumberFormat("hu-HU").format(Number(value ?? 0));
}

function formatMoneyCents(value: unknown): string {
  const cents = Number(value ?? 0);
  return `${new Intl.NumberFormat("hu-HU", { maximumFractionDigits: 0 }).format(Math.round(cents / 100))} €`;
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
      <p className="text-sm text-[var(--color-muted)]">{label}</p>
      <p className="mt-3 text-3xl font-bold">{value}</p>
      {hint ? <p className="mt-2 text-xs text-[var(--color-muted)]">{hint}</p> : null}
    </div>
  );
}

export default function PlatformAdminDashboardPage() {
  const { token, user, loadingUser } = usePlatformAdminStore();
  const [statistics, setStatistics] = useState<PlatformAdminStatisticsResponse | null>(null);
  const [loadingTenants, setLoadingTenants] = useState(true);
  const [tenantError, setTenantError] = useState<string | null>(null);

  useEffect(() => {
    if (loadingUser || !user || !token) return;
    let cancelled = false;
    setLoadingTenants(true);
    fetchPlatformAdminStatistics()
      .then((result) => {
        if (!cancelled) {
          setStatistics(result);
          setTenantError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setTenantError(getApiErrorMessage(err) ?? "Nem sikerült betölteni az aktív tenantokat.");
      })
      .finally(() => {
        if (!cancelled) setLoadingTenants(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadingUser, token, user]);

  const summary = statistics?.summary;
  const tenants: PlatformAdminStatisticsTenant[] = statistics?.tenants ?? [];
  const activeTenants = tenants.filter((tenant) => tenant.is_active);

  return (
    <PlatformAdminLayout>
      <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--color-muted)]">Monitoring</p>
        <h1 className="mt-2 text-3xl font-bold">Fő admin áttekintés</h1>
        <p className="mt-2 max-w-2xl text-[var(--color-muted)]">
          Itt kapnak majd helyet a platform szintű statisztikák, tenant állapotok és monitoring adatok.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Regisztrációk száma" value={loadingTenants ? "..." : formatNumber(summary?.tenants)} hint="Tenantok összesen" />
        <StatCard label="Tudástárak száma" value={loadingTenants ? "..." : formatNumber(summary?.knowledge_bases)} />
        <StatCard label="Felhasználók száma" value={loadingTenants ? "..." : formatNumber(summary?.users)} />
        <StatCard label="Adott évben befizetett összeg" value={loadingTenants ? "..." : formatMoneyCents(summary?.paid_this_year_cents)} />
        <StatCard label="Várható éves bevétel" value={loadingTenants ? "..." : formatMoneyCents(summary?.expected_annual_revenue_cents)} />
        <StatCard label="Várható átlagos havi bevétel" value={loadingTenants ? "..." : formatMoneyCents(summary?.expected_average_monthly_revenue_cents)} />
      </div>
      <div className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Aktív tenantok</h2>
            <p className="text-sm text-[var(--color-muted)]">A public tenant nyilvántartás jelenleg aktív elemei.</p>
          </div>
        </div>
        {tenantError ? <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{tenantError}</p> : null}
        {!tenantError && loadingTenants ? <p className="text-sm text-[var(--color-muted)]">Tenantok betöltése...</p> : null}
        {!tenantError && !loadingTenants && activeTenants.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">Nincs aktív tenant.</p>
        ) : null}
        {!tenantError && activeTenants.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
                <tr>
                  <th className="py-3 pr-4 font-medium">Név</th>
                  <th className="py-3 pr-4 font-medium">Slug</th>
                  <th className="py-3 pr-4 font-medium">Létrehozva</th>
                  <th className="py-3 pr-4 font-medium">Állapot</th>
                </tr>
              </thead>
              <tbody>
                {activeTenants.map((tenant) => (
                  <tr key={tenant.id} className="border-b border-[var(--color-border)]/60">
                    <td className="py-3 pr-4 font-medium">{tenant.name}</td>
                    <td className="py-3 pr-4">{tenant.slug}</td>
                    <td className="py-3 pr-4">
                      {tenant.created_at ? new Date(tenant.created_at).toLocaleDateString("hu-HU") : "-"}
                    </td>
                    <td className="py-3 pr-4">
                      <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-700">Aktív</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
      </div>
    </PlatformAdminLayout>
  );
}

