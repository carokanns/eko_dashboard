import { fetchCommoditiesSummary, fetchMag7Summary } from "@/lib/api";

import { DashboardView } from "./dashboard-view";

export default async function Home() {
  const warnings: string[] = [];

  const [commoditiesResult, mag7Result] = await Promise.allSettled([
    fetchCommoditiesSummary(),
    fetchMag7Summary(),
  ]);

  const commodities = commoditiesResult.status === "fulfilled" ? commoditiesResult.value : null;
  if (commoditiesResult.status === "rejected") {
    warnings.push("Kunde inte hamta ravaror just nu.");
  }

  const mag7 = mag7Result.status === "fulfilled" ? mag7Result.value : null;
  if (mag7Result.status === "rejected") {
    warnings.push("Kunde inte hamta Mag 7 just nu.");
  }

  return <DashboardView commodities={commodities} mag7={mag7} warnings={warnings} />;
}
