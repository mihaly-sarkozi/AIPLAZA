// frontend/src/features/settings/hooks/useSettings.ts
// Feladat: Legacy settings React Query hookok a központi query key és API service réteggel.
// Sárközi Mihály - 2026.05.29

import { useQuery, useMutation, useQueryClient, type UseQueryOptions, type UseMutationOptions } from "@tanstack/react-query";
import { useAuthStore } from "../../auth/state/authStore";
import { queryKeys } from "../../../queryKeys";
import {
  getBillingSettings,
  getLocaleSettings,
  getSettings,
  getTwoFactorSettings,
  patchBillingSettings,
  patchLocaleSettings,
  patchSettings,
  patchTwoFactorSettings,
  type BillingSettingsResponse,
  type LocaleSettingsResponse,
  type PatchBillingSettingsPayload,
  type PatchLocaleSettingsPayload,
  type PatchSettingsPayload,
  type PatchTwoFactorSettingsPayload,
  type SettingsResponse,
  type TwoFactorSettingsResponse,
} from "../../../api/services/settingsService";

export function useSettings(options?: Omit<UseQueryOptions<SettingsResponse>, "queryKey" | "queryFn">) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: queryKeys.settings,
    queryFn: getSettings,
    enabled: user?.role === "owner" || user?.role === "admin",
    ...options,
  });
}

export function usePatchSettingsMutation(
  options?: UseMutationOptions<SettingsResponse, Error, PatchSettingsPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.settings, (prev: unknown) =>
        prev ? { ...(prev as object), ...data } : data
      );
    },
    ...options,
  });
}

export function useBillingSettings(
  options?: Omit<UseQueryOptions<BillingSettingsResponse>, "queryKey" | "queryFn">
) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: queryKeys.settingsBilling,
    queryFn: getBillingSettings,
    enabled: user?.role === "owner" || user?.role === "admin",
    ...options,
  });
}

export function usePatchBillingSettingsMutation(
  options?: UseMutationOptions<BillingSettingsResponse, Error, PatchBillingSettingsPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchBillingSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.settingsBilling, (prev: unknown) =>
        prev ? { ...(prev as object), ...data } : data
      );
      queryClient.setQueryData(queryKeys.settings, (prev: unknown) =>
        prev ? { ...(prev as object), ...data } : prev
      );
    },
    ...options,
  });
}

export function useLocaleSettings(
  options?: Omit<UseQueryOptions<LocaleSettingsResponse>, "queryKey" | "queryFn">
) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: queryKeys.settingsLocale,
    queryFn: getLocaleSettings,
    enabled: Boolean(user),
    ...options,
  });
}

export function usePatchLocaleSettingsMutation(
  options?: UseMutationOptions<LocaleSettingsResponse, Error, PatchLocaleSettingsPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchLocaleSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.settingsLocale, (prev: unknown) =>
        prev ? { ...(prev as object), ...data } : data
      );
      queryClient.setQueryData(queryKeys.settings, (prev: unknown) =>
        prev ? { ...(prev as object), ...data } : prev
      );
    },
    ...options,
  });
}

export function useTwoFactorSettings(
  options?: Omit<UseQueryOptions<TwoFactorSettingsResponse>, "queryKey" | "queryFn">
) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: queryKeys.settingsTwoFactor,
    queryFn: getTwoFactorSettings,
    enabled: user?.role === "owner" || user?.role === "admin",
    ...options,
  });
}

export function usePatchTwoFactorSettingsMutation(
  options?: UseMutationOptions<TwoFactorSettingsResponse, Error, PatchTwoFactorSettingsPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchTwoFactorSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.settingsTwoFactor, (prev: unknown) =>
        prev ? { ...(prev as object), ...data } : data
      );
      queryClient.setQueryData(queryKeys.settings, (prev: unknown) =>
        prev ? { ...(prev as object), ...data } : prev
      );
    },
    ...options,
  });
}
