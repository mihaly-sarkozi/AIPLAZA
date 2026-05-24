export function formatNumber(value: number | undefined): string {
  return new Intl.NumberFormat("hu-HU").format(Number(value ?? 0));
}

export function domainLabel(domain: string): string {
  if (domain === "application") return "Alkalmazás";
  if (domain === "auth_security") return "Auth / security";
  if (domain === "infrastructure") return "Infrastructure";
  if (domain === "business") return "Üzleti egészség";
  return domain;
}

export function readinessLabel(status: "green" | "yellow" | "red"): string {
  if (status === "green") return "MVP ready";
  if (status === "yellow") return "Részben kész";
  return "Blokkolt";
}

export function readinessBadgeClass(status: "green" | "yellow" | "red"): string {
  if (status === "green") return "border-green-200 bg-green-50 text-green-700";
  if (status === "yellow") return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-red-200 bg-red-50 text-red-700";
}
