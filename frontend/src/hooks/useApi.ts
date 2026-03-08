import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import api from "../api/axiosClient";
import { useAuthStore } from "../store/authStore";

// ----- Auth / settings (unauthenticated or public) -----

export function useDefaultSettings(
  options?: Omit<UseQueryOptions<{ locale?: string; theme?: string }>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: ["auth", "default-settings"],
    queryFn: async () => {
      const res = await api.get("/auth/default-settings");
      return res.data as { locale?: string; theme?: string };
    },
    ...options,
  });
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

export function useSettings(options?: Omit<UseQueryOptions<{ two_factor_enabled?: boolean }>, "queryKey" | "queryFn">) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      const res = await api.get("/settings");
      return res.data as { two_factor_enabled?: boolean };
    },
    enabled: user?.role === "owner",
    ...options,
  });
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
    mutationFn: async (body: { name?: string; preferred_locale?: string; preferred_theme?: string }) => {
      const res = await api.patch("/auth/me", body);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
    ...options,
  });
}

export function useChangePasswordMutation(
  options?: UseMutationOptions<unknown, Error, { current_password: string; new_password: string }>
) {
  return useMutation({
    mutationFn: async (body: { current_password: string; new_password: string }) => {
      const res = await api.post("/auth/me/change-password", body);
      return res.data;
    },
    ...options,
  });
}

// ----- Users (admin) -----

export type UserListItem = {
  id: number;
  email: string;
  name?: string | null;
  role: string;
  is_active: boolean;
  created_at?: string;
  [key: string]: unknown;
};

export function useUsers(options?: Omit<UseQueryOptions<UserListItem[]>, "queryKey" | "queryFn">) {
  return useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const res = await api.get("/users");
      return res.data as UserListItem[];
    },
    ...options,
  });
}

export function useCreateUserMutation(
  options?: UseMutationOptions<UserListItem, Error, { email: string; name?: string; role: string }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { email: string; name?: string; role: string }) => {
      const res = await api.post("/users", body);
      return res.data as UserListItem;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
    ...options,
  });
}

export type UpdateUserPayload = {
  id: number;
  name?: string;
  is_active?: boolean;
  email?: string;
  role?: string;
};

export function useUpdateUserMutation(
  options?: UseMutationOptions<UserListItem, Error, UpdateUserPayload>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: UpdateUserPayload) => {
      const res = await api.put(`/users/${id}`, body);
      return res.data as UserListItem;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
    ...options,
  });
}

export function useDeleteUserMutation(options?: UseMutationOptions<unknown, Error, number>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (userId: number) => {
      const res = await api.delete(`/users/${userId}`);
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
    ...options,
  });
}

export function useResendInviteMutation(options?: UseMutationOptions<unknown, Error, number>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (userId: number) => {
      const res = await api.post(`/users/${userId}/resend-invite`);
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
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
