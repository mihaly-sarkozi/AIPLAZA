import type { PlatformAdminSecurityMonitoringResponse } from "../../types";
import { formatNumber, readinessBadgeClass, readinessLabel } from "../../utils/securityMonitoringFormat";

export default function MvpReadinessPanel({ readiness }: { readiness: PlatformAdminSecurityMonitoringResponse["mvp_readiness"] }) {
  return (
    <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">MVP readiness</h2>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${readinessBadgeClass(readiness.status)}`}>
          {readinessLabel(readiness.status)}
        </span>
      </div>
      <p className="mt-2 text-sm text-[var(--color-muted)]">
        Score: <strong>{formatNumber(readiness.score_percent)}%</strong> · Bekötött checklist:{" "}
        <strong>{formatNumber(readiness.configured_checks)}</strong> / <strong>{formatNumber(readiness.total_checks)}</strong> · Hiányzó:{" "}
        <strong>{formatNumber(readiness.missing_checks)}</strong> · Triggered: <strong>{formatNumber(readiness.triggered_checks)}</strong>
      </p>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {readiness.checks.map((check) => (
          <div key={check.id} className="rounded-lg border border-[var(--color-border)] p-3 text-xs">
            <p className="font-semibold">{check.label}</p>
            <p className="mt-1 text-[var(--color-muted)]">
              Konfiguráció: {check.configured ? "OK" : "HIÁNYZIK"} · Futásidő: {check.runtime_status.toUpperCase()}
            </p>
            {check.detail ? <p className="mt-1 text-[var(--color-muted)]">{check.detail}</p> : null}
          </div>
        ))}
      </div>
    </section>
  );
}
