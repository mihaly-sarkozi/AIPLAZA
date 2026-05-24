import type { PlatformAdminSecurityMonitoringResponse } from "../../types";
import { domainLabel, formatNumber } from "../../utils/securityMonitoringFormat";

type PlatformMetricsPanelProps = {
  data: PlatformAdminSecurityMonitoringResponse;
  metricValueByKey: (key: string) => string;
};

export default function PlatformMetricsPanel({ data, metricValueByKey }: PlatformMetricsPanelProps) {
  return (
    <>
      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="text-xl font-semibold">Alap platform metrikák</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-sm">
          <div>Kérésszám: <strong>{formatNumber(data.metrics_summary.request_count)}</strong></div>
          <div>Kérés hiba: <strong>{formatNumber(data.metrics_summary.request_error_count)}</strong></div>
          <div>Unhandled hiba: <strong>{formatNumber(data.metrics_summary.unhandled_error_count)}</strong></div>
          <div>Rate-limit találat: <strong>{formatNumber(data.metrics_summary.rate_limit_hit_count)}</strong></div>
          <div>Auth hibák: <strong>{formatNumber(data.metrics_summary.auth_failure_count)}</strong></div>
          <div>Outbox fail: <strong>{formatNumber(data.metrics_summary.outbox_failed_count)}</strong></div>
          <div>Latency átlag (ms): <strong>{formatNumber(data.metrics_summary.request_latency_avg_ms)}</strong></div>
          <div>Latency max (ms): <strong>{formatNumber(data.metrics_summary.request_latency_max_ms)}</strong></div>
          <div>Latency utolsó (ms): <strong>{formatNumber(data.metrics_summary.request_latency_last_ms)}</strong></div>
        </div>
      </section>

      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="text-xl font-semibold">Monitoringba kerülő metrikák</h2>
        <p className="mt-2 text-xs text-[var(--color-muted)]">
          A metrikák domainenként jelennek meg. Az `unavailable` státusz jelzi, ahol még telemetria bekötés szükséges.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
              <tr>
                <th className="py-2 pr-3">Domain</th>
                <th className="py-2 pr-3">Metrika</th>
                <th className="py-2 pr-3">Érték</th>
                <th className="py-2 pr-3">Státusz</th>
                <th className="py-2 pr-3">Megjegyzés</th>
              </tr>
            </thead>
            <tbody>
              {data.monitoring_metrics.map((metric) => (
                <tr key={metric.key} className="border-b border-[var(--color-border)]/60">
                  <td className="py-2 pr-3 text-xs">{domainLabel(metric.domain)}</td>
                  <td className="py-2 pr-3 text-xs">{metric.label}</td>
                  <td className="py-2 pr-3 text-xs">
                    {metric.status === "available" && metric.value !== undefined && metric.value !== null
                      ? `${formatNumber(metric.value)}${metric.unit ? ` ${metric.unit}` : ""}`
                      : "-"}
                  </td>
                  <td className="py-2 pr-3 text-xs">{metric.status}</td>
                  <td className="py-2 pr-3 text-xs text-[var(--color-muted)]">
                    {metric.reason || (metric.details && metric.details.length > 0 ? JSON.stringify(metric.details.slice(0, 3)) : "-")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="text-xl font-semibold">Dashboard sorrend (első kör)</h2>
        <div className="mt-3 grid gap-4 lg:grid-cols-3">
          {[...data.dashboards]
            .sort((a, b) => a.order - b.order)
            .map((dashboard) => (
              <div key={dashboard.id} className="rounded-xl border border-[var(--color-border)] p-4">
                <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{dashboard.order}. dashboard</p>
                <h3 className="mt-1 text-base font-semibold">{dashboard.title}</h3>
                <div className="mt-3 space-y-2">
                  {dashboard.items.map((item, idx) => (
                    <div key={`${dashboard.id}-${idx}`} className="rounded-md border border-[var(--color-border)]/60 p-2 text-xs">
                      <p className="font-medium">{item.label}</p>
                      {item.status === "available" ? (
                        <p className="text-[var(--color-muted)]">
                          {item.metric_key
                            ? metricValueByKey(item.metric_key)
                            : item.value !== undefined && item.value !== null
                              ? `${formatNumber(item.value)}${item.unit ? ` ${item.unit}` : ""}`
                              : "Elérhető"}
                        </p>
                      ) : (
                        <p className="text-[var(--color-muted)]">{item.reason || "Még nincs bekötve"}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
        </div>
      </section>
    </>
  );
}
