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
  type UserListItem,
  type UpdateUserPayload,
} from "../api/services/userService";
import { queryKeys } from "../queryKeys";
import { useAuthStore } from "../store/authStore";

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
    { access_token?: string; pending_token?: string },
    Error,
    Record<string, unknown>
  >
) {
  return useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const res = await api.post("/auth/login", payload);
      return res.data as { access_token?: string; pending_token?: string };
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
  queryFn: async () => {
    const res = await api.get("/settings");
    return res.data as { two_factor_enabled?: boolean };
  },
};

export function useSettings(options?: Omit<UseQueryOptions<{ two_factor_enabled?: boolean }>, "queryKey" | "queryFn">) {
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
  options?: UseMutationOptions<
    { two_factor_enabled?: boolean },
    Error,
    { two_factor_enabled: boolean }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { two_factor_enabled: boolean }) => {
      const res = await api.patch("/settings", body);
      return res.data as { two_factor_enabled?: boolean };
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["settings"], (prev: unknown) =>
        prev ? { ...(prev as object), ...data } : data
      );
    },
    ...options,
  });
}

// ----- Me (profile) -----

export function usePatchMeMutation(
  options?: UseMutationOptions<
    { name?: string; preferred_locale?: string; preferred_theme?: string },
    Error,
    { name?: string; preferred_locale?: string; preferred_theme?: string }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: patchMe,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.authMe });
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

export function useKbTrainTextMutation(
  options?: UseMutationOptions<unknown, Error, { uuid: string; title: string; content: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ uuid, title, content }: { uuid: string; title: string; content: string }) => {
      const res = await api.post(`/kb/${uuid}/train/text`, { title, content });
      return res.data;
    },
    onSuccess: (_, { uuid }) =>
      queryClient.invalidateQueries({ queryKey: ["kb", uuid] }),
    ...options,
  });
}

export function useKbTrainFileMutation(
  options?: UseMutationOptions<unknown, Error, { uuid: string; formData: FormData }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ uuid, formData }: { uuid: string; formData: FormData }) => {
      const res = await api.post(`/kb/${uuid}/train/file`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return res.data;
    },
    onSuccess: (_, { uuid }) =>
      queryClient.invalidateQueries({ queryKey: ["kb", uuid] }),
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
