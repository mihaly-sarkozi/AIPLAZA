import api from "../axiosClient";

export type DomainRecordResponse = {
  domain: string;
  state: "platform_primary" | "custom_pending" | "custom_verified" | string;
  verified_at: string | null;
  is_primary: boolean;
  cname_target: string | null;
  dns_record_type: string | null;
  dns_record_name: string | null;
  dns_record_value: string | null;
};

export type DomainOverviewResponse = {
  tenant_slug: string;
  primary_domain: DomainRecordResponse;
  active_host: string | null;
  active_custom_domain: boolean;
  custom_domains: DomainRecordResponse[];
};

export async function getDomainOverview(): Promise<DomainOverviewResponse> {
  const res = await api.get("/platform/domain");
  return res.data as DomainOverviewResponse;
}

export async function addCustomDomain(domain: string): Promise<DomainRecordResponse> {
  const res = await api.post("/platform/domain/custom", { domain });
  return res.data as DomainRecordResponse;
}

export async function verifyCustomDomain(domain: string): Promise<DomainRecordResponse> {
  const res = await api.post("/platform/domain/custom/verify", { domain });
  return res.data as DomainRecordResponse;
}

export async function deleteCustomDomain(domain: string): Promise<void> {
  await api.post("/platform/domain/custom/delete", { domain });
}
