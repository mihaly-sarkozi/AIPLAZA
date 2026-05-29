// frontend/src/features/settings/api/domainService.ts
// Feladat: Domain API hívások feature-szintű thin wrappere UI logika nélkül.
// Sárközi Mihály - 2026.05.29

export {
  addCustomDomain,
  deleteCustomDomain,
  getDomainOverview,
  verifyCustomDomain,
  type DomainOverviewResponse,
  type DomainRecordResponse,
} from "../../../api/services/domainService";
