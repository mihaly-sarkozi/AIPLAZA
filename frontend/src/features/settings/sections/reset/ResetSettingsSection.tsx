import Button from "../../../../components/ui/Button";
import Alert from "../../../../components/ui/Alert";

type ResetSettingsSectionProps = {
  title: string;
  description: string;
  warning: string;
  confirmLabel: string;
  confirmPlaceholder: string;
  confirmSlug: string;
  expectedSlug: string | null;
  slugHint: string;
  submitLabel: string;
  pending: boolean;
  error: string | null;
  onConfirmSlugChange: (value: string) => void;
  onSubmit: () => void;
};

export default function ResetSettingsSection({
  title,
  description,
  warning,
  confirmLabel,
  confirmPlaceholder,
  confirmSlug,
  expectedSlug,
  slugHint,
  submitLabel,
  pending,
  error,
  onConfirmSlugChange,
  onSubmit,
}: ResetSettingsSectionProps) {
  const slugMatches =
    expectedSlug != null && confirmSlug.trim().toLowerCase() === expectedSlug.trim().toLowerCase();

  return (
    <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 space-y-5">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-[var(--color-foreground)]">{title}</h2>
        <p className="text-sm text-[var(--color-muted-foreground)]">{description}</p>
      </div>
      <Alert tone="warning">{warning}</Alert>
      {error ? <Alert tone="error">{error}</Alert> : null}
      <div className="space-y-2 max-w-md">
        <label htmlFor="tenant-reset-confirm-slug" className="text-sm font-medium text-[var(--color-foreground)]">
          {confirmLabel}
        </label>
        {expectedSlug ? (
          <p className="text-xs text-[var(--color-muted-foreground)]">
            {slugHint.replace("{{slug}}", expectedSlug)}
          </p>
        ) : null}
        <input
          id="tenant-reset-confirm-slug"
          type="text"
          autoComplete="off"
          spellCheck={false}
          value={confirmSlug}
          onChange={(e) => onConfirmSlugChange(e.target.value)}
          placeholder={confirmPlaceholder}
          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm text-[var(--color-foreground)]"
        />
      </div>
      <Button type="button" variant="danger" disabled={!slugMatches || pending} onClick={onSubmit}>
        {submitLabel}
      </Button>
    </section>
  );
}
