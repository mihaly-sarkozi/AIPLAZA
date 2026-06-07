// Feladat: React Query hook a traffic overview read modellhez. A jogosultsági enable feltételt a traffic modulban tartja.

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { queryKeys } from "../../../queryKeys";
import { useAuthStore } from "../../auth/state/authStore";
import { fetchTrafficOverview } from "../api/trafficService";
import type { TrafficOverview } from "../types/trafficTypes";

export function useTrafficOverview(options?: Omit<UseQueryOptions<TrafficOverview>, "queryKey" | "queryFn">) {
  const user = useAuthStore((s) => s.user);
  return useQuery({
    queryKey: queryKeys.trafficOverview,
    queryFn: fetchTrafficOverview,
    enabled: user?.role === "owner" || user?.role === "admin",
    ...options,
  });
}
