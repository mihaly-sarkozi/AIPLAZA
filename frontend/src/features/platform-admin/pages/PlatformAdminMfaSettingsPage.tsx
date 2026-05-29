import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";

import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  confirmPlatformAdminMfaSetup,
  fetchPlatformAdminMfaStatus,
  startPlatformAdminMfaSetup,
} from "../api";
import type { PlatformAdminMfaSetupResponse, PlatformAdminMfaStatusResponse } from "../types";
import PlatformAdminLayout from "./PlatformAdminLayout";

export default function PlatformAdminMfaSettingsPage() {
  const [status, setStatus] = useState<PlatformAdminMfaStatusResponse | null>(null);
  const [setupData, setSetupData] = useState<PlatformAdminMfaSetupResponse | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(await fetchPlatformAdminMfaStatus());
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Nem sikerült betölteni az MFA állapotot.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadStatus();
  }, []);

  const startSetup = async () => {
    setPending(true);
    setError(null);
    setRecoveryCodes([]);
    try {
      setSetupData(await startPlatformAdminMfaSetup());
      setCode("");
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Nem sikerült elindítani az MFA beállítást.");
    } finally {
      setPending(false);
    }
  };

  const confirmSetup = async () => {
    if (code.length !== 6 || pending) return;
    setPending(true);
    setError(null);
    try {
      const result = await confirmPlatformAdminMfaSetup(code);
      setRecoveryCodes(result.recovery_codes ?? []);
      setSetupData(null);
      setCode("");
      await loadStatus();
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Érvénytelen MFA kód.");
    } finally {
      setPending(false);
    }
  };

  return (
    <PlatformAdminLayout>
      <div className="mx-auto max-w-3xl space-y-6">
        <PageHeader
          eyebrow="Főadmin biztonság"
          title="MFA beállítás"
          description="Google Authenticator vagy kompatibilis alkalmazás bekapcsolása a főadmin belépéshez."
        />

        {error ? <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}

        <section className="app-surface p-6">
          <p className="text-sm font-medium text-[var(--color-muted)]">Állapot</p>
          <p className="mt-2 text-xl font-semibold text-[var(--color-foreground)]">
            {loading ? "Betöltés..." : status?.enabled ? "MFA bekapcsolva" : "MFA nincs bekapcsolva"}
          </p>
          {status?.enabled ? (
            <p className="mt-2 text-sm text-[var(--color-muted)]">
              Recovery kódok száma: {status.recovery_codes_remaining}
            </p>
          ) : (
            <Button type="button" className="mt-4" onClick={startSetup} disabled={pending || loading}>
              {pending ? "Előkészítés..." : "Google Authenticator beállítása"}
            </Button>
          )}
        </section>

        {setupData ? (
          <section className="app-surface p-6">
            <h2 className="text-lg font-semibold text-[var(--color-foreground)]">Authenticator telepítése</h2>
            <p className="mt-2 text-sm text-[var(--color-muted)]">
              Olvasd be a QR kódot az authenticator alkalmazással, majd add meg a 6 számjegyű kódot.
            </p>
            <div className="mt-4 inline-flex rounded border border-[var(--color-border)] bg-white p-2">
              <QRCodeSVG value={setupData.otpauth_uri} size={190} includeMargin bgColor="#ffffff" fgColor="#111827" />
            </div>
            <p className="mt-3 text-xs text-[var(--color-muted)]">Manuális kulcs: {setupData.secret}</p>
            <div className="mt-4 flex flex-wrap items-end gap-2">
              <input
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="123456"
                maxLength={6}
                className="w-40 rounded-xl border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
                disabled={pending}
              />
              <Button type="button" onClick={confirmSetup} disabled={code.length !== 6 || pending}>
                {pending ? "Ellenőrzés..." : "Bekapcsolás"}
              </Button>
            </div>
          </section>
        ) : null}

        {recoveryCodes.length > 0 ? (
          <section className="app-surface p-6">
            <h2 className="text-lg font-semibold text-[var(--color-foreground)]">Recovery kódok</h2>
            <p className="mt-2 text-sm text-[var(--color-muted)]">
              Mentsd el őket biztonságos helyre. Ezekkel tudsz belépni, ha nincs nálad az authenticator.
            </p>
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {recoveryCodes.map((item) => (
                <code key={item} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] px-3 py-2 text-sm">
                  {item}
                </code>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </PlatformAdminLayout>
  );
}
