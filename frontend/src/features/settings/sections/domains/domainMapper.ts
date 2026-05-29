// frontend/src/features/settings/sections/domains/domainMapper.ts
// Feladat: Domain API response mezők UI-hoz szükséges alakra mappolása.
// Sárközi Mihály - 2026.05.29

import type { DomainOverviewResponse } from "../../api/domainService";

export function mapDomainOverview(overview: DomainOverviewResponse | undefined) {
  return {
    customDomains: overview?.custom_domains ?? [],
    primaryDomain: overview?.primary_domain?.domain ?? "-",
    activeHost: overview?.active_host,
    showActiveCustomHost: Boolean(overview?.active_custom_domain && overview?.active_host && overview?.active_host !== overview?.primary_domain?.domain),
  };
}
