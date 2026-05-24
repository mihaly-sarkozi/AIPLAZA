import api from "../axiosClient";
import type { BillingCustomerType } from "../../features/billing/billingCountries";

export type SettingsTimezone =
  | "UTC"
  | "Europe/London"
  | "Europe/Paris"
  | "Europe/Berlin"
  | "Europe/Madrid"
  | "Europe/Rome"
  | "Europe/Amsterdam"
  | "Europe/Zurich"
  | "Europe/Vienna"
  | "Europe/Prague"
  | "Europe/Warsaw"
  | "Europe/Budapest"
  | "Europe/Athens"
  | "Europe/Bucharest"
  | "Europe/Istanbul"
  | "Asia/Dubai"
  | "Asia/Kolkata"
  | "Asia/Singapore"
  | "Asia/Hong_Kong"
  | "Asia/Shanghai"
  | "Asia/Seoul"
  | "America/New_York"
  | "America/Toronto"
  | "America/Chicago"
  | "America/Denver"
  | "America/Los_Angeles"
  | "America/Mexico_City"
  | "America/Sao_Paulo"
  | "Africa/Cairo"
  | "Africa/Johannesburg"
  | "Australia/Sydney"
  | "Asia/Tokyo";

export type SettingsDateFormat =
  | "YYYY-MM-DD"
  | "DD.MM.YYYY"
  | "DD/MM/YYYY"
  | "MM/DD/YYYY";

export type SettingsTimeFormat = "HH:mm" | "HH:mm:ss" | "hh:mm A";

export type SettingsResponse = {
  two_factor_enabled: boolean;
  timezone: SettingsTimezone;
  date_format: SettingsDateFormat;
  time_format: SettingsTimeFormat;
  billing_customer_type: BillingCustomerType;
  billing_full_name: string;
  billing_company_name: string;
  billing_tax_id: string;
  billing_address_line: string;
  billing_postal_code: string;
  billing_city: string;
  billing_region: string;
  billing_country: string;
};

export type PatchSettingsPayload = {
  two_factor_enabled?: boolean;
  timezone?: SettingsTimezone;
  date_format?: SettingsDateFormat;
  time_format?: SettingsTimeFormat;
  billing_customer_type?: BillingCustomerType;
  billing_full_name?: string;
  billing_company_name?: string;
  billing_tax_id?: string;
  billing_address_line?: string;
  billing_postal_code?: string;
  billing_city?: string;
  billing_region?: string;
  billing_country?: string;
};

export async function getSettings(): Promise<SettingsResponse> {
  const res = await api.get("/settings");
  return res.data as SettingsResponse;
}

export async function patchSettings(body: PatchSettingsPayload): Promise<SettingsResponse> {
  const res = await api.patch("/settings", body);
  return res.data as SettingsResponse;
}
