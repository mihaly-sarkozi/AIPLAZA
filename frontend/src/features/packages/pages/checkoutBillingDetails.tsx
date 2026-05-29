import type { BillingSettingsResponse } from "../../../api/services/settingsService";
import { isEuBillingCountry, isValidEuVatId, isValidPostalCode } from "../../billing/billingCountries";

export type BillingCustomerType = "company" | "private";

export function checkoutCustomerTypeFromSettings(settings?: BillingSettingsResponse | null): BillingCustomerType {
  return settings?.billing_customer_type ?? (settings?.billing_tax_id?.trim() ? "company" : "private");
}

export function hasSavedCheckoutBillingDetails(settings?: BillingSettingsResponse | null): boolean {
  if (!settings) return false;
  const commonFieldsFilled =
    Boolean(settings.billing_address_line?.trim()) &&
    Boolean(settings.billing_country?.trim()) &&
    isValidPostalCode(settings.billing_postal_code ?? "") &&
    Boolean(settings.billing_city?.trim());
  if (!commonFieldsFilled) return false;
  const customerType = checkoutCustomerTypeFromSettings(settings);
  if (customerType === "private") {
    return Boolean(settings.billing_full_name?.trim());
  }
  const taxId = settings.billing_tax_id?.trim() ?? "";
  return Boolean(settings.billing_company_name?.trim()) && isEuBillingCountry(settings.billing_country) && isValidEuVatId(settings.billing_country, taxId);
}
