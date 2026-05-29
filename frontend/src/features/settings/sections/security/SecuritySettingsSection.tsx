// frontend/src/features/settings/sections/security/SecuritySettingsSection.tsx
// Feladat: Security UI-only szekció komponens authenticator státusz és akciók megjelenítésére.
// Sárközi Mihály - 2026.05.29

import Button from "../../../../components/ui/Button";
import SettingsBlock from "../../components/SettingsBlock";

type SecuritySettingsSectionProps = {
  title: string;
  description: string;
  labels: {
    authenticatorTitle: string;
    authenticatorDescription: string;
    statusEnabled: string;
    statusPending: string;
    statusDisabled: string;
    enableAction: string;
    enablePending: string;
    disableAction: string;
    disablePending: string;
    trialNotice: string;
  };
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
  labels,
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
            <p className="text-sm font-semibold text-[var(--color-foreground)]">{labels.authenticatorTitle}</p>
            <p className="text-xs text-[var(--color-muted)]">{labels.authenticatorDescription}</p>
          </div>
          <span className={`rounded-full px-2 py-1 text-xs ${authenticatorEnabled ? "bg-emerald-500/15 text-emerald-600" : "bg-amber-500/15 text-amber-600"}`}>
            {authenticatorEnabled ? labels.statusEnabled : authenticatorPending ? labels.statusPending : labels.statusDisabled}
          </span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {!authenticatorEnabled ? (
            <Button type="button" onClick={onStart} disabled={startPending || confirmPending}>
              {startPending ? labels.enablePending : labels.enableAction}
            </Button>
          ) : (
            <Button type="button" variant="danger" onClick={onDisable} disabled={disablePending}>
              {disablePending ? labels.disablePending : labels.disableAction}
            </Button>
          )}
        </div>
        <p className="mt-3 text-xs text-[var(--color-muted)]">{labels.trialNotice}</p>
      </div>
    </SettingsBlock>
  );
}
