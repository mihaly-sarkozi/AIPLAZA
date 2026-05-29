// frontend/src/features/settings/sections/billing/billingValidation.test.ts
// Feladat: Billing validációs szabályok tesztje company/private esetekre.
// Sárközi Mihály - 2026.05.29

import { describe, expect, it } from "vitest";
import { validateBillingForm } from "./billingValidation";
import type { BillingFormState } from "./billingTypes";

const t = (key: string) => key;

const baseForm: BillingFormState = {
  customerType: "company",
  fullName: "",
  companyName: "",
  taxId: "",
  addressLine: "Fo utca 1",
  postalCode: "1111",
  city: "Budapest",
  region: "",
  country: "HU",
};

describe("validateBillingForm", () => {
  it("requires company name and tax id for company customer type", () => {
    const errors = validateBillingForm(baseForm, t);
    expect(errors.companyName).toBe("settings.billingFieldRequired");
    expect(errors.taxId).toBe("settings.billingFieldRequired");
  });

  it("requires full name for private customer type", () => {
    const errors = validateBillingForm({ ...baseForm, customerType: "private", fullName: "", companyName: "", taxId: "" }, t);
    expect(errors.fullName).toBe("settings.billingFieldRequired");
    expect(errors.companyName).toBeUndefined();
  });
});
