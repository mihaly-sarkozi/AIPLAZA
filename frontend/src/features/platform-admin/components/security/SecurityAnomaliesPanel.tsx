import type { PlatformAdminSecurityMonitoringResponse } from "../../types";

export default function SecurityAnomaliesPanel({ data }: { data: PlatformAdminSecurityMonitoringResponse }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="text-xl font-semibold">Duplikált user gyanú (azonos email több tenantban)</h2>
        {data.duplicate_users.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--color-muted)]">Nem találtunk duplikált email mintát tenantok között.</p>
        ) : (
          <div className="mt-3 space-y-2">
            {data.duplicate_users.slice(0, 20).map((item) => (
              <div key={item.email} className="rounded-lg border border-[var(--color-border)] p-2 text-xs">
                <p className="font-semibold">{item.email}</p>
                <p className="text-[var(--color-muted)]">tenantok: {item.tenants.join(", ")}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
        <h2 className="text-xl font-semibold">Egy user több IP-ről (24h)</h2>
        {data.concurrent_ip_anomalies.length === 0 ? (
          <p className="mt-3 text-sm text-[var(--color-muted)]">Nincs kiugró egyidejű IP anomália.</p>
        ) : (
          <div className="mt-3 space-y-2">
            {data.concurrent_ip_anomalies.slice(0, 30).map((item, index) => (
              <div key={`${item.tenant}-${item.user_id}-${index}`} className="rounded-lg border border-[var(--color-border)] p-2 text-xs">
                tenant: <strong>{item.tenant}</strong> · user_id: <strong>{item.user_id}</strong> · IP darab:{" "}
                <strong>{item.distinct_ip_count_24h}</strong>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
