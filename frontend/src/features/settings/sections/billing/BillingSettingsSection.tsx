// frontend/src/features/settings/sections/billing/BillingSettingsSection.tsx
// Feladat: Billing settings UI-only komponens, kizárólag kapott propsokra támaszkodva.
// Sárközi Mihály - 2026.05.29

import SettingsBlock from "../../components/SettingsBlock";
import type { Locale } from "../../../../i18n";
import {
  BILLING_COUNTRY_OTHER,
  BILLING_REGIONS_BY_COUNTRY,
  getBillingCountryOptions,
  getEuVatPlaceholder,
  isEuBillingCountry,
  isRegionRequired,
} from "../../../billing/billingCountries";
import type { BillingFieldErrors, BillingFormState } from "./billingTypes";

type BillingSettingsSectionProps = {
  title: string;
  disabled: boolean;
  locale: Locale;
  t: (key: string) => string;
  form: BillingFormState;
  errors: BillingFieldErrors;
  onFieldChange: <K extends keyof BillingFormState>(field: K, value: BillingFormState[K]) => void;
};

export default function BillingSettingsSection({ title, disabled, locale, t, form, errors, onFieldChange }: BillingSettingsSectionProps) {
  const regionOptions = BILLING_REGIONS_BY_COUNTRY[form.country] ?? [];
  const countryOptions = getBillingCountryOptions(locale);
  const regionRequired = isRegionRequired(form.country);
  const companyUnavailable = form.customerType === "company" && form.country && !isEuBillingCountry(form.country);
  return (
    <SettingsBlock title={title}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--color-muted)]">{t("settings.billingEuropeOnlyNotice")}</p>
        <fieldset className="inline-flex max-w-full flex-col gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-3">
          <legend className="px-1 text-xs font-medium text-[var(--color-muted)]">{t("settings.billingCustomerType")}</legend>
          <div className="inline-flex w-fit max-w-full overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-card)] p-1">
            <RadioOption
              label={t("settings.billingCustomerTypeCompany")}
              value="company"
              checked={form.customerType === "company"}
              disabled={disabled}
              onChange={() => onFieldChange("customerType", "company")}
            />
            <RadioOption
              label={t("settings.billingCustomerTypePrivate")}
              value="private"
              checked={form.customerType === "private"}
              disabled={disabled}
              onChange={() => onFieldChange("customerType", "private")}
            />
          </div>
        </fieldset>
        <div className="grid gap-4 md:grid-cols-2">
          {form.customerType === "company" ? (
            <TextField
              label={t("settings.billingCompanyName")}
              value={form.companyName}
              setter={(value) => onFieldChange("companyName", value)}
              disabled={disabled}
              required
              error={errors.companyName}
            />
          ) : (
            <TextField
              label={t("settings.billingFullName")}
              value={form.fullName}
              setter={(value) => onFieldChange("fullName", value)}
              disabled={disabled}
              required
              error={errors.fullName}
            />
          )}
          <label className="block text-sm text-[var(--color-label)]">
            {t("settings.billingCountry")} *
            <select
              value={form.country}
              onChange={(event) => {
                onFieldChange("country", event.target.value);
                onFieldChange("region", "");
              }}
              className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
              disabled={disabled}
              required
              aria-invalid={Boolean(errors.country)}
            >
              <option value="">{t("settings.billingCountrySelectPlaceholder")}</option>
              {countryOptions.map((option) => (
                <option key={option.code} value={option.code} disabled={option.disabled}>
                  {option.label}
                </option>
              ))}
            </select>
            {errors.country ? <span className="mt-1 block text-xs text-red-600 dark:text-red-400">{errors.country}</span> : null}
          </label>
          {form.customerType === "company" ? (
            <TextField
              label={t("settings.billingTaxId")}
              value={form.taxId}
              setter={(value) => onFieldChange("taxId", value)}
              disabled={disabled}
              required
              placeholder={getEuVatPlaceholder(form.country)}
              error={errors.taxId}
            />
          ) : null}
          <TextField
            label={t("settings.billingPostalCode")}
            value={form.postalCode}
            setter={(value) => onFieldChange("postalCode", value)}
            disabled={disabled}
            required
            error={errors.postalCode}
          />
          {regionRequired ? (
            <label className="block text-sm text-[var(--color-label)]">
              {t("settings.billingRegion")} *
              <select
                value={form.region}
                onChange={(event) => onFieldChange("region", event.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
                disabled={disabled}
                required
                aria-invalid={Boolean(errors.region)}
              >
                <option value="">{t("settings.billingRegionSelectPlaceholder")}</option>
                {regionOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              {errors.region ? <span className="mt-1 block text-xs text-red-600 dark:text-red-400">{errors.region}</span> : null}
            </label>
          ) : null}
          <TextField
            label={t("settings.billingCity")}
            value={form.city}
            setter={(value) => onFieldChange("city", value)}
            disabled={disabled}
            required
            error={errors.city}
          />
          <TextField
            label={t("settings.billingAddressLine")}
            value={form.addressLine}
            setter={(value) => onFieldChange("addressLine", value)}
            disabled={disabled}
            required
            error={errors.addressLine}
          />
        </div>
        {form.country === BILLING_COUNTRY_OTHER ? <p className="text-sm text-red-600">{t("settings.billingOtherCountryDisabled")}</p> : null}
        {companyUnavailable ? <p className="text-sm text-red-600">{t("settings.billingCompanyEuOnly")}</p> : null}
      </div>
    </SettingsBlock>
  );
}

function RadioOption({
  label,
  value,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  value: "company" | "private";
  checked: boolean;
  disabled: boolean;
  onChange: () => void;
}) {
  return (
    <label
      className={`inline-flex cursor-pointer items-center justify-center whitespace-nowrap rounded px-3 py-1.5 text-sm font-medium transition ${
        checked ? "bg-[var(--color-primary)] shadow-sm" : "hover:bg-[var(--color-card-muted)]"
      } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
      style={{ color: checked ? "var(--color-on-primary)" : "var(--color-foreground)" }}
    >
      <input type="radio" name="settings_billing_customer_type" value={value} checked={checked} onChange={onChange} disabled={disabled} className="sr-only" />
      <span>{label}</span>
    </label>
  );
}

function TextField({
  label,
  value,
  setter,
  disabled,
  required = false,
  placeholder,
  error,
}: {
  label: string;
  value: string;
  setter: (value: string) => void;
  disabled: boolean;
  required?: boolean;
  placeholder?: string;
  error?: string;
}) {
  return (
    <label className="block text-sm text-[var(--color-label)]">
      {label}
      {required ? " *" : ""}
      <input
        value={value}
        onChange={(event) => setter(event.target.value)}
        placeholder={placeholder}
        className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
        disabled={disabled}
        required={required}
        aria-invalid={Boolean(error)}
      />
      {error ? <span className="mt-1 block text-xs text-red-600 dark:text-red-400">{error}</span> : null}
    </label>
  );
}
