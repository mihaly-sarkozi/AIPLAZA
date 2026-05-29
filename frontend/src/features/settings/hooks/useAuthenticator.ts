// frontend/src/features/settings/hooks/useAuthenticator.ts
// Feladat: Legacy authenticator React Query hookok a settings security nézethez.
// Sárközi Mihály - 2026.05.29

import { useMutation, useQuery, useQueryClient, type UseMutationOptions, type UseQueryOptions } from "@tanstack/react-query";

import { useAuthStore } from "../../auth/state/authStore";
import {
  confirmAuthenticatorSetup,
  disableAuthenticator,
  getAuthenticatorStatus,
  startAuthenticatorSetup,
  type AuthenticatorSetupResponse,
  type AuthenticatorStatusResponse,
} from "../../../api/services/authenticatorService";
import { queryKeys } from "../../../queryKeys";

export function useAuthenticatorStatus(
  options?: Omit<UseQueryOptions<AuthenticatorStatusResponse>, "queryKey" | "queryFn">
) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: queryKeys.authenticatorStatus,
    queryFn: getAuthenticatorStatus,
    enabled: !!user,
    ...options,
  });
}

export function useStartAuthenticatorSetupMutation(
  options?: UseMutationOptions<AuthenticatorSetupResponse, Error, void>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: startAuthenticatorSetup,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.authenticatorStatus });
    },
    ...options,
  });
}

export function useConfirmAuthenticatorSetupMutation(
  options?: UseMutationOptions<AuthenticatorStatusResponse, Error, string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => confirmAuthenticatorSetup(code),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.authenticatorStatus });
    },
    ...options,
  });
}

export function useDisableAuthenticatorMutation(
  options?: UseMutationOptions<AuthenticatorStatusResponse, Error, void>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: disableAuthenticator,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.authenticatorStatus });
    },
    ...options,
  });
}
