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
  fetchPortfolioSeries,
  fetchPortfolioStatus,
  fetchPortfolioSummary,
  type MarketRange,
  type SparkPoint,
} from "@/lib/api";

import { DashboardView } from "./dashboard-view";

async function fetchSeriesSequentially<TRequest extends { id: string; name: string }>(
  requests: TRequest[],
  fetchOne: (request: TRequest) => Promise<void>,
): Promise<string[]> {
  const failedNames: string[] = [];
  for (const request of requests) {
    try {
      await fetchOne(request);
    } catch {
      failedNames.push(request.name);
    }
  }
  return failedNames;
}

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

  const portfolioStatusQuery = useQuery({
    queryKey: ["portfolio", "status"],
    queryFn: fetchPortfolioStatus,
    retry: false,
  });

  const portfolioQuery = useQuery({
    queryKey: ["summary", "portfolio"],
    queryFn: fetchPortfolioSummary,
    enabled: portfolioStatusQuery.data?.enabled === true,
    retry: false,
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
  const portfolioSummarySettled = portfolioStatusQuery.data?.enabled !== true || portfolioQuery.isSuccess || portfolioQuery.isError;
  const shouldFetchExpandedSeries = marketRange !== "1m" && portfolioSummarySettled;

  const marketSeriesQuery = useQuery({
    queryKey: ["market-series", marketRange, marketIdsByModule],
    enabled:
      shouldFetchExpandedSeries &&
      (marketIdsByModule.commodities.length > 0 ||
        marketIdsByModule.mag7.length > 0 ||
        marketIdsByModule.indexes.length > 0),
    queryFn: async () => {
      const results: Record<"commodities" | "mag7" | "indexes", Record<string, SparkPoint[]>> = {
        commodities: {},
        mag7: {},
        indexes: {},
      };

      const requests = [
        ...(commoditiesQuery.data?.items ?? []).map((item) => ({ module: "commodities" as const, id: item.id, name: item.name, fetcher: fetchCommoditySeries })),
        ...(mag7Query.data?.items ?? []).map((item) => ({ module: "mag7" as const, id: item.id, name: item.name, fetcher: fetchMag7Series })),
        ...(indexesQuery.data?.items ?? []).map((item) => ({ module: "indexes" as const, id: item.id, name: item.name, fetcher: fetchIndexSeries })),
      ];

      const failedNames = await fetchSeriesSequentially(requests, async (request) => {
        const series = await request.fetcher(request.id, marketRange);
        results[request.module][request.id] = series.points;
      });

      return { series: results, failedNames };
    },
  });

  const portfolioChartItems = useMemo(
    () => (portfolioQuery.data?.holdings ?? []).filter((item) => item.has_chart),
    [portfolioQuery.data?.holdings],
  );
  const portfolioIds = useMemo(() => portfolioChartItems.map((item) => item.id), [portfolioChartItems]);

  const portfolioSeriesQuery = useQuery({
    queryKey: ["portfolio-series", marketRange, portfolioIds],
    enabled: shouldFetchExpandedSeries && portfolioIds.length > 0,
    queryFn: async () => {
      const results: Record<string, SparkPoint[]> = {};

      const failedNames = await fetchSeriesSequentially(portfolioChartItems, async (item) => {
        const series = await fetchPortfolioSeries(item.id, marketRange);
        results[item.id] = series.points;
      });

      return { series: results, failedNames };
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
  if (marketSeriesQuery.data?.failedNames.length) warnings.push(`Marknadsserier kunde inte hamtas: ${marketSeriesQuery.data.failedNames.join(", ")}.`);
  if (portfolioQuery.isError) warnings.push("Kunde inte hamta Min Avanza just nu.");
  if (portfolioSeriesQuery.data?.failedNames.length) warnings.push(`Portfoliografer kunde inte hamtas: ${portfolioSeriesQuery.data.failedNames.join(", ")}.`);
  if (inflationSeriesQuery.data?.failedCount) warnings.push("Vissa inflationsserier kunde inte hamtas.");

  return (
    <DashboardView
      commodities={commoditiesQuery.data ?? null}
      mag7={mag7Query.data ?? null}
      indexes={indexesQuery.data ?? null}
      inflation={inflationQuery.data ?? null}
      portfolio={portfolioQuery.data ?? null}
      marketRange={marketRange}
      onMarketRangeChange={setMarketRange}
      marketSeriesByModule={marketSeriesQuery.data?.series ?? { commodities: {}, mag7: {}, indexes: {} }}
      portfolioSeries={portfolioSeriesQuery.data?.series ?? {}}
      inflationSeries={inflationSeriesQuery.data?.series ?? {}}
      warnings={warnings}
    />
  );
}
