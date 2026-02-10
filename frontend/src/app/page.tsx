import { fetchCommoditiesSummary, fetchInflationSeries, fetchInflationSummary, fetchMag7Summary, type SparkPoint } from "@/lib/api";

import { DashboardView } from "./dashboard-view";

export default async function Home() {
  const warnings: string[] = [];
  const inflationSeriesByRange: Record<"3m" | "6m" | "1y", Record<string, SparkPoint[]>> = {
    "3m": {},
    "6m": {},
    "1y": {},
  };

  const [commoditiesResult, mag7Result, inflationResult] = await Promise.allSettled([
    fetchCommoditiesSummary(),
    fetchMag7Summary(),
    fetchInflationSummary(),
  ]);

  const commodities = commoditiesResult.status === "fulfilled" ? commoditiesResult.value : null;
  if (commoditiesResult.status === "rejected") {
    warnings.push("Kunde inte hamta ravaror just nu.");
  }

  const mag7 = mag7Result.status === "fulfilled" ? mag7Result.value : null;
  if (mag7Result.status === "rejected") {
    warnings.push("Kunde inte hamta Mag 7 just nu.");
  }

  const inflation = inflationResult.status === "fulfilled" ? inflationResult.value : null;
  if (inflationResult.status === "rejected") {
    warnings.push("Kunde inte hamta inflation just nu.");
  }

  if (inflation) {
    const ranges: Array<"3m" | "6m" | "1y"> = ["3m", "6m", "1y"];
    const ids = inflation.items.map((item) => item.id);
    const requests = ranges.flatMap((range) => ids.map((id) => ({ range, id })));
    const results = await Promise.allSettled(
      requests.map(({ range, id }) => fetchInflationSeries(id, range)),
    );

    let hasErrors = false;
    results.forEach((result, index) => {
      const { range, id } = requests[index];
      if (result.status === "fulfilled") {
        inflationSeriesByRange[range][id] = result.value.points;
      } else {
        hasErrors = true;
      }
    });

    if (hasErrors) {
      warnings.push("Vissa inflationsserier kunde inte hamtas.");
    }
  }

  return (
    <DashboardView
      commodities={commodities}
      mag7={mag7}
      inflation={inflation}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={warnings}
    />
  );
}
