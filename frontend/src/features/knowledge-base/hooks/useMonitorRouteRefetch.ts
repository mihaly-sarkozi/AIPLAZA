import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { queryKeys } from "../../../queryKeys";

/** Monitor útvonalváltáskor / visszalépéskor azonnali refetch (ne maradjon stale progress). */
export function useMonitorRouteRefetch(kbUuid: string | undefined) {
  const location = useLocation();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!kbUuid) return;
    if (!location.pathname.includes(`/kb/monitor/${kbUuid}`)) return;

    void queryClient.refetchQueries({
      queryKey: queryKeys.kbProcessingMonitor(kbUuid),
      type: "active",
    });
  }, [kbUuid, location.pathname, queryClient]);
}
