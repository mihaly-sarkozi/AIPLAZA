import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import api from "../../../api/axiosClient";
import { useAuthStore } from "../../auth/state/authStore";

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
