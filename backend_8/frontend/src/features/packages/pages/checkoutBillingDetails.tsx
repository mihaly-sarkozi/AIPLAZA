import type { SettingsResponse } from "../../../api/services/settingsService";
import { isValidEuVatId, isValidPostalCode } from "./checkoutOptions";

export type BillingCustomerType = "company" | "private";

export function checkoutCustomerTypeFromSettings(settings?: SettingsResponse | null): BillingCustomerType {
  return settings?.billing_tax_id?.trim() ? "company" : "private";
}

export function hasSavedCheckoutBillingDetails(settings?: SettingsResponse | null): boolean {
  if (!settings) return false;
  const commonFieldsFilled =
    Boolean(settings.billing_company_name?.trim()) &&
    Boolean(settings.billing_address_line?.trim()) &&
    Boolean(settings.billing_country?.trim()) &&
    isValidPostalCode(settings.billing_postal_code ?? "") &&
    Boolean(settings.billing_city?.trim());
  if (!commonFieldsFilled) return false;
  const taxId = settings.billing_tax_id?.trim() ?? "";
  return !taxId || isValidEuVatId(settings.billing_country, taxId);
}
