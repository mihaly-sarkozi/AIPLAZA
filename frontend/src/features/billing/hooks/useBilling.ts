import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
  type UseMutationOptions,
} from "@tanstack/react-query";
import api from "../../../api/axiosClient";
import { useAuthStore } from "../../auth/state/authStore";
import { queryKeys } from "../../../queryKeys";

export type BillingCatalogEntry = {
  entry_type: string;
  code: string;
  name: string;
  currency: string;
  price_cents: number;
  price: number;
  included: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

export type BillingUpgradePreview = {
  immediate_use: boolean;
  total_period_days: number;
  remaining_period_days: number;
  proration_fraction: number;
  old_plan_code: string;
  new_plan_code: string;
  old_monthly_cents: number;
  new_monthly_cents: number;
  delta_monthly_cents: number;
  prorated_charge_cents: number;
  old_remaining_credit_cents: number;
  next_period_charge_cents: number;
  training_initial_fee_cents: number;
  total_charge_cents: number;
  paid_until_iso: string;
  currency: string;
};

export type BillingUpgradeComplete = {
  status: string;
  prorated_charge_cents: number;
  prorated_charge: number;
  old_remaining_credit_cents: number;
  next_period_charge_cents: number;
  training_initial_fee_cents: number;
  total_charge_cents: number;
  paid_until_iso: string;
};

export type BillingCancellationResponse = {
  status: string;
  message: string;
  active_kb_count: number;
  cancellation_request_id?: number | null;
  current_period_end_iso?: string | null;
};

export type BillingOverview = {
  current_period_key: string;
  current_period_start_iso: string;
  current_period_end_iso: string;
  catalog: BillingCatalogEntry[];
  subscription: Record<string, unknown>;
  limits: Record<string, unknown>;
  usage: Record<string, unknown>;
  invoices: Array<Record<string, unknown>>;
  estimated_next_invoice: Record<string, unknown>;
  payment_warning?: Record<string, unknown> | null;
  demo_mode?: boolean;
};

export type BillingAccessStatus = {
  restricted: boolean;
  payment_warning?: Record<string, unknown> | null;
};

export function useBillingAccessStatus(options?: Omit<UseQueryOptions<BillingAccessStatus>, "queryKey" | "queryFn">) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: queryKeys.billingAccessStatus,
    queryFn: async () => {
      const res = await api.get("/billing/access-status");
      return res.data as BillingAccessStatus;
    },
    enabled: Boolean(user),
    ...options,
  });
}

export function useBillingOverview(options?: Omit<UseQueryOptions<BillingOverview>, "queryKey" | "queryFn">) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: queryKeys.billingOverview,
    queryFn: async () => {
      const res = await api.get("/billing/overview");
      return res.data as BillingOverview;
    },
    enabled: user?.role === "owner" || user?.role === "admin",
    ...options,
  });
}

export function useBillingUpgradePreview(
  planCode: string,
  billingPeriod: string,
  options?: Omit<UseQueryOptions<BillingUpgradePreview>, "queryKey" | "queryFn">
) {
  const user = useAuthStore((s) => s.user);
  const { enabled: optionEnabled, ...queryOptions } = options ?? {};
  const allowFetch = Boolean(planCode) && (optionEnabled ?? true);
  return useQuery({
    queryKey: queryKeys.billingUpgradePreview(planCode, billingPeriod),
    queryFn: async () => {
      const res = await api.get("/billing/subscription/upgrade-preview", {
        params: { plan_code: planCode, billing_period: billingPeriod },
      });
      return res.data as BillingUpgradePreview;
    },
    enabled: user?.role === "owner" && allowFetch,
    ...queryOptions,
  });
}

export function useCompleteUpgradeMutation(
  options?: UseMutationOptions<
    BillingUpgradeComplete,
    Error,
    { plan_code: string; billing_period: string }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { plan_code: string; billing_period: string }) => {
      const res = await api.post("/billing/subscription/upgrade-complete", body);
      return res.data as BillingUpgradeComplete;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
      await queryClient.invalidateQueries({ queryKey: ["billing", "upgradePreview"] });
    },
    ...options,
  });
}

export function useUpdateSubscriptionMutation(
  options?: UseMutationOptions<
    { status: string; message: string },
    Error,
    { plan_code: string; billing_period: string }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { plan_code: string; billing_period: string }) => {
      const res = await api.patch("/billing/subscription", body);
      return res.data as { status: string; message: string };
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
    },
    ...options,
  });
}

export function useCancelSubscriptionMutation(
  options?: UseMutationOptions<
    BillingCancellationResponse,
    Error,
    { reason_code: string; reason_text: string }
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { reason_code: string; reason_text: string }) => {
      const res = await api.post("/billing/subscription/cancel", body);
      return res.data as BillingCancellationResponse;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
      await queryClient.invalidateQueries({ queryKey: queryKeys.billingAccessStatus });
    },
    ...options,
  });
}

export function useDeleteServiceAccessMutation(
  options?: UseMutationOptions<
    BillingCancellationResponse,
    Error,
    void
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await api.post("/billing/subscription/delete-access");
      return res.data as BillingCancellationResponse;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
      await queryClient.invalidateQueries({ queryKey: queryKeys.billingAccessStatus });
    },
    ...options,
  });
}

export function useRestoreSubscriptionRenewalMutation(
  options?: UseMutationOptions<
    BillingCancellationResponse,
    Error,
    void
  >
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await api.post("/billing/subscription/restore-renewal");
      return res.data as BillingCancellationResponse;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
      await queryClient.invalidateQueries({ queryKey: queryKeys.billingAccessStatus });
    },
    ...options,
  });
}

export function usePurchaseAddonMutation(
  options?: UseMutationOptions<Record<string, unknown>, Error, { addon_code: string; quantity: number }>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { addon_code: string; quantity: number }) => {
      const res = await api.post("/billing/addons/purchase", body);
      return res.data as Record<string, unknown>;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
    },
    ...options,
  });
}
