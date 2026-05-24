import SecurityAlertsPanel from "../components/security/SecurityAlertsPanel";
import SecurityAnomaliesPanel from "../components/security/SecurityAnomaliesPanel";
import SecurityAuditTable from "../components/security/SecurityAuditTable";
import SecuritySummaryCards from "../components/security/SecuritySummaryCards";
import MvpReadinessPanel from "../components/security/MvpReadinessPanel";
import PlatformMetricsPanel from "../components/security/PlatformMetricsPanel";
import SuspiciousIpPanel from "../components/security/SuspiciousIpPanel";
import { useSecurityMonitoring } from "../hooks/useSecurityMonitoring";
import { formatNumber } from "../utils/securityMonitoringFormat";
import PlatformAdminLayout from "./PlatformAdminLayout";

export default function PlatformAdminSecurityMonitoringPage() {
  const { data, loading, error, busyIp, busyAlertId, handleBanIp, handleUnbanIp, handleAckAlert } = useSecurityMonitoring();

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
            <SecuritySummaryCards summary={data.summary} />
            <MvpReadinessPanel readiness={data.mvp_readiness} />
            <PlatformMetricsPanel data={data} metricValueByKey={metricValueByKey} />
            <SecurityAlertsPanel data={data} busyAlertId={busyAlertId} onAckAlert={(alertId) => void handleAckAlert(alertId)} />
            <SecurityAuditTable data={data} />
            <SuspiciousIpPanel
              data={data}
              busyIp={busyIp}
              onBanIp={(ip) => void handleBanIp(ip)}
              onUnbanIp={(ip) => void handleUnbanIp(ip)}
            />
            <SecurityAnomaliesPanel data={data} />
          </>
        ) : null}
      </div>
    </PlatformAdminLayout>
  );
}
