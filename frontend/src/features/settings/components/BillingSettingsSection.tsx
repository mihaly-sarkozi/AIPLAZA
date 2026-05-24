import SettingsBlock from "./SettingsBlock";
import {
  BILLING_COUNTRY_OTHER,
  BILLING_REGIONS_BY_COUNTRY,
  type BillingCustomerType,
  getEuVatPlaceholder,
  getBillingCountryOptions,
  isEuBillingCountry,
  isRegionRequired,
} from "../../billing/billingCountries";
import type { Locale } from "../../../i18n";

type BillingSettingsSectionProps = {
  title: string;
  disabled: boolean;
  customerType: BillingCustomerType;
  fullName: string;
  companyName: string;
  taxId: string;
  country: string;
  postalCode: string;
  region: string;
  city: string;
  addressLine: string;
  errors?: Partial<Record<"fullName" | "companyName" | "taxId" | "country" | "postalCode" | "region" | "city" | "addressLine", string>>;
  setCustomerType: (value: BillingCustomerType) => void;
  setFullName: (value: string) => void;
  setCompanyName: (value: string) => void;
  setTaxId: (value: string) => void;
  setCountry: (value: string) => void;
  setPostalCode: (value: string) => void;
  setRegion: (value: string) => void;
  setCity: (value: string) => void;
  setAddressLine: (value: string) => void;
  locale: Locale;
  t: (key: string) => string;
};

export default function BillingSettingsSection({
  title,
  disabled,
  customerType,
  fullName,
  companyName,
  taxId,
  country,
  postalCode,
  region,
  city,
  addressLine,
  errors = {},
  setCustomerType,
  setFullName,
  setCompanyName,
  setTaxId,
  setCountry,
  setPostalCode,
  setRegion,
  setCity,
  setAddressLine,
  locale,
  t,
}: BillingSettingsSectionProps) {
  const regionOptions = BILLING_REGIONS_BY_COUNTRY[country] ?? [];
  const countryOptions = getBillingCountryOptions(locale);
  const regionRequired = isRegionRequired(country);
  const companyUnavailable = customerType === "company" && country && !isEuBillingCountry(country);

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
              checked={customerType === "company"}
              disabled={disabled}
              onChange={() => setCustomerType("company")}
            />
            <RadioOption
              label={t("settings.billingCustomerTypePrivate")}
              value="private"
              checked={customerType === "private"}
              disabled={disabled}
              onChange={() => setCustomerType("private")}
            />
          </div>
        </fieldset>

        <div className="grid gap-4 md:grid-cols-2">
          {customerType === "company" ? (
            <TextField label={t("settings.billingCompanyName")} value={companyName} setter={setCompanyName} disabled={disabled} required error={errors.companyName} />
          ) : (
            <TextField label={t("settings.billingFullName")} value={fullName} setter={setFullName} disabled={disabled} required error={errors.fullName} />
          )}
          <label className="block text-sm text-[var(--color-label)]">
            {t("settings.billingCountry")} *
            <select
              value={country}
              onChange={(event) => {
                setCountry(event.target.value);
                setRegion("");
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
          {customerType === "company" ? (
            <TextField label={t("settings.billingTaxId")} value={taxId} setter={setTaxId} disabled={disabled} required placeholder={getEuVatPlaceholder(country)} error={errors.taxId} />
          ) : null}
          <TextField label={t("settings.billingPostalCode")} value={postalCode} setter={setPostalCode} disabled={disabled} required error={errors.postalCode} />
          {regionRequired ? (
            <label className="block text-sm text-[var(--color-label)]">
              {t("settings.billingRegion")} *
              <select
                value={region}
                onChange={(event) => setRegion(event.target.value)}
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
          <TextField label={t("settings.billingCity")} value={city} setter={setCity} disabled={disabled} required error={errors.city} />
          <TextField label={t("settings.billingAddressLine")} value={addressLine} setter={setAddressLine} disabled={disabled} required error={errors.addressLine} />
        </div>
        {country === BILLING_COUNTRY_OTHER ? <p className="text-sm text-red-600">{t("settings.billingOtherCountryDisabled")}</p> : null}
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
  value: BillingCustomerType;
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
