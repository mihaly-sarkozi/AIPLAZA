import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";

import Button from "../../../components/ui/Button";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  confirmPlatformAdminMfaSetup,
  fetchPlatformAdminMfaStatus,
  startPlatformAdminMfaSetup,
} from "../api";
import type { PlatformAdminMfaSetupResponse } from "../types";

type PlatformAdminMfaRequiredProps = {
  onCompleted: () => void;
};

export default function PlatformAdminMfaRequired({ onCompleted }: PlatformAdminMfaRequiredProps) {
  const [setupData, setSetupData] = useState<PlatformAdminMfaSetupResponse | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const status = await fetchPlatformAdminMfaStatus();
        if (status.enabled) {
          onCompleted();
          return;
        }
        const setup = await startPlatformAdminMfaSetup();
        if (!cancelled) setSetupData(setup);
      } catch (err) {
        if (!cancelled) setError(getApiErrorMessage(err) ?? "Nem sikerült elindítani az MFA telepítést.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [onCompleted]);

  const confirm = async () => {
    if (code.length !== 6 || confirming) return;
    setConfirming(true);
    setError(null);
    try {
      const result = await confirmPlatformAdminMfaSetup(code);
      setRecoveryCodes(result.recovery_codes ?? []);
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Érvénytelen MFA kód.");
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-background)] px-4 py-10 text-[var(--color-foreground)]">
      <div className="mx-auto max-w-2xl rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] p-8 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--color-muted)]">Fő admin biztonság</p>
        <h1 className="mt-2 text-3xl font-bold">MFA kötelező telepítése</h1>
        <p className="mt-3 text-sm leading-6 text-[var(--color-muted)]">
          A főadmin felület használatához Google Authenticator vagy kompatibilis alkalmazás szükséges.
        </p>

        {error ? <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}
        {loading ? <p className="mt-6 text-sm text-[var(--color-muted)]">MFA telepítés előkészítése...</p> : null}

        {!loading && setupData && recoveryCodes.length === 0 ? (
          <div className="mt-6 space-y-5">
            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
              <p className="text-sm font-semibold">1. Telepíts authenticator alkalmazást</p>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Használhatsz Google Authenticatort, Microsoft Authenticatort vagy 1Passwordot.
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
              <p className="text-sm font-semibold">2. Olvasd be a QR kódot</p>
              <div className="mt-3 inline-flex rounded border border-[var(--color-border)] bg-white p-2">
                <QRCodeSVG value={setupData.otpauth_uri} size={190} includeMargin bgColor="#ffffff" fgColor="#111827" />
              </div>
              <p className="mt-3 text-xs text-[var(--color-muted)]">Manuális kulcs: {setupData.secret}</p>
            </div>
            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
              <p className="text-sm font-semibold">3. Add meg a 6 számjegyű kódot</p>
              <div className="mt-3 flex flex-wrap items-end gap-2">
                <input
                  value={code}
                  onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="123456"
                  maxLength={6}
                  className="w-40 rounded-xl border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
                  disabled={confirming}
                />
                <Button type="button" onClick={confirm} disabled={code.length !== 6 || confirming}>
                  {confirming ? "Ellenőrzés..." : "MFA bekapcsolása"}
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {recoveryCodes.length > 0 ? (
          <div className="mt-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
            <p className="text-sm font-semibold">Recovery kódok</p>
            <p className="mt-1 text-sm text-[var(--color-muted)]">
              Ezeket mentsd el biztonságos helyre. Később ezekkel tudsz belépni, ha elveszik az authenticator.
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {recoveryCodes.map((item) => (
                <code key={item} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm">
                  {item}
                </code>
              ))}
            </div>
            <Button type="button" className="mt-4" onClick={onCompleted}>
              Tovább a főadmin felületre
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
