import { useEffect, useState } from "react";

import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  acknowledgePlatformSecurityAlert,
  banPlatformSecurityIp,
  fetchPlatformAdminSecurityMonitoring,
  unbanPlatformSecurityIp,
} from "../api";
import type { PlatformAdminSecurityMonitoringResponse } from "../types";
import PlatformAdminLayout from "./PlatformAdminLayout";

function formatNumber(value: number | undefined): string {
  return new Intl.NumberFormat("hu-HU").format(Number(value ?? 0));
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
      <p className="text-sm text-[var(--color-muted)]">{label}</p>
      <p className="mt-2 text-3xl font-bold">{value}</p>
    </div>
  );
}

function domainLabel(domain: string): string {
  if (domain === "application") return "Alkalmazás";
  if (domain === "auth_security") return "Auth / security";
  if (domain === "infrastructure") return "Infrastructure";
  if (domain === "business") return "Üzleti egészség";
  return domain;
}

function readinessLabel(status: "green" | "yellow" | "red"): string {
  if (status === "green") return "MVP ready";
  if (status === "yellow") return "Részben kész";
  return "Blokkolt";
}

function readinessBadgeClass(status: "green" | "yellow" | "red"): string {
  if (status === "green") return "border-green-200 bg-green-50 text-green-700";
  if (status === "yellow") return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-red-200 bg-red-50 text-red-700";
}

