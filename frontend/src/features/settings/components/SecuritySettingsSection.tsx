import Button from "../../../components/ui/Button";
import SettingsBlock from "./SettingsBlock";

type SecuritySettingsSectionProps = {
  title: string;
  description: string;
  authenticatorEnabled: boolean;
  authenticatorPending: boolean;
  startPending: boolean;
  confirmPending: boolean;
  disablePending: boolean;
  onStart: () => void;
  onDisable: () => void;
};

export default function SecuritySettingsSection({
  title,
  description,
  authenticatorEnabled,
  authenticatorPending,
  startPending,
  confirmPending,
  disablePending,
  onStart,
  onDisable,
}: SecuritySettingsSectionProps) {
  return (
    <SettingsBlock title={title} description={description}>
      <div className="mt-6 rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-[var(--color-foreground)]">Google Authenticator (TOTP)</p>
            <p className="text-xs text-[var(--color-muted)]">Belépéskor email kód helyett Google Authenticator alkalmazás kódját használod.</p>
          </div>
          <span className={`rounded-full px-2 py-1 text-xs ${authenticatorEnabled ? "bg-emerald-500/15 text-emerald-600" : "bg-amber-500/15 text-amber-600"}`}>
            {authenticatorEnabled ? "Bekapcsolva" : authenticatorPending ? "Folyamatban" : "Kikapcsolva"}
          </span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {!authenticatorEnabled ? (
            <Button type="button" onClick={onStart} disabled={startPending || confirmPending}>
              {startPending ? "Bekapcsolás..." : "Google Authenticator bekapcsolása"}
            </Button>
          ) : (
            <Button type="button" variant="danger" onClick={onDisable} disabled={disablePending}>
              {disablePending ? "Kikapcsolás..." : "Google Authenticator kikapcsolása"}
            </Button>
          )}
        </div>
        <p className="mt-3 text-xs text-[var(--color-muted)]">
          Próbaidőszak alatt opcionális a 2FA, de előfizetés indításához kötelező az Authenticator aktiválása.
        </p>
      </div>
    </SettingsBlock>
  );
}
