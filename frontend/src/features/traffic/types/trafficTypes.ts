// Feladat: A traffic frontend API response típusait tartalmazza. Ezek írják le a /traffic/overview read modellt.

export type TrafficCatalogEntry = {
  entry_type: string;
  code: string;
  name: string;
  currency: string;
  price_cents: number;
  price: number;
  included: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

export type TrafficOverview = {
  current_period_key: string;
  current_period_start_iso: string;
  current_period_end_iso: string;
  catalog: TrafficCatalogEntry[];
  subscription: Record<string, unknown>;
  limits: Record<string, unknown>;
  usage: Record<string, unknown>;
};
