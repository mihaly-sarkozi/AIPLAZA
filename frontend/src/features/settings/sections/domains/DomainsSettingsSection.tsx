// frontend/src/features/settings/sections/domains/DomainsSettingsSection.tsx
// Feladat: Domain settings UI-only szekció komponens API hívások nélkül.
// Sárközi Mihály - 2026.05.29

import Button from "../../../../components/ui/Button";
import SettingsBlock from "../../components/SettingsBlock";
import type { DomainRow } from "./domainTypes";

type DomainsSettingsSectionProps = {
  title: string;
  description: string;
  primaryDomain: string;
  activeHost?: string | null;
  showActiveCustomHost: boolean;
  customDomainInput: string;
  customDomains: DomainRow[];
  isLoading: boolean;
  addPending: boolean;
  verifyPending: boolean;
  deletePending: boolean;
  t: (key: string) => string;
  getDomainStateLabel: (state: DomainRow["state"]) => string;
  setCustomDomainInput: (value: string) => void;
  onAdd: () => void;
  onVerify: (domain: string) => void;
  onDelete: (domain: string) => void;
  onCopy: (value: string) => void;
};

export default function DomainsSettingsSection({
  title,
  description,
  primaryDomain,
  activeHost,
  showActiveCustomHost,
  customDomainInput,
  customDomains,
  isLoading,
  addPending,
  verifyPending,
  deletePending,
  t,
  getDomainStateLabel,
  setCustomDomainInput,
  onAdd,
  onVerify,
  onDelete,
  onCopy,
}: DomainsSettingsSectionProps) {
  return (
    <SettingsBlock title={title} description={description}>
      <div className="space-y-4">
        <DomainInstructions t={t} />
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-3 text-sm">
          <p className="text-[var(--color-muted)]">{t("settings.domainPrimary")}</p>
          <p className="font-medium text-[var(--color-foreground)]">{primaryDomain}</p>
          {showActiveCustomHost ? (
            <>
              <p className="mt-2 text-[var(--color-muted)]">{t("settings.domainActiveHost")}</p>
              <p className="font-medium text-[var(--color-foreground)]">{activeHost ?? "-"}</p>
            </>
          ) : null}
        </div>
        <div className="grid gap-2 md:grid-cols-[1fr_auto]">
          <label className="block text-sm text-[var(--color-label)]">
            {t("settings.domainInputLabel")}
            <input
              value={customDomainInput}
              onChange={(event) => setCustomDomainInput(event.target.value)}
              placeholder={t("settings.domainPlaceholder")}
              className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
              disabled={addPending}
            />
          </label>
          <div className="flex items-end pb-1">
            <Button type="button" onClick={onAdd} disabled={!customDomainInput.trim() || addPending}>
              {addPending ? t("common.loading") : t("settings.domainAddButton")}
            </Button>
          </div>
        </div>
        {isLoading ? <p className="text-sm text-[var(--color-muted)]">{t("common.loading")}</p> : null}
        {!isLoading && customDomains.length === 0 ? <p className="text-sm text-[var(--color-muted)]">{t("settings.domainEmpty")}</p> : null}
        {customDomains.length > 0 ? (
          <DomainTable
            customDomains={customDomains}
            verifyPending={verifyPending}
            deletePending={deletePending}
            t={t}
            getDomainStateLabel={getDomainStateLabel}
            onCopy={onCopy}
            onVerify={onVerify}
            onDelete={onDelete}
          />
        ) : null}
      </div>
    </SettingsBlock>
  );
}

function DomainInstructions({ t }: { t: (key: string) => string }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-3 text-sm">
      <p className="font-semibold text-[var(--color-foreground)]">{t("settings.domainHowToTitle")}</p>
      <ol className="mt-2 list-decimal space-y-1 pl-5 text-[var(--color-muted)]">
        <li>{t("settings.domainHowToStep1")}</li>
        <li>{t("settings.domainHowToStep2")}</li>
        <li>{t("settings.domainHowToStep3")}</li>
      </ol>
      <p className="mt-3 text-[var(--color-muted)]">{t("settings.domainDnsTargetHint")}</p>
    </div>
  );
}

function DomainTable({
  customDomains,
  verifyPending,
  deletePending,
  t,
  getDomainStateLabel,
  onCopy,
  onVerify,
  onDelete,
}: Pick<DomainsSettingsSectionProps, "customDomains" | "verifyPending" | "deletePending" | "t" | "getDomainStateLabel" | "onCopy" | "onVerify" | "onDelete">) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
      <table className="w-full text-sm">
        <thead className="border-b border-[var(--color-border)] text-left text-[var(--color-muted)]">
          <tr>
            <th className="px-3 py-2">{t("settings.domainInputLabel")}</th>
            <th className="px-3 py-2">{t("settings.domainStatusLabel")}</th>
            <th className="px-3 py-2 text-right">{t("settings.domainActionLabel")}</th>
          </tr>
        </thead>
        <tbody>
          {customDomains.map((domain) => (
            <tr key={domain.domain} className="border-b border-[var(--color-border)]/60 last:border-b-0 align-top">
              <td className="px-3 py-2">{domain.domain}</td>
              <td className="px-3 py-2">
                <span className="rounded-full bg-[var(--color-card-muted)] px-2 py-1 text-xs">{getDomainStateLabel(domain.state)}</span>
                {domain.state === "custom_pending" ? <DnsInstruction domain={domain} t={t} onCopy={onCopy} /> : null}
              </td>
              <td className="px-3 py-2 text-right">
                <div className="inline-flex gap-2">
                  {domain.state === "custom_pending" ? (
                    <Button type="button" variant="secondary" onClick={() => onVerify(domain.domain)} disabled={verifyPending || deletePending}>
                      {verifyPending ? t("common.loading") : t("settings.domainVerifyButton")}
                    </Button>
                  ) : null}
                  <Button type="button" variant="danger" onClick={() => onDelete(domain.domain)} disabled={deletePending || verifyPending}>
                    {deletePending ? t("common.loading") : t("settings.domainDeleteButton")}
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DnsInstruction({ domain, t, onCopy }: { domain: DomainRow; t: (key: string) => string; onCopy: (value: string) => void }) {
  return (
    <div className="mt-2 space-y-1 text-xs text-[var(--color-muted)]">
      <p>
        {t("settings.domainHostInstruction")} <span className="font-medium text-[var(--color-foreground)]">{domain.dns_record_name ?? "-"}</span>
        <CopyButton label={t("settings.domainCopyButton")} onClick={() => onCopy(`${domain.dns_record_name ?? "-"}`)} />
      </p>
      <p>
        {t("settings.domainTokenInstruction")} <span className="font-medium text-[var(--color-foreground)]">{domain.dns_record_value ?? "-"}</span>
        <CopyButton label={t("settings.domainCopyButton")} onClick={() => onCopy(`${domain.dns_record_value ?? "-"}`)} />
      </p>
    </div>
  );
}

function CopyButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="ml-2 inline-flex items-center rounded border border-[var(--color-border)] px-2 py-0.5 text-[11px] text-[var(--color-foreground)] hover:bg-[var(--color-card)]"
    >
      {label}
    </button>
  );
}
