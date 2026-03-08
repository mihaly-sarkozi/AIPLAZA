import {
  useQuery,
  useMutation,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import api from "../../../api/axiosClient";

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
