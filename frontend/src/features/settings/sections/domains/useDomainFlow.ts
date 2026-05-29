// frontend/src/features/settings/sections/domains/useDomainFlow.ts
// Feladat: Domain list/add/verify/delete/copy flow és query invalidáció kezelése.
// Sárközi Mihály - 2026.05.29

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../../../queryKeys";
import { addCustomDomain, deleteCustomDomain, getDomainOverview, verifyCustomDomain } from "../../api/domainService";
import { mapDomainOverview } from "./domainMapper";

export function useDomainFlow() {
  const queryClient = useQueryClient();
  const [customDomainInput, setCustomDomainInput] = useState("");
  const overviewQuery = useQuery({
    queryKey: queryKeys.domainOverview,
    queryFn: getDomainOverview,
  });
  const addMutation = useMutation({
    mutationFn: (domain: string) => addCustomDomain(domain),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: queryKeys.domainOverview }),
  });
  const verifyMutation = useMutation({
    mutationFn: (domain: string) => verifyCustomDomain(domain),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: queryKeys.domainOverview }),
  });
  const deleteMutation = useMutation({
    mutationFn: (domain: string) => deleteCustomDomain(domain),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: queryKeys.domainOverview }),
  });

  const overview = useMemo(() => mapDomainOverview(overviewQuery.data), [overviewQuery.data]);

  return {
    customDomainInput,
    setCustomDomainInput,
    overview,
    loading: overviewQuery.isLoading,
    error: overviewQuery.error ?? addMutation.error ?? verifyMutation.error ?? deleteMutation.error,
    addPending: addMutation.isPending,
    verifyPending: verifyMutation.isPending,
    deletePending: deleteMutation.isPending,
    addDomain: (domain: string) => addMutation.mutateAsync(domain),
    verifyDomain: (domain: string) => verifyMutation.mutateAsync(domain),
    deleteDomain: (domain: string) => deleteMutation.mutateAsync(domain),
  };
}
