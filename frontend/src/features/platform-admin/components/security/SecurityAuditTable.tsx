import type { PlatformAdminSecurityMonitoringResponse } from "../../types";
import { formatNumber } from "../../utils/securityMonitoringFormat";

type SecurityAuditTableProps = {
  data: PlatformAdminSecurityMonitoringResponse;
};

export default function SecurityAuditTable({ data }: SecurityAuditTableProps) {
  return (
    <>
      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="text-xl font-semibold">Első körös figyelők / alert szabályok</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
              <tr>
                <th className="py-2 pr-3">Prioritás</th>
                <th className="py-2 pr-3">Szabály</th>
                <th className="py-2 pr-3">Státusz</th>
                <th className="py-2 pr-3">Érték / küszöb</th>
                <th className="py-2 pr-3">Ablak</th>
                <th className="py-2 pr-3">Megjegyzés</th>
              </tr>
            </thead>
            <tbody>
              {data.alert_rule_results.map((rule) => (
                <tr key={rule.rule_id} className="border-b border-[var(--color-border)]/60">
                  <td className="py-2 pr-3 text-xs font-semibold">{rule.priority}</td>
                  <td className="py-2 pr-3 text-xs">{rule.title}</td>
                  <td className="py-2 pr-3 text-xs">{rule.status === "triggered" ? "TRIGGERED" : rule.status === "ok" ? "OK" : "UNAVAILABLE"}</td>
                  <td className="py-2 pr-3 text-xs">
                    {rule.value !== undefined && rule.value !== null
                      ? `${formatNumber(rule.value)}${rule.threshold !== undefined && rule.threshold !== null ? ` / ${formatNumber(rule.threshold)}` : ""}`
                      : "-"}
                  </td>
                  <td className="py-2 pr-3 text-xs">{rule.window_minutes ? `${rule.window_minutes} perc` : "-"}</td>
                  <td className="py-2 pr-3 text-xs text-[var(--color-muted)]">{rule.reason || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="text-xl font-semibold">Bekötött események státusza</h2>
        <p className="mt-2 text-xs text-[var(--color-muted)]">
          Az első körös event-taxonómia szerinti bontás (auth/security/business/system), 24 órás észleléssel.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
              <tr>
                <th className="py-2 pr-3">Esemény</th>
                <th className="py-2 pr-3">Kategória</th>
                <th className="py-2 pr-3">Darab</th>
                <th className="py-2 pr-3">Státusz</th>
              </tr>
            </thead>
            <tbody>
              {data.event_stream_summary.map((item) => (
                <tr key={item.event} className="border-b border-[var(--color-border)]/60">
                  <td className="py-2 pr-3 text-xs font-mono">{item.event}</td>
                  <td className="py-2 pr-3 text-xs">{item.category}</td>
                  <td className="py-2 pr-3 text-xs">{formatNumber(item.count)}</td>
                  <td className="py-2 pr-3 text-xs">{item.status === "active" ? "Aktív" : "Nem detektált"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
