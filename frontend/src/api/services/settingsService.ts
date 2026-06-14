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

export type TwoFactorSettingsResponse = Pick<SettingsResponse, "two_factor_enabled">;
export type LocaleSettingsResponse = Pick<SettingsResponse, "timezone" | "date_format" | "time_format">;
export type BillingSettingsResponse = Pick<
  SettingsResponse,
  | "billing_customer_type"
  | "billing_full_name"
  | "billing_company_name"
  | "billing_tax_id"
  | "billing_address_line"
  | "billing_postal_code"
  | "billing_city"
  | "billing_region"
  | "billing_country"
>;

export type PatchTwoFactorSettingsPayload = Partial<TwoFactorSettingsResponse>;
export type PatchLocaleSettingsPayload = Partial<LocaleSettingsResponse>;
export type PatchBillingSettingsPayload = Partial<BillingSettingsResponse>;

export type PatchSettingsPayload = PatchTwoFactorSettingsPayload & PatchLocaleSettingsPayload & PatchBillingSettingsPayload;

export async function getSettings(): Promise<SettingsResponse> {
  const res = await api.get("/settings");
  return res.data as SettingsResponse;
}

export async function patchSettings(body: PatchSettingsPayload): Promise<SettingsResponse> {
  const res = await api.patch("/settings", body);
  return res.data as SettingsResponse;
}

export async function getTwoFactorSettings(): Promise<TwoFactorSettingsResponse> {
  const res = await api.get("/settings/security/2fa");
  return res.data as TwoFactorSettingsResponse;
}

export async function patchTwoFactorSettings(
  body: PatchTwoFactorSettingsPayload
): Promise<TwoFactorSettingsResponse> {
  const res = await api.patch("/settings/security/2fa", body);
  return res.data as TwoFactorSettingsResponse;
}

export async function getLocaleSettings(): Promise<LocaleSettingsResponse> {
  const res = await api.get("/settings/locale");
  return res.data as LocaleSettingsResponse;
}

export async function patchLocaleSettings(body: PatchLocaleSettingsPayload): Promise<LocaleSettingsResponse> {
  const res = await api.patch("/settings/locale", body);
  return res.data as LocaleSettingsResponse;
}

export async function getBillingSettings(): Promise<BillingSettingsResponse> {
  const res = await api.get("/settings/billing");
  return res.data as BillingSettingsResponse;
}

export async function patchBillingSettings(body: PatchBillingSettingsPayload): Promise<BillingSettingsResponse> {
  const res = await api.patch("/settings/billing", body);
  return res.data as BillingSettingsResponse;
}

export type TenantResetPayload = {
  confirm_slug: string;
};

export type TenantResetResponse = {
  status: string;
  message: string;
  tenant_slug: string;
  owner_user_id: number;
  default_knowledge_base_uuid?: string | null;
};

export async function postTenantReset(body: TenantResetPayload): Promise<TenantResetResponse> {
  const res = await api.post("/settings/reset", body);
  return res.data as TenantResetResponse;
}

export type LegacyPatchSettingsPayload = {
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