export default function PlatformAdminSecurityMonitoringPage() {
  const [data, setData] = useState<PlatformAdminSecurityMonitoringResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyIp, setBusyIp] = useState<string | null>(null);
  const [busyAlertId, setBusyAlertId] = useState<number | null>(null);

  const loadMonitoring = async () => {
    setLoading(true);
    const result = await fetchPlatformAdminSecurityMonitoring();
    setData(result);
    setError(null);
    setLoading(false);
  };

  useEffect(() => {
    let cancelled = false;
    loadMonitoring()
      .then(() => undefined)
      .catch((err) => {
        if (cancelled) return;
        setError(getApiErrorMessage(err) ?? "Nem sikerült betölteni a monitoring adatokat.");
        setLoading(false);
      })
      .finally(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const handleBanIp = async (ip: string) => {
    if (!ip) return;
    const reason = window.prompt("Tiltás oka (opcionális):", "Gyakori sikertelen auth próbálkozás");
    setBusyIp(ip);
    try {
      await banPlatformSecurityIp({ ip, reason: reason || undefined, expires_hours: 24 });
      await loadMonitoring();
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "IP tiltás sikertelen.");
    } finally {
      setBusyIp(null);
    }
  };

  const handleUnbanIp = async (ip: string) => {
    if (!ip) return;
    setBusyIp(ip);
    try {
      await unbanPlatformSecurityIp(ip);
      await loadMonitoring();
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "IP feloldás sikertelen.");
    } finally {
      setBusyIp(null);
    }
  };

  const handleAckAlert = async (alertId: number) => {
    setBusyAlertId(alertId);
    try {
      await acknowledgePlatformSecurityAlert(alertId);
      await loadMonitoring();
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Riasztás nyugtázása sikertelen.");
    } finally {
      setBusyAlertId(null);
    }
  };

  const metricValueByKey = (key: string): string => {
    const metric = data?.monitoring_metrics.find((item) => item.key === key);
    if (!metric || metric.value === undefined || metric.value === null) return "-";
    return `${formatNumber(metric.value)}${metric.unit ? ` ${metric.unit}` : ""}`;
  };

  return (
    <PlatformAdminLayout>
      <div className="space-y-6">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--color-muted)]">Biztonság</p>
          <h1 className="mt-2 text-3xl font-bold">Monitoring és támadásfigyelés</h1>
          <p className="mt-2 max-w-3xl text-sm text-[var(--color-muted)]">
            A nézet személyes adat nélkül mutatja a biztonsági mintákat: sikertelen token/session műveletek, rate-limit események,
            gyanús források és regisztrációs anomáliák.
          </p>
        </div>

        {loading ? <p className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">Monitoring betöltése...</p> : null}
        {error ? <p className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700">{error}</p> : null}

        {!loading && !error && data ? (
          <>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Kockázati esemény (24h)" value={formatNumber(data.summary.risk_events_total)} />
              <StatCard label="Sikertelen belépés (24h)" value={formatNumber(data.summary.failed_login)} />
              <StatCard label="Sikertelen refresh (24h)" value={formatNumber(data.summary.failed_refresh)} />
              <StatCard label="Rate-limit esemény (24h)" value={formatNumber(data.summary.rate_limited)} />
            </div>

            <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-xl font-semibold">MVP readiness</h2>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${readinessBadgeClass(data.mvp_readiness.status)}`}>
                  {readinessLabel(data.mvp_readiness.status)}
                </span>
              </div>
              <p className="mt-2 text-sm text-[var(--color-muted)]">
                Score: <strong>{formatNumber(data.mvp_readiness.score_percent)}%</strong> · Bekötött checklist:{" "}
                <strong>{formatNumber(data.mvp_readiness.configured_checks)}</strong> /{" "}
                <strong>{formatNumber(data.mvp_readiness.total_checks)}</strong> · Hiányzó:{" "}
                <strong>{formatNumber(data.mvp_readiness.missing_checks)}</strong> · Triggered:{" "}
                <strong>{formatNumber(data.mvp_readiness.triggered_checks)}</strong>
              </p>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {data.mvp_readiness.checks.map((check) => (
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
                          {metric.reason ||
                            (metric.details && metric.details.length > 0
                              ? JSON.stringify(metric.details.slice(0, 3))
                              : "-")}
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
                                {item.metric_key ? metricValueByKey(item.metric_key) : item.value !== undefined && item.value !== null ? `${formatNumber(item.value)}${item.unit ? ` ${item.unit}` : ""}` : "Elérhető"}
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
                                onClick={() => void handleAckAlert(alert.id)}
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
                        <td className="py-2 pr-3 text-xs">
                          {rule.status === "triggered" ? "TRIGGERED" : rule.status === "ok" ? "OK" : "UNAVAILABLE"}
                        </td>
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
                  <p>
                    Új tenant 24h: <strong>{formatNumber(data.signup_watch.new_tenants_24h)}</strong>
                  </p>
                  <p>
                    Új tenant 7 nap: <strong>{formatNumber(data.signup_watch.new_tenants_7d)}</strong>
                  </p>
                  <p>
                    Új tenant 30 nap: <strong>{formatNumber(data.signup_watch.new_tenants_30d)}</strong>
                  </p>
                  <p>
                    7 napon belüli új, de tanítás nélküli tenant:{" "}
                    <strong>{formatNumber(data.signup_watch.new_tenants_without_training_7d)}</strong>
                  </p>
                </div>
              </section>
            </div>

            <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
              <h2 className="text-xl font-semibold">Részletes események (IP látható)</h2>
              <p className="mt-2 text-xs text-[var(--color-muted)]">
                A "possible_test_traffic" jelzi, ha valószínű tesztforgalom (pl. pytest) lehet.
              </p>
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
                              onClick={() => void handleBanIp(event.ip as string)}
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
                          <td className="py-2 pr-3 text-xs">
                            {item.expires_at ? new Date(item.expires_at).toLocaleString("hu-HU") : "Nincs lejárat"}
                          </td>
                          <td className="py-2 pr-3 text-xs">{item.active ? "Igen" : "Nem"}</td>
                          <td className="py-2 pr-3 text-right">
                            {item.active ? (
                              <button
                                type="button"
                                disabled={busyIp === item.ip}
                                onClick={() => void handleUnbanIp(item.ip)}
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
          </>
        ) : null}
      </div>
    </PlatformAdminLayout>
  );
}
