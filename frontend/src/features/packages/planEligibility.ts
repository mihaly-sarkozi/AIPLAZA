import type { BillingCatalogEntry } from "../billing/hooks/useBilling";

export type PlanResourceBlockResult = {
  blocked: boolean;
  storageBlocked: boolean;
  kbBlocked: boolean;
  capGb: number | null;
  capKb: number | null;
};

export function getPlanIncludedCaps(plan: BillingCatalogEntry): { storageGb: number | null; knowledgeBases: number | null } {
  const inc = plan.included ?? {};
  const sg = inc.storage_gb;
  const kb = inc.knowledge_bases;
  return {
    storageGb: sg != null && sg !== "" ? Number(sg) : null,
    knowledgeBases: kb != null && kb !== "" ? Number(kb) : null,
  };
}

/** Nem választható, ha a célcsomag kerete kisebb, mint a jelenlegi felhasználás (és nem ez az aktuális csomag). */
export function planResourceBlock(
  plan: BillingCatalogEntry,
  usedGb: number,
  usedKbCount: number,
  isCurrentPlan: boolean
): PlanResourceBlockResult {
  const { storageGb: capGb, knowledgeBases: capKb } = getPlanIncludedCaps(plan);
  const storageBlocked = capGb != null && Number.isFinite(capGb) && usedGb > capGb;
  const kbBlocked = capKb != null && Number.isFinite(capKb) && usedKbCount > capKb;
  const blocked = !isCurrentPlan && (storageBlocked || kbBlocked);
  return { blocked, storageBlocked, kbBlocked, capGb, capKb };
}

export function formatPlanResourceBlockMessage(
  block: PlanResourceBlockResult,
  usedGb: number,
  usedKb: number,
  t: (key: string) => string
): string {
  const parts: string[] = [];
  if (block.storageBlocked && block.capGb != null) {
    parts.push(t("packages.planBlockedStorageDetail").replace("{{gb}}", String(block.capGb)).replace("{{used}}", String(usedGb)));
  }
  if (block.kbBlocked && block.capKb != null) {
    parts.push(t("packages.planBlockedKbDetail").replace("{{max}}", String(block.capKb)).replace("{{current}}", String(usedKb)));
  }
  return parts.join("\n\n");
}

export function readBillingResourceUsage(usage: Record<string, unknown> | undefined): { usedGb: number; usedKbCount: number } {
  if (!usage) return { usedGb: 0, usedKbCount: 0 };
  const resources = (usage.resources as Record<string, unknown> | undefined) ?? {};
  const training = (usage.training as Record<string, unknown> | undefined) ?? {};
  return {
    usedKbCount: Number(resources.knowledge_bases ?? 0),
    usedGb: Number(resources.storage_gb_used_rounded ?? training.storage_gb_used_rounded ?? 0),
  };
}
