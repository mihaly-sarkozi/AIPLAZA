/** Bővítések, amelyek a csomagok oldalról fizetési flow-val vásárolhatók. */
export const ADDON_CHECKOUT_CODES = [
  "training_extra_500k",
  "extra_storage_gb",
  "question_pack_100",
  "question_pack_500",
] as const;

export type AddonCheckoutCode = (typeof ADDON_CHECKOUT_CODES)[number];

export function isAddonCheckoutCode(code: string): code is AddonCheckoutCode {
  return (ADDON_CHECKOUT_CODES as readonly string[]).includes(code);
}
