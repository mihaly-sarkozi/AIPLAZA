import { describe, expect, it } from "vitest";
import {
  BILLING_COUNTRIES,
  BILLING_COUNTRY_OTHER,
  BILLING_REGIONS_BY_COUNTRY,
  getEuVatPlaceholder,
  getBillingCountryOptions,
  isEuBillingCountry,
  isRegionRequired,
  isValidEuVatId,
  isValidEuropeanBillingCountry,
  normalizeEuVatId,
  normalizePostalCode,
} from "./billingCountries";

describe("billingCountries", () => {
  it("contains European countries and a disabled other option", () => {
    expect(BILLING_COUNTRIES.some((country) => country.code === "HU" && country.eu)).toBe(true);
    expect(BILLING_COUNTRIES.some((country) => country.code === "CH" && !country.eu)).toBe(true);
    expect(BILLING_COUNTRIES.find((country) => country.code === BILLING_COUNTRY_OTHER)?.disabled).toBe(true);
  });

  it("localizes country names by active locale", () => {
    const huHungary = getBillingCountryOptions("hu").find((country) => country.code === "HU");
    const enHungary = getBillingCountryOptions("en").find((country) => country.code === "HU");
    const esHungary = getBillingCountryOptions("es").find((country) => country.code === "HU");

    expect(huHungary?.label).toBe("Magyarország");
    expect(enHungary?.label).toBe("Hungary");
    expect(esHungary?.label).toBe("Hungría");
    expect(getBillingCountryOptions("en").find((country) => country.code === BILLING_COUNTRY_OTHER)?.label).toBe("Other");
  });

  it("classifies EU and supported European countries", () => {
    expect(isEuBillingCountry("HU")).toBe(true);
    expect(isEuBillingCountry("CH")).toBe(false);
    expect(isValidEuropeanBillingCountry("CH")).toBe(true);
    expect(isValidEuropeanBillingCountry(BILLING_COUNTRY_OTHER)).toBe(false);
  });

  it("normalizes postal codes and EU VAT IDs", () => {
    expect(normalizePostalCode("h-1111!")).toBe("H-1111");
    expect(normalizeEuVatId("hu 12.34-5678")).toBe("HU12345678");
  });

  it("validates EU VAT IDs by country code", () => {
    expect(isValidEuVatId("HU", "HU12345678")).toBe(true);
    expect(isValidEuVatId("ES", "ESB09835208")).toBe(true);
    expect(isValidEuVatId("HU", "HU123")).toBe(false);
    expect(isValidEuVatId("CH", "CHE123")).toBe(false);
  });

  it("returns country-specific EU VAT placeholder examples", () => {
    expect(getEuVatPlaceholder("HU")).toBe("HU12345678");
    expect(getEuVatPlaceholder("DE")).toBe("DE123456789");
    expect(getEuVatPlaceholder("ES")).toBe("ESB12345678");
    expect(getEuVatPlaceholder("CH")).toBe("EU VAT ID");
  });

  it("exposes region options only for selected countries", () => {
    expect(isRegionRequired("CH")).toBe(true);
    expect(BILLING_REGIONS_BY_COUNTRY.CH.length).toBeGreaterThan(0);
    expect(isRegionRequired("HU")).toBe(false);
  });
});
