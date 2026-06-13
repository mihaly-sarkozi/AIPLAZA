import { useMutation, type UseMutationOptions } from "@tanstack/react-query";
import { postTenantReset, type TenantResetPayload, type TenantResetResponse } from "../../../api/services/settingsService";

export function useTenantResetMutation(
  options?: UseMutationOptions<TenantResetResponse, Error, TenantResetPayload>
) {
  return useMutation({
    mutationFn: postTenantReset,
    ...options,
  });
}
