// frontend/src/features/settings/sections/security/useAuthenticatorFlow.ts
// Feladat: Authenticator MFA flow állapot- és műveletkezelése a settings security szekcióhoz.
// Sárközi Mihály - 2026.05.29

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../../../queryKeys";
import {
  confirmAuthenticatorSetup,
  disableAuthenticator,
  getAuthenticatorStatus,
  startAuthenticatorSetup,
  type AuthenticatorSetupResponse,
} from "../../api/authenticatorService";

export function useAuthenticatorFlow() {
  const queryClient = useQueryClient();
  const [setupData, setSetupData] = useState<AuthenticatorSetupResponse | null>(null);
  const [code, setCode] = useState("");
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);

  const statusQuery = useQuery({
    queryKey: queryKeys.authenticatorStatus,
    queryFn: getAuthenticatorStatus,
  });
  const startMutation = useMutation({
    mutationFn: startAuthenticatorSetup,
    onSuccess: async (data) => {
      setSetupData(data);
      setCode("");
      setWizardStep(1);
      setWizardOpen(true);
      await queryClient.invalidateQueries({ queryKey: queryKeys.authenticatorStatus });
    },
  });
  const confirmMutation = useMutation({
    mutationFn: (value: string) => confirmAuthenticatorSetup(value),
    onSuccess: async () => {
      setSetupData(null);
      setCode("");
      setWizardStep(1);
      setWizardOpen(false);
      await queryClient.invalidateQueries({ queryKey: queryKeys.authenticatorStatus });
    },
  });
  const disableMutation = useMutation({
    mutationFn: disableAuthenticator,
    onSuccess: async () => {
      setSetupData(null);
      setCode("");
      setWizardStep(1);
      setWizardOpen(false);
      await queryClient.invalidateQueries({ queryKey: queryKeys.authenticatorStatus });
    },
  });

  const status = statusQuery.data;
  const enabled = Boolean(status?.enabled);
  const pending = Boolean(status?.pending);
  const setupReady = !enabled && wizardOpen && Boolean(setupData);

  return {
    enabled,
    pending,
    setupReady,
    statusError: statusQuery.error,
    setupData,
    code,
    wizardStep,
    startPending: startMutation.isPending,
    confirmPending: confirmMutation.isPending,
    disablePending: disableMutation.isPending,
    setCode,
    setWizardStep,
    openWizard: () => setWizardOpen(true),
    closeWizard: () => {
      if (confirmMutation.isPending) return;
      setWizardOpen(false);
      setWizardStep(1);
    },
    startSetup: () => startMutation.mutateAsync(),
    confirmSetup: () => confirmMutation.mutateAsync(code.trim()),
    disable: () => disableMutation.mutateAsync(),
    isCodeValid: useMemo(() => code.trim().length === 6, [code]),
  };
}
