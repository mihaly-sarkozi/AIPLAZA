import type { PlatformAdminSecurityMonitoringResponse } from "../../types";
import { formatNumber } from "../../utils/securityMonitoringFormat";

type SuspiciousIpPanelProps = {
  data: PlatformAdminSecurityMonitoringResponse;
  busyIp: string | null;
  onBanIp: (ip: string) => void;
  onUnbanIp: (ip: string) => void;
};

export default function SuspiciousIpPanel({ data, busyIp, onBanIp, onUnbanIp }: SuspiciousIpPanelProps) {
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <h2 className="text-xl font-semibold">Támadott tenantok/hostok</h2>
          {data.tenant_hotspots.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--color-muted)]">Nincs kiugró tenant hotspot.</p>
          ) : (
            <div className="mt-3 space-y-2 text-sm">
              {data.tenant_hotspots.map((item) => (
                <div key={`${item.tenant}-${item.risk_events}`} className="rounded-lg border border-[var(--color-border)] p-2">
                  <p className="font-semibold">{item.host}</p>
                  <p className="text-xs text-[var(--color-muted)]">
                    tenant: {item.tenant} · esemény: {formatNumber(item.risk_events)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <h2 className="text-xl font-semibold">Top gyanús források (hash)</h2>
          <p className="mt-2 text-xs text-[var(--color-muted)]">IP címek hash-elve vannak; a nézet nem jelenít meg személyes adatot.</p>
          {data.top_sources.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--color-muted)]">Nincs forrás adat.</p>
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
                  <tr>
                    <th className="py-2 pr-4">Forrás hash</th>
                    <th className="py-2 pr-4 text-right">Kockázati esemény</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_sources.map((source) => (
                    <tr key={source.source_hash} className="border-b border-[var(--color-border)]/60">
                      <td className="py-2 pr-4 font-mono text-xs">{source.source_hash}</td>
                      <td className="py-2 pr-4 text-right">{formatNumber(source.risk_events)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
          <h2 className="text-xl font-semibold">Regisztrációs figyelő</h2>
          <div className="mt-3 space-y-2 text-sm">
            <p>Új tenant 24h: <strong>{formatNumber(data.signup_watch.new_tenants_24h)}</strong></p>
            <p>Új tenant 7 nap: <strong>{formatNumber(data.signup_watch.new_tenants_7d)}</strong></p>
            <p>Új tenant 30 nap: <strong>{formatNumber(data.signup_watch.new_tenants_30d)}</strong></p>
            <p>7 napon belüli új, de tanítás nélküli tenant: <strong>{formatNumber(data.signup_watch.new_tenants_without_training_7d)}</strong></p>
          </div>
        </section>
      </div>

      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="text-xl font-semibold">Részletes események (IP látható)</h2>
        <p className="mt-2 text-xs text-[var(--color-muted)]">A "possible_test_traffic" jelzi, ha valószínű tesztforgalom (pl. pytest) lehet.</p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
              <tr>
                <th className="py-2 pr-3">Idő</th>
                <th className="py-2 pr-3">Host/Tenant</th>
                <th className="py-2 pr-3">Esemény</th>
                <th className="py-2 pr-3">Súlyosság</th>
                <th className="py-2 pr-3">IP</th>
                <th className="py-2 pr-3">Teszt?</th>
                <th className="py-2 pr-3 text-right">Művelet</th>
              </tr>
            </thead>
            <tbody>
              {data.events.slice(0, 80).map((event, index) => (
                <tr key={`${event.created_at}-${event.action}-${index}`} className="border-b border-[var(--color-border)]/60">
                  <td className="py-2 pr-3 text-xs">{event.created_at ? new Date(event.created_at).toLocaleString("hu-HU") : "-"}</td>
                  <td className="py-2 pr-3 text-xs">{event.host || event.tenant || "-"}</td>
                  <td className="py-2 pr-3 text-xs">{event.action}</td>
                  <td className="py-2 pr-3 text-xs">{event.severity}</td>
                  <td className="py-2 pr-3 font-mono text-xs">{event.ip || "-"}</td>
                  <td className="py-2 pr-3 text-xs">{event.possible_test_traffic ? "Lehetséges" : "Nem"}</td>
                  <td className="py-2 pr-3 text-right">
                    {event.ip ? (
                      <button
                        type="button"
                        disabled={busyIp === event.ip}
                        onClick={() => onBanIp(event.ip as string)}
                        className="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-60"
                      >
                        Tiltás
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <BannedIpsTable data={data} busyIp={busyIp} onUnbanIp={onUnbanIp} />
    </>
  );
}

function BannedIpsTable({
  data,
  busyIp,
  onUnbanIp,
}: {
  data: PlatformAdminSecurityMonitoringResponse;
  busyIp: string | null;
  onUnbanIp: (ip: string) => void;
}) {
  return (
    <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
      <h2 className="text-xl font-semibold">Tiltott IP-k</h2>
      {data.banned_ips.length === 0 ? (
        <p className="mt-3 text-sm text-[var(--color-muted)]">Nincs aktív vagy történeti tiltott IP.</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-[var(--color-border)] text-[var(--color-muted)]">
              <tr>
                <th className="py-2 pr-3">IP</th>
                <th className="py-2 pr-3">Ok</th>
                <th className="py-2 pr-3">Lejárat</th>
                <th className="py-2 pr-3">Aktív</th>
                <th className="py-2 pr-3 text-right">Művelet</th>
              </tr>
            </thead>
            <tbody>
              {data.banned_ips.slice(0, 100).map((item) => (
                <tr key={`${item.ip}-${item.created_at}`} className="border-b border-[var(--color-border)]/60">
                  <td className="py-2 pr-3 font-mono text-xs">{item.ip}</td>
                  <td className="py-2 pr-3 text-xs">{item.reason || "-"}</td>
                  <td className="py-2 pr-3 text-xs">{item.expires_at ? new Date(item.expires_at).toLocaleString("hu-HU") : "Nincs lejárat"}</td>
                  <td className="py-2 pr-3 text-xs">{item.active ? "Igen" : "Nem"}</td>
                  <td className="py-2 pr-3 text-right">
                    {item.active ? (
                      <button
                        type="button"
                        disabled={busyIp === item.ip}
                        onClick={() => onUnbanIp(item.ip)}
                        className="rounded border border-[var(--color-border)] px-2 py-1 text-xs hover:bg-[var(--color-border)]/30 disabled:opacity-60"
                      >
                        Feloldás
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
  );
}
