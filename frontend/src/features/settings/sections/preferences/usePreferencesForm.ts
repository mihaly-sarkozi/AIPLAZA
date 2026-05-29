// frontend/src/features/settings/sections/preferences/usePreferencesForm.ts
// Feladat: Preferences form state, betöltés/mentés/reset és query cache frissítés kezelése.
// Sárközi Mihály - 2026.05.29

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../../../auth/state/authStore";
import { queryKeys } from "../../../../queryKeys";
import { getLocaleSettings, patchLocaleSettings } from "../../api/settingsService";
import { mapLocaleResponseToPreferencesForm, mapPreferencesFormToLocalePayload } from "./preferencesMapper";
import type { PreferencesFormState } from "./preferencesTypes";

const DEFAULT_FORM: PreferencesFormState = {
  timezone: "UTC",
  dateFormat: "YYYY-MM-DD",
  timeFormat: "HH:mm",
};

export function usePreferencesForm() {
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();
  const localeQuery = useQuery({
    queryKey: queryKeys.settingsLocale,
    queryFn: getLocaleSettings,
    enabled: Boolean(user),
  });
  const [form, setForm] = useState<PreferencesFormState>(DEFAULT_FORM);
  useEffect(() => {
    if (!localeQuery.data) return;
    setForm(mapLocaleResponseToPreferencesForm(localeQuery.data));
  }, [localeQuery.data]);

  const saveMutation = useMutation({
    mutationFn: patchLocaleSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.settingsLocale, (prev: unknown) => (prev ? { ...(prev as object), ...data } : data));
      queryClient.setQueryData(queryKeys.settings, (prev: unknown) => (prev ? { ...(prev as object), ...data } : prev));
    },
  });

  const isDirty = useMemo(() => {
    if (!localeQuery.data) return false;
    const base = mapLocaleResponseToPreferencesForm(localeQuery.data);
    return base.timezone !== form.timezone || base.dateFormat !== form.dateFormat || base.timeFormat !== form.timeFormat;
  }, [form, localeQuery.data]);

  return {
    form,
    setForm,
    isDirty,
    loading: localeQuery.isLoading,
    saving: saveMutation.isPending,
    error: localeQuery.error ?? saveMutation.error,
    save: () => saveMutation.mutateAsync(mapPreferencesFormToLocalePayload(form)),
    reset: () => {
      if (!localeQuery.data) return;
      setForm(mapLocaleResponseToPreferencesForm(localeQuery.data));
    },
  };
}
