// Feladat: A traffic modul vékony API service rétege. Csak HTTP hívást végez, UI/form/billing logikát nem tartalmaz.

import api from "../../../api/axiosClient";
import type { TrafficOverview } from "../types/trafficTypes";

export async function fetchTrafficOverview(): Promise<TrafficOverview> {
  const res = await api.get("/traffic/overview");
  return res.data as TrafficOverview;
}
