// frontend/src/features/settings/sections/billing/useBillingForm.ts
// Feladat: Billing form state és mentési flow kezelése query/mutation integrációval.
// Sárközi Mihály - 2026.05.29

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../../../auth/state/authStore";
import { queryKeys } from "../../../../queryKeys";
import { getBillingSettings, patchBillingSettings } from "../../api/settingsService";
import { mapBillingFormToPayload, mapBillingResponseToForm } from "./billingMapper";
import { validateBillingForm } from "./billingValidation";
import type { BillingFieldErrors, BillingFieldKey, BillingFormState } from "./billingTypes";

const EMPTY_FORM: BillingFormState = {
  customerType: "company",
  fullName: "",
  companyName: "",
  taxId: "",
  addressLine: "",
  postalCode: "",
  city: "",
  region: "",
  country: "",
};

export function useBillingForm(t: (key: string) => string) {
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();
  const billingQuery = useQuery({
    queryKey: queryKeys.settingsBilling,
    queryFn: getBillingSettings,
    enabled: user?.role === "owner" || user?.role === "admin",
  });
  const [form, setForm] = useState<BillingFormState>(EMPTY_FORM);
  const [errors, setErrors] = useState<BillingFieldErrors>({});
  useEffect(() => {
    if (!billingQuery.data) return;
    setForm(mapBillingResponseToForm(billingQuery.data));
  }, [billingQuery.data]);

  const saveMutation = useMutation({
    mutationFn: patchBillingSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.settingsBilling, (prev: unknown) => (prev ? { ...(prev as object), ...data } : data));
      queryClient.setQueryData(queryKeys.settings, (prev: unknown) => (prev ? { ...(prev as object), ...data } : prev));
    },
  });

  const isDirty = useMemo(() => {
    if (!billingQuery.data) return false;
    const base = mapBillingResponseToForm(billingQuery.data);
    return JSON.stringify(base) !== JSON.stringify(form);
  }, [billingQuery.data, form]);

  return {
    form,
    errors,
    loading: billingQuery.isLoading,
    saving: saveMutation.isPending,
    error: billingQuery.error ?? saveMutation.error,
    isDirty,
    updateField: <K extends BillingFieldKey>(field: K, value: BillingFormState[K]) =>
      setForm((prev) => ({
        ...prev,
        [field]: value,
      })),
    reset: () => {
      if (!billingQuery.data) return;
      setErrors({});
      setForm(mapBillingResponseToForm(billingQuery.data));
    },
    save: async () => {
      const validation = validateBillingForm(form, t);
      setErrors(validation);
      if (Object.keys(validation).length > 0) return { ok: false as const, reason: "validation" as const };
      await saveMutation.mutateAsync(mapBillingFormToPayload(form));
      return { ok: true as const };
    },
  };
}
