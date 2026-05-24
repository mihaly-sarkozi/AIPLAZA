import type { PlatformAdminSecurityMonitoringResponse } from "../../types";
import { formatNumber } from "../../utils/securityMonitoringFormat";

type SecurityAlertsPanelProps = {
  data: PlatformAdminSecurityMonitoringResponse;
  busyAlertId: number | null;
  onAckAlert: (alertId: number) => void;
};

export default function SecurityAlertsPanel({ data, busyAlertId, onAckAlert }: SecurityAlertsPanelProps) {
  return (
    <>
      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="text-xl font-semibold">AI alapú kockázati összefoglaló</h2>
        <p className="mt-3 text-sm text-[var(--color-muted)]">{data.ai_assessment}</p>
      </section>

      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="text-xl font-semibold">Támadási jelzések</h2>
        {data.attack_signals.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--color-muted)]">Nincs kiugró jelzés az aktuális ablakban.</p>
        ) : (
          <div className="mt-3 space-y-2">
            {data.attack_signals.map((signal) => (
              <div key={`${signal.signal}-${signal.value}`} className="rounded-xl border border-[var(--color-border)] p-3">
                <p className="text-sm font-semibold">{signal.signal}</p>
                <p className="text-xs text-[var(--color-muted)]">
                  Súlyosság: {signal.severity} · Érték: {formatNumber(signal.value)}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="text-xl font-semibold">Riasztások (nyugtázható)</h2>
        {data.alerts.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--color-muted)]">Nincs nyitott vagy történeti riasztás.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
                <tr>
                  <th className="py-2 pr-3">Riasztás</th>
                  <th className="py-2 pr-3">Severity</th>
                  <th className="py-2 pr-3">Érték</th>
                  <th className="py-2 pr-3">Találat</th>
                  <th className="py-2 pr-3">Állapot</th>
                  <th className="py-2 pr-3 text-right">Művelet</th>
                </tr>
              </thead>
              <tbody>
                {data.alerts.slice(0, 50).map((alert) => (
                  <tr key={alert.id} className="border-b border-[var(--color-border)]/60">
                    <td className="py-2 pr-3 text-xs">{alert.title}</td>
                    <td className="py-2 pr-3 text-xs">{alert.severity}</td>
                    <td className="py-2 pr-3 text-xs">{formatNumber(alert.value)}</td>
                    <td className="py-2 pr-3 text-xs">{formatNumber(alert.hit_count)}</td>
                    <td className="py-2 pr-3 text-xs">{alert.status}</td>
                    <td className="py-2 pr-3 text-right">
                      {alert.status === "open" ? (
                        <button
                          type="button"
                          disabled={busyAlertId === alert.id}
                          onClick={() => onAckAlert(alert.id)}
                          className="rounded border border-[var(--color-border)] px-2 py-1 text-xs hover:bg-[var(--color-border)]/30 disabled:opacity-60"
                        >
                          Nyugtázás
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
