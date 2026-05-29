// frontend/src/features/settings/hooks/useDomainSettings.ts
// Feladat: Legacy domain React Query hookok a settings modulból használt domain műveletekhez.
// Sárközi Mihály - 2026.05.29

import { useMutation, useQuery, useQueryClient, type UseMutationOptions, type UseQueryOptions } from "@tanstack/react-query";

import { useAuthStore } from "../../auth/state/authStore";
import { queryKeys } from "../../../queryKeys";
import {
  addCustomDomain,
  deleteCustomDomain,
  getDomainOverview,
  type DomainOverviewResponse,
  type DomainRecordResponse,
  verifyCustomDomain,
} from "../../../api/services/domainService";

export function useDomainOverview(options?: Omit<UseQueryOptions<DomainOverviewResponse>, "queryKey" | "queryFn">) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: queryKeys.domainOverview,
    queryFn: getDomainOverview,
    enabled: user?.role === "owner" || user?.role === "admin",
    ...options,
  });
}

export function useAddCustomDomainMutation(options?: UseMutationOptions<DomainRecordResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (domain: string) => addCustomDomain(domain),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.domainOverview });
    },
    ...options,
  });
}

export function useVerifyCustomDomainMutation(options?: UseMutationOptions<DomainRecordResponse, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (domain: string) => verifyCustomDomain(domain),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.domainOverview });
    },
    ...options,
  });
}

export function useDeleteCustomDomainMutation(options?: UseMutationOptions<void, Error, string>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (domain: string) => deleteCustomDomain(domain),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.domainOverview });
    },
    ...options,
  });
}
