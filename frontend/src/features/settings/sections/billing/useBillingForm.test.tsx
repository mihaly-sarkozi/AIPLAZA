// frontend/src/features/settings/sections/billing/useBillingForm.test.tsx
// Feladat: useBillingForm hook mentési és validációs viselkedésének tesztelése.
// Sárközi Mihály - 2026.05.29

import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { useAuthStore } from "../../../auth/state/authStore";
import { useBillingForm } from "./useBillingForm";

const getBillingSettingsMock = vi.fn();
const patchBillingSettingsMock = vi.fn();

vi.mock("../../api/settingsService", async () => {
  const actual = await vi.importActual<object>("../../api/settingsService");
  return {
    ...actual,
    getBillingSettings: () => getBillingSettingsMock(),
    patchBillingSettings: (payload: unknown) => patchBillingSettingsMock(payload),
  };
});

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useBillingForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ token: "x", user: { id: 1, email: "admin@example.test", role: "admin" }, loadingUser: false });
    getBillingSettingsMock.mockResolvedValue({
      billing_customer_type: "company",
      billing_full_name: "",
      billing_company_name: "",
      billing_tax_id: "",
      billing_address_line: "",
      billing_postal_code: "",
      billing_city: "",
      billing_region: "",
      billing_country: "HU",
    });
    patchBillingSettingsMock.mockResolvedValue({});
  });

  it("does not call mutation when validation fails", async () => {
    const { result } = renderHook(() => useBillingForm((k) => k), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      const saveResult = await result.current.save();
      expect(saveResult.ok).toBe(false);
    });
    expect(patchBillingSettingsMock).not.toHaveBeenCalled();
  });

  it("sends mapped payload on successful save", async () => {
    const { result } = renderHook(() => useBillingForm((k) => k), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.updateField("companyName", "Acme Kft");
      result.current.updateField("taxId", "HU12345678");
      result.current.updateField("addressLine", "Fo utca 1");
      result.current.updateField("postalCode", "1111");
      result.current.updateField("city", "Budapest");
      result.current.updateField("country", "HU");
    });
    await act(async () => {
      const saveResult = await result.current.save();
      expect(saveResult.ok).toBe(true);
    });

    expect(patchBillingSettingsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        billing_customer_type: "company",
        billing_company_name: "Acme Kft",
        billing_tax_id: "HU12345678",
        billing_postal_code: "1111",
      })
    );
  });
});
