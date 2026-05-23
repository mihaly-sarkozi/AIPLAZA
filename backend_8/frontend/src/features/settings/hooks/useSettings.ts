import { useQuery, useMutation, useQueryClient, type UseQueryOptions, type UseMutationOptions } from "@tanstack/react-query";
import { useAuthStore } from "../../auth/state/authStore";
import { queryKeys } from "../../../queryKeys";
import {
  getSettings,
  patchSettings,
  type PatchSettingsPayload,
  type SettingsResponse,
} from "../../../api/services/settingsService";

export function useSettings(options?: Omit<UseQueryOptions<SettingsResponse>, "queryKey" | "queryFn">) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: queryKeys.settings,
    queryFn: getSettings,
    enabled: user?.role === "owner",
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
