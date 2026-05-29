// frontend/src/features/settings/sections/billing/billingValidation.ts
// Feladat: Billing form kliensoldali validációs szabályai (company/private, VAT, ország/régió).
// Sárközi Mihály - 2026.05.29

import { isRegionRequired, isValidEuVatId } from "../../../billing/billingCountries";
import type { BillingFieldErrors, BillingFormState } from "./billingTypes";

export function validateBillingForm(form: BillingFormState, t: (key: string) => string): BillingFieldErrors {
  const validateRequired = (value: string) => (value.trim() ? "" : t("settings.billingFieldRequired"));
  const errors: BillingFieldErrors = {};

  if (form.customerType === "company") {
    const companyNameError = validateRequired(form.companyName);
    if (companyNameError) errors.companyName = companyNameError;
    const taxIdError = validateRequired(form.taxId);
    if (taxIdError) {
      errors.taxId = taxIdError;
    } else if (!isValidEuVatId(form.country, form.taxId)) {
      errors.taxId = t("settings.billingInvalidTaxId");
    }
  } else {
    const fullNameError = validateRequired(form.fullName);
    if (fullNameError) errors.fullName = fullNameError;
  }

  const countryError = validateRequired(form.country);
  if (countryError) errors.country = countryError;
  const postalCodeError = validateRequired(form.postalCode);
  if (postalCodeError) errors.postalCode = postalCodeError;
  if (isRegionRequired(form.country)) {
    const regionError = validateRequired(form.region);
    if (regionError) errors.region = regionError;
  }
  const cityError = validateRequired(form.city);
  if (cityError) errors.city = cityError;
  const addressLineError = validateRequired(form.addressLine);
  if (addressLineError) errors.addressLine = addressLineError;

  return errors;
}
