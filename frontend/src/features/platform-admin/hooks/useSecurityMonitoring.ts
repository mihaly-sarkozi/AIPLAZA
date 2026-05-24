import { useEffect, useState } from "react";

import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  acknowledgePlatformSecurityAlert,
  banPlatformSecurityIp,
  fetchPlatformAdminSecurityMonitoring,
  unbanPlatformSecurityIp,
} from "../api";
import type { PlatformAdminSecurityMonitoringResponse } from "../types";

export function useSecurityMonitoring() {
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

  return {
    data,
    loading,
    error,
    busyIp,
    busyAlertId,
    handleBanIp,
    handleUnbanIp,
    handleAckAlert,
  };
}
