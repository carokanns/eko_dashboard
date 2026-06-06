export type SparkPoint = {
  t: string;
  v: number;
};

export type SummaryItem = {
  id: string;
  name: string;
  unit: string | null;
  price_type: string | null;
  display_group?: string | null;
  last: number | null;
  day_abs: number | null;
  day_pct: number | null;
  w1_pct: number | null;
  ytd_pct: number | null;
  y1_pct: number | null;
  timestamp_local: string | null;
  is_stale: boolean;
  sparkline: SparkPoint[];
};

export type ApiMeta = {
  source: string;
  cached: boolean;
  fetched_at: string;
  stale_reason?: "none" | "global_threshold" | "provider_error" | "no_recent_success";
  age_seconds?: number;
};

export type SummaryResponse = {
  items: SummaryItem[];
  meta: ApiMeta;
};

export type MarketRange = "1m" | "3m" | "6m" | "1y";

export type SeriesResponse = {
  id: string;
  range: MarketRange;
  points: SparkPoint[];
  meta: ApiMeta;
};

const baseUrl = "/api/dashboard";

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as T;
}

export function fetchCommoditiesSummary(): Promise<SummaryResponse> {
  return fetchJson<SummaryResponse>("/commodities/summary");
}

export function fetchMag7Summary(): Promise<SummaryResponse> {
  return fetchJson<SummaryResponse>("/mag7/summary");
}

export function fetchIndexesSummary(): Promise<SummaryResponse> {
  return fetchJson<SummaryResponse>("/indexes/summary");
}

export function fetchInflationSummary(): Promise<SummaryResponse> {
  return fetchJson<SummaryResponse>("/inflation/summary");
}

export function fetchCommoditySeries(id: string, range: MarketRange = "1m"): Promise<SeriesResponse> {
  const query = new URLSearchParams({ id, range });
  return fetchJson<SeriesResponse>(`/commodities/series?${query.toString()}`);
}

export function fetchMag7Series(id: string, range: MarketRange = "1m"): Promise<SeriesResponse> {
  const query = new URLSearchParams({ id, range });
  return fetchJson<SeriesResponse>(`/mag7/series?${query.toString()}`);
}

export function fetchIndexSeries(id: string, range: MarketRange = "1m"): Promise<SeriesResponse> {
  const query = new URLSearchParams({ id, range });
  return fetchJson<SeriesResponse>(`/indexes/series?${query.toString()}`);
}

export function fetchInflationSeries(
  id: string,
  range: MarketRange = "1y",
): Promise<SeriesResponse> {
  const query = new URLSearchParams({ id, range });
  return fetchJson<SeriesResponse>(`/inflation/series?${query.toString()}`);
}
