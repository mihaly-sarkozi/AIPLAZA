// frontend/src/features/settings/sections/billing/billingMapper.ts
// Feladat: Billing settings API payload és frontend form state közötti mappolás.
// Sárközi Mihály - 2026.05.29

import { normalizeEuVatId, normalizePostalCode } from "../../../billing/billingCountries";
import type { BillingSettingsResponse, PatchBillingSettingsPayload } from "../../api/settingsService";
import type { BillingFormState } from "./billingTypes";

export function mapBillingResponseToForm(response: BillingSettingsResponse): BillingFormState {
  return {
    customerType: response.billing_customer_type ?? "company",
    fullName: response.billing_full_name ?? "",
    companyName: response.billing_company_name ?? "",
    taxId: response.billing_tax_id ?? "",
    addressLine: response.billing_address_line ?? "",
    postalCode: response.billing_postal_code ?? "",
    city: response.billing_city ?? "",
    region: response.billing_region ?? "",
    country: response.billing_country ?? "",
  };
}

export function mapBillingFormToPayload(form: BillingFormState): PatchBillingSettingsPayload {
  return {
    billing_customer_type: form.customerType,
    billing_full_name: form.fullName.trim(),
    billing_company_name: form.customerType === "company" ? form.companyName.trim() : "",
    billing_tax_id: form.customerType === "company" ? normalizeEuVatId(form.taxId) : "",
    billing_address_line: form.addressLine,
    billing_postal_code: normalizePostalCode(form.postalCode),
    billing_city: form.city,
    billing_region: form.region,
    billing_country: form.country,
  };
}
