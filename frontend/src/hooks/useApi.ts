import {
  useQuery,
  useMutation,
  useQueryClient,
  useSuspenseQuery,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import api from "../api/axiosClient";
import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  resendInvite,
  patchMe,
  changePassword,
  setInitialPassword,
  demoUnsubscribe,
  type UserListItem,
  type UpdateUserPayload,
} from "../api/services/userService";
import {
  getProfile,
  patchProfile,
  getProfilePreferences,
  patchProfilePreferences,
  type PatchProfilePayload,
  type ProfileResponse,
  type ProfilePreferences,
} from "../api/services/profileService";
import { queryKeys } from "../queryKeys";
import { useAuthStore } from "../store/authStore";
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
} from "../api/services/settingsService";

// ----- Auth / settings (unauthenticated or public) -----

const defaultSettingsQueryOptions = {
  queryKey: ["auth", "default-settings"] as const,
  queryFn: async () => {
    const res = await api.get("/auth/default-settings");
    return res.data as { locale?: string; theme?: string };
  },
};

export function useDefaultSettings(
  options?: Omit<UseQueryOptions<{ locale?: string; theme?: string }>, "queryKey" | "queryFn">
) {
  return useQuery({
    ...defaultSettingsQueryOptions,
    ...options,
  });
}

/** Suspense-based: suspend until default settings are loaded. Wrap in <Suspense>. */
export function useDefaultSettingsSuspense() {
  return useSuspenseQuery(defaultSettingsQueryOptions);
}

export function useLoginMutation(
  options?: UseMutationOptions<
    { access_token?: string; pending_token?: string; challenge_type?: "email" | "authenticator" },
    Error,
    Record<string, unknown>
  >
) {
  return useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const res = await api.post("/auth/login", payload);
      return res.data as { access_token?: string; pending_token?: string; challenge_type?: "email" | "authenticator" };
    },
    ...options,
  });
}

export function useForgotPasswordMutation(
  options?: UseMutationOptions<{ ok?: boolean }, Error, { email: string }>
) {
  return useMutation({
    mutationFn: async ({ email }: { email: string }) => {
      const res = await api.post("/auth/forgot-password", { email });
      return res.data as { ok?: boolean };
    },
    ...options,
  });
}

export function useSetPasswordMutation(
  options?: UseMutationOptions<unknown, Error, { token: string; password: string }>
) {
  return useMutation({
    mutationFn: async ({ token, password }: { token: string; password: string }) => {
      const res = await api.post("/users/set-password", { token, password });
      return res.data;
    },
    ...options,
  });
}

// ----- Settings (owner) -----

const settingsQueryOptions = {
  queryKey: ["settings"] as const,
  queryFn: getSettings,
};

export function useSettings(options?: Omit<UseQueryOptions<SettingsResponse>, "queryKey" | "queryFn">) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    ...settingsQueryOptions,
    enabled: user?.role === "owner",
    ...options,
  });
}

/** Suspense-based: suspend until settings are loaded. Only mount when user is owner. Wrap in <Suspense>. */
export function useSettingsSuspense() {
  return useSuspenseQuery(settingsQueryOptions);
}

export function usePatchSettingsMutation(
  options?: UseMutationOptions<SettingsResponse, Error, PatchSettingsPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["settings"], (prev: unknown) =>
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
      queryClient.setQueryData(["settings"], (prev: unknown) =>
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
      queryClient.setQueryData(["settings"], (prev: unknown) =>
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
      queryClient.setQueryData(["settings"], (prev: unknown) =>
        prev ? { ...(prev as object), ...data } : prev
      );
    },
    ...options,
  });
}

// ----- Me (profile) -----

export function useProfileQuery(
  options?: Omit<UseQueryOptions<ProfileResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.profile,
    queryFn: getProfile,
    ...options,
  });
}

export function useProfilePreferencesQuery(
  options?: Omit<
    UseQueryOptions<{ app_preferences: ProfilePreferences }>,
    "queryKey" | "queryFn"
  >
) {
  return useQuery({
    queryKey: queryKeys.profilePreferences,
    queryFn: getProfilePreferences,
    ...options,
  });
}

