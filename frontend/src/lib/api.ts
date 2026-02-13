export type SparkPoint = {
  t: string;
  v: number;
};

export type SummaryItem = {
  id: string;
  name: string;
  unit: string | null;
  price_type: string | null;
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

export type SeriesResponse = {
  id: string;
  range: "1m" | "3m" | "6m" | "1y";
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

export function fetchInflationSummary(): Promise<SummaryResponse> {
  return fetchJson<SummaryResponse>("/inflation/summary");
}

export function fetchCommoditySeries(id: string, range: "1m" | "3m" | "1y" = "1m"): Promise<SeriesResponse> {
  const query = new URLSearchParams({ id, range });
  return fetchJson<SeriesResponse>(`/commodities/series?${query.toString()}`);
}

export function fetchInflationSeries(
  id: string,
  range: "3m" | "6m" | "1y" = "1y",
): Promise<SeriesResponse> {
  const query = new URLSearchParams({ id, range });
  return fetchJson<SeriesResponse>(`/inflation/series?${query.toString()}`);
}
