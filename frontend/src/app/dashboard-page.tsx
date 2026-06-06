"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  fetchCommoditiesSummary,
  fetchCommoditySeries,
  fetchIndexSeries,
  fetchIndexesSummary,
  fetchInflationSeries,
  fetchInflationSummary,
  fetchMag7Series,
  fetchMag7Summary,
  type MarketRange,
  type SparkPoint,
} from "@/lib/api";

import { DashboardView } from "./dashboard-view";

export function DashboardPage() {
  const [marketRange, setMarketRange] = useState<MarketRange>("1m");

  const commoditiesQuery = useQuery({
    queryKey: ["summary", "commodities"],
    queryFn: fetchCommoditiesSummary,
  });

  const mag7Query = useQuery({
    queryKey: ["summary", "mag7"],
    queryFn: fetchMag7Summary,
  });

  const indexesQuery = useQuery({
    queryKey: ["summary", "indexes"],
    queryFn: fetchIndexesSummary,
  });

  const inflationQuery = useQuery({
    queryKey: ["summary", "inflation"],
    queryFn: fetchInflationSummary,
  });

  const inflationIds = useMemo(
    () => (inflationQuery.data?.items ?? []).map((item) => item.id),
    [inflationQuery.data?.items],
  );

  const marketIdsByModule = useMemo(
    () => ({
      commodities: (commoditiesQuery.data?.items ?? []).map((item) => item.id),
      mag7: (mag7Query.data?.items ?? []).map((item) => item.id),
      indexes: (indexesQuery.data?.items ?? []).map((item) => item.id),
    }),
    [commoditiesQuery.data?.items, indexesQuery.data?.items, mag7Query.data?.items],
  );

  const marketSeriesQuery = useQuery({
    queryKey: ["market-series", marketRange, marketIdsByModule],
    enabled:
      marketIdsByModule.commodities.length > 0 ||
      marketIdsByModule.mag7.length > 0 ||
      marketIdsByModule.indexes.length > 0,
    queryFn: async () => {
      const results: Record<"commodities" | "mag7" | "indexes", Record<string, SparkPoint[]>> = {
        commodities: {},
        mag7: {},
        indexes: {},
      };
      let failedCount = 0;

      const requests = [
        ...marketIdsByModule.commodities.map((id) => ({ module: "commodities" as const, id, fetcher: fetchCommoditySeries })),
        ...marketIdsByModule.mag7.map((id) => ({ module: "mag7" as const, id, fetcher: fetchMag7Series })),
        ...marketIdsByModule.indexes.map((id) => ({ module: "indexes" as const, id, fetcher: fetchIndexSeries })),
      ];

      await Promise.all(
        requests.map(async (request) => {
          try {
            const series = await request.fetcher(request.id, marketRange);
            results[request.module][request.id] = series.points;
          } catch {
            failedCount += 1;
          }
        }),
      );

      return { series: results, failedCount };
    },
  });

  const inflationSeriesQuery = useQuery({
    queryKey: ["inflation-series", inflationIds],
    enabled: inflationIds.length > 0,
    queryFn: async () => {
      const results: Record<string, SparkPoint[]> = {};
      let failedCount = 0;

      await Promise.all(
        inflationIds.map(async (id) => {
          try {
            const series = await fetchInflationSeries(id, "1y");
            results[id] = series.points;
          } catch {
            failedCount += 1;
          }
        }),
      );

      return { series: results, failedCount };
    },
  });

  const warnings: string[] = [];
  if (commoditiesQuery.isError) warnings.push("Kunde inte hamta ravaror just nu.");
  if (mag7Query.isError) warnings.push("Kunde inte hamta Mag 7 just nu.");
  if (indexesQuery.isError) warnings.push("Kunde inte hamta index just nu.");
  if (inflationQuery.isError) warnings.push("Kunde inte hamta inflation just nu.");
  if (marketSeriesQuery.data?.failedCount) warnings.push("Vissa marknadsserier kunde inte hamtas.");
  if (inflationSeriesQuery.data?.failedCount) warnings.push("Vissa inflationsserier kunde inte hamtas.");

  return (
    <DashboardView
      commodities={commoditiesQuery.data ?? null}
      mag7={mag7Query.data ?? null}
      indexes={indexesQuery.data ?? null}
      inflation={inflationQuery.data ?? null}
      marketRange={marketRange}
      onMarketRangeChange={setMarketRange}
      marketSeriesByModule={marketSeriesQuery.data?.series ?? { commodities: {}, mag7: {}, indexes: {} }}
      inflationSeries={inflationSeriesQuery.data?.series ?? {}}
      warnings={warnings}
    />
  );
}
