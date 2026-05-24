import type { PlatformAdminSecurityMonitoringResponse } from "../../types";
import { formatNumber } from "../../utils/securityMonitoringFormat";

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
      <p className="text-sm text-[var(--color-muted)]">{label}</p>
      <p className="mt-2 text-3xl font-bold">{value}</p>
    </div>
  );
}

export default function SecuritySummaryCards({ summary }: { summary: PlatformAdminSecurityMonitoringResponse["summary"] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Kockázati esemény (24h)" value={formatNumber(summary.risk_events_total)} />
      <StatCard label="Sikertelen belépés (24h)" value={formatNumber(summary.failed_login)} />
      <StatCard label="Sikertelen refresh (24h)" value={formatNumber(summary.failed_refresh)} />
      <StatCard label="Rate-limit esemény (24h)" value={formatNumber(summary.rate_limited)} />
    </div>
  );
}
