import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import api from "../../../api/axiosClient";
import { useAuthStore } from "../../auth/state/authStore";

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