export function usePatchProfileMutation(
  options?: UseMutationOptions<ProfileResponse, Error, PatchProfilePayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchProfile,
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.profile, data);
      queryClient.invalidateQueries({ queryKey: queryKeys.profilePreferences });
      queryClient.invalidateQueries({ queryKey: queryKeys.authMe });
      queryClient.invalidateQueries({ queryKey: queryKeys.users });
    },
    ...options,
  });
}

export function usePatchProfilePreferencesMutation(
  options?: UseMutationOptions<
    { app_preferences: ProfilePreferences },
    Error,
    Partial<ProfilePreferences>
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchProfilePreferences,
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.profilePreferences, data);
      queryClient.invalidateQueries({ queryKey: queryKeys.profile });
    },
    ...options,
  });
}

export function usePatchMeMutation(
  options?: UseMutationOptions<
    { name?: string; email?: string; pending_email?: string | null; preferred_locale?: string; preferred_theme?: string },
    Error,
    { name?: string; email?: string; preferred_locale?: string; preferred_theme?: string }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchMe,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.authMe });
      queryClient.invalidateQueries({ queryKey: queryKeys.users });
    },
    ...options,
  });
}

export function useChangePasswordMutation(
  options?: UseMutationOptions<unknown, Error, { current_password: string; new_password: string }>
) {
  return useMutation({
    mutationFn: changePassword,
    ...options,
  });
}

export function useSetInitialPasswordMutation(
  options?: UseMutationOptions<{ access_token: string; user: UserListItem }, Error, { new_password: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: setInitialPassword,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.authMe });
    },
    ...options,
  });
}

export function useDemoUnsubscribeMutation(
  options?: UseMutationOptions<{ ok: boolean; deletion_due_days?: number; message?: string }, Error, { email: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: demoUnsubscribe,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.authMe });
    },
    ...options,
  });
}

// ----- Users (admin) -----

export type { UserListItem, UpdateUserPayload } from "../api/services/userService";

export function useUsers(options?: Omit<UseQueryOptions<UserListItem[]>, "queryKey" | "queryFn">) {
  return useQuery({
    queryKey: queryKeys.users,
    queryFn: getUsers,
    ...options,
  });
}

export function useCreateUserMutation(
  options?: UseMutationOptions<UserListItem, Error, { email: string; name?: string; role: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.users }),
    ...options,
  });
}

export function useUpdateUserMutation(
  options?: UseMutationOptions<UserListItem, Error, UpdateUserPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.users }),
    ...options,
  });
}

export function useDeleteUserMutation(options?: UseMutationOptions<unknown, Error, number>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.users }),
    ...options,
  });
}

export function useResendInviteMutation(options?: UseMutationOptions<unknown, Error, number>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: resendInvite,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.users }),
    ...options,
  });
}

// ----- Knowledge base -----

export type KbItem = { uuid: string; name: string; description?: string; [key: string]: unknown };

export function useKbList(options?: Omit<UseQueryOptions<KbItem[]>, "queryKey" | "queryFn">) {
  return useQuery({
    queryKey: ["kb"],
    queryFn: async () => {
      const res = await api.get("/kb");
      return res.data as KbItem[];
    },
    ...options,
  });
}

export function useCreateKbMutation(
  options?: UseMutationOptions<KbItem, Error, { name: string; description?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; description?: string }) => {
      const res = await api.post("/kb", body);
      return res.data as KbItem;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kb"] }),
    ...options,
  });
}

export function useUpdateKbMutation(
  options?: UseMutationOptions<KbItem, Error, { uuid: string; name: string; description?: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ uuid, name, description }: { uuid: string; name: string; description?: string }) => {
      const res = await api.put(`/kb/${uuid}`, { name, description });
      return res.data as KbItem;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kb"] }),
    ...options,
  });
}

export function useDeleteKbMutation(
  options?: UseMutationOptions<unknown, Error, { uuid: string; confirm_name: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ uuid, confirm_name }: { uuid: string; confirm_name: string }) => {
      const res = await api.delete(`/kb/${uuid}`, { data: { confirm_name } });
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["kb"] }),
    ...options,
  });
}

// ----- Chat -----

export function useChatMutation(
  options?: UseMutationOptions<{ answer: string }, Error, { question: string }>
) {
  return useMutation({
    mutationFn: async ({ question }: { question: string }) => {
      const res = await api.post("/chat", { question });
      return res.data as { answer: string };
    },
    ...options,
  });
}
