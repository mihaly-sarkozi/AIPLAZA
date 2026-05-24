import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import BillingSettingsSection from "./BillingSettingsSection";
import type { BillingCustomerType } from "../../billing/billingCountries";

const labels: Record<string, string> = {
  "settings.billingEuropeOnlyNotice": "Europe only",
  "settings.billingCustomerType": "Customer type",
  "settings.billingCustomerTypeCompany": "Company",
  "settings.billingCustomerTypePrivate": "Private individual",
  "settings.billingCompanyName": "Company name",
  "settings.billingTaxId": "VAT ID",
  "settings.billingFullName": "Full name",
  "settings.billingCountry": "Country",
  "settings.billingCountrySelectPlaceholder": "Select country",
  "settings.billingPostalCode": "Postal code",
  "settings.billingRegion": "Region",
  "settings.billingRegionSelectPlaceholder": "Select region",
  "settings.billingCity": "City",
  "settings.billingAddressLine": "Address",
  "settings.billingOtherCountryDisabled": "Europe only message",
  "settings.billingCompanyEuOnly": "EU company only",
};

function renderSection(overrides: Partial<Parameters<typeof BillingSettingsSection>[0]> = {}) {
  const props = {
    title: "Billing",
    disabled: false,
    customerType: "company" as BillingCustomerType,
    fullName: "",
    companyName: "",
    taxId: "",
    country: "",
    postalCode: "",
    region: "",
    city: "",
    addressLine: "",
    setCustomerType: vi.fn(),
    setFullName: vi.fn(),
    setCompanyName: vi.fn(),
    setTaxId: vi.fn(),
    setCountry: vi.fn(),
    setPostalCode: vi.fn(),
    setRegion: vi.fn(),
    setCity: vi.fn(),
    setAddressLine: vi.fn(),
    locale: "en" as const,
    t: (key: string) => labels[key] ?? key,
    ...overrides,
  };
  render(<BillingSettingsSection {...props} />);
  return props;
}

describe("BillingSettingsSection", () => {
  it("shows company fields by default", () => {
    renderSection();

    expect(screen.getByText("Billing")).toBeInTheDocument();
    expect(screen.getByLabelText(/Company name/)).toBeInTheDocument();
    expect(screen.getByLabelText(/VAT ID/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Full name/)).not.toBeInTheDocument();
  });

  it("shows private full name field when private customer is selected", () => {
    renderSection({ customerType: "private" });

    expect(screen.getByLabelText(/Full name/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Company name/)).not.toBeInTheDocument();
  });

  it("notifies parent when customer type changes", async () => {
    const user = userEvent.setup();
    const props = renderSection();

    await user.click(screen.getByLabelText("Private individual"));

    expect(props.setCustomerType).toHaveBeenCalledWith("private");
  });

  it("shows region select for countries where it is required", () => {
    renderSection({ country: "CH" });

    expect(screen.getByLabelText(/Region/)).toBeInTheDocument();
  });

  it("shows company EU-only warning for non-EU company country", () => {
    renderSection({ customerType: "company", country: "CH" });

    expect(screen.getByText("EU company only")).toBeInTheDocument();
  });
});
