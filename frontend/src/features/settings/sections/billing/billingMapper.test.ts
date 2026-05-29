// frontend/src/features/settings/sections/billing/billingMapper.test.ts
// Feladat: Billing response->form és form->payload mapper tesztek.
// Sárközi Mihály - 2026.05.29

import { describe, expect, it } from "vitest";
import { mapBillingFormToPayload, mapBillingResponseToForm } from "./billingMapper";

describe("billingMapper", () => {
  it("maps API response into billing form state", () => {
    const form = mapBillingResponseToForm({
      billing_customer_type: "company",
      billing_full_name: "Teszt Elek",
      billing_company_name: "Acme Kft",
      billing_tax_id: "HU12345678",
      billing_address_line: "Fo utca 1",
      billing_postal_code: "1111",
      billing_city: "Budapest",
      billing_region: "",
      billing_country: "HU",
    });
    expect(form.companyName).toBe("Acme Kft");
    expect(form.customerType).toBe("company");
  });

  it("maps form into normalized API payload", () => {
    const payload = mapBillingFormToPayload({
      customerType: "company",
      fullName: "Teszt Elek",
      companyName: " Acme Kft ",
      taxId: "hu 12345678",
      addressLine: "Fo utca 1",
      postalCode: "11 11",
      city: "Budapest",
      region: "",
      country: "HU",
    });
    expect(payload.billing_company_name).toBe("Acme Kft");
    expect(payload.billing_tax_id).toBe("HU12345678");
    expect(payload.billing_postal_code).toBe("11 11");
  });
});
