import SettingsBlock from "./SettingsBlock";

type BillingField = {
  label: string;
  value: string;
  setter: (value: string) => void;
};

type BillingSettingsSectionProps = {
  title: string;
  fields: BillingField[];
  disabled: boolean;
};

export default function BillingSettingsSection({ title, fields, disabled }: BillingSettingsSectionProps) {
  return (
    <SettingsBlock title={title}>
      <div className="grid gap-4 md:grid-cols-2">
        {fields.map((field) => (
          <label key={field.label} className="block text-sm text-[var(--color-label)]">
            {field.label}
            <input
              value={field.value}
              onChange={(event) => field.setter(event.target.value)}
              className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
              disabled={disabled}
            />
          </label>
        ))}
      </div>
    </SettingsBlock>
  );
}
