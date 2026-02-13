"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  fetchCommoditiesSummary,
  fetchInflationSeries,
  fetchInflationSummary,
  fetchMag7Summary,
  type SparkPoint,
} from "@/lib/api";

import { DashboardView } from "./dashboard-view";

export default function Home() {
  const commoditiesQuery = useQuery({
    queryKey: ["summary", "commodities"],
    queryFn: fetchCommoditiesSummary,
  });

  const mag7Query = useQuery({
    queryKey: ["summary", "mag7"],
    queryFn: fetchMag7Summary,
  });

  const inflationQuery = useQuery({
    queryKey: ["summary", "inflation"],
    queryFn: fetchInflationSummary,
  });

  const inflationIds = useMemo(
    () => (inflationQuery.data?.items ?? []).map((item) => item.id),
    [inflationQuery.data?.items],
  );

  const inflationSeriesQuery = useQuery({
    queryKey: ["inflation-series", inflationIds],
    enabled: inflationIds.length > 0,
    queryFn: async () => {
      const ranges: Array<"3m" | "6m" | "1y"> = ["1y", "6m", "3m"];
      const results: Record<"3m" | "6m" | "1y", Record<string, SparkPoint[]>> = {
        "3m": {},
        "6m": {},
        "1y": {},
      };

      await Promise.all(
        ranges.flatMap((range) =>
          inflationIds.map(async (id) => {
            const series = await fetchInflationSeries(id, range);
            results[range][id] = series.points;
          }),
        ),
      );

      return results;
    },
  });

  const warnings: string[] = [];
  if (commoditiesQuery.isError) warnings.push("Kunde inte hamta ravaror just nu.");
  if (mag7Query.isError) warnings.push("Kunde inte hamta Mag 7 just nu.");
  if (inflationQuery.isError) warnings.push("Kunde inte hamta inflation just nu.");
  if (inflationSeriesQuery.isError) warnings.push("Vissa inflationsserier kunde inte hamtas.");

  return (
    <DashboardView
      commodities={commoditiesQuery.data ?? null}
      mag7={mag7Query.data ?? null}
      inflation={inflationQuery.data ?? null}
      inflationSeriesByRange={
        inflationSeriesQuery.data ?? {
          "3m": {},
          "6m": {},
          "1y": {},
        }
      }
      warnings={warnings}
    />
  );
}
