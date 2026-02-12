"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import type { SparkPoint, SummaryItem, SummaryResponse } from "@/lib/api";

const tabs = [
  { id: "commodities", label: "Råvaror" },
  { id: "mag7", label: "Mag 7" },
  { id: "inflation", label: "Inflation" },
] as const;

type TabId = (typeof tabs)[number]["id"];

type DashboardViewProps = {
  commodities: SummaryResponse | null;
  mag7: SummaryResponse | null;
  inflation: SummaryResponse | null;
  inflationSeriesByRange: Record<"3m" | "6m" | "1y", Record<string, SparkPoint[]>>;
  warnings: string[];
};

type ModuleStatus = "fresh" | "partial" | "stale" | "offline";
type InflationRange = "3m" | "6m" | "1y";
type Theme = "light" | "dark";

const inflationRanges: Array<{ id: InflationRange; label: string }> = [
  { id: "1y", label: "12 man" },
  { id: "6m", label: "6 man" },
  { id: "3m", label: "3 man" },
];

const EMPTY_ITEMS: SummaryItem[] = [];

function formatValue(value: number | null, precision = 2): string {
  if (value === null) return "--";
  return value.toFixed(precision);
}

function formatPercent(value: number | null): string {
  if (value === null) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatSignedValue(value: number | null, precision = 2): string {
  if (value === null) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(precision)}`;
}

function formatAbsAndPercent(dayAbs: number | null, dayPct: number | null): string {
  if (dayAbs === null && dayPct === null) return "--";
  if (dayAbs === null) return formatPercent(dayPct);
  if (dayPct === null) return formatSignedValue(dayAbs);
  return `${formatSignedValue(dayAbs)} (${formatPercent(dayPct)})`;
}

function changeToneClass(value: number | null): string {
  if (value === null) return "change-neutral";
  if (value > 0) return "change-positive";
  if (value < 0) return "change-negative";
  return "change-neutral";
}

function formatUpdateTime(timestamp: string | undefined): string {
  if (!timestamp) return "--:--";
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "--:--";
  return date.toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" });
}

function formatTimestampCell(timestamp: string | null | undefined): string {
  if (!timestamp) return "--";
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "--";
  return date.toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" });
}

function getModuleStatus(items: SummaryItem[]): ModuleStatus {
  if (items.length === 0) return "offline";
  const staleCount = items.filter((item) => item.is_stale).length;
  if (staleCount === 0) return "fresh";
  if (staleCount === items.length) return "stale";
  return "partial";
}

function statusLabel(status: ModuleStatus): string {
  if (status === "fresh") return "Fresh";
  if (status === "partial") return "Partial";
  if (status === "stale") return "Stale";
  return "Offline";
}

type Mag7SortField = "name" | "last" | "day_pct" | "w1_pct" | "ytd_pct" | "y1_pct";

function sortMag7Items(items: SummaryItem[], field: Mag7SortField, direction: "asc" | "desc"): SummaryItem[] {
  const sorted = [...items];
  sorted.sort((a, b) => {
    if (field === "name") {
      return direction === "desc"
        ? b.name.localeCompare(a.name, "sv")
        : a.name.localeCompare(b.name, "sv");
    }

    const av = a[field] ?? Number.NEGATIVE_INFINITY;
    const bv = b[field] ?? Number.NEGATIVE_INFINITY;
    return direction === "desc" ? bv - av : av - bv;
  });
  return sorted;
}

function topMag7Cards(items: SummaryItem[]): SummaryItem[] {
  const rank: Record<string, number> = {
    msft: 1,
    nvda: 2,
    aapl: 3,
    amzn: 4,
    googl: 5,
    meta: 6,
    tsla: 7,
  };

  return [...items]
    .sort((a, b) => {
      const ra = rank[a.id] ?? Number.MAX_SAFE_INTEGER;
      const rb = rank[b.id] ?? Number.MAX_SAFE_INTEGER;
      return ra - rb;
    })
    .slice(0, 6);
}

function sortCommoditiesForDisplay(items: SummaryItem[]): SummaryItem[] {
  const rank: Record<string, number> = {
    gold: 1,
    silver: 2,
    copper: 3,
    zinc: 4,
    brent: 5,
    wti: 6,
  };

  return [...items].sort((a, b) => {
    const ra = rank[a.id] ?? Number.MAX_SAFE_INTEGER;
    const rb = rank[b.id] ?? Number.MAX_SAFE_INTEGER;
    if (ra !== rb) return ra - rb;
    return a.name.localeCompare(b.name, "sv");
  });
}

function formatXAxisTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "--";
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  return `${date.getUTCFullYear()}-${month}`;
}

function Sparkline({
  points,
  heightClass = "h-20",
  showXAxis = false,
}: {
  points: { t: string; v: number }[];
  heightClass?: string;
  showXAxis?: boolean;
}) {
  if (points.length < 2) {
    return <div className={`mt-4 ${heightClass} rounded-xl chart-empty`} />;
  }

  const values = points.map((p) => p.v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const chartTop = 8;
  const chartBottom = showXAxis ? 78 : 100;
  const chartHeight = chartBottom - chartTop;
  const path = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * 100;
      const y = chartBottom - ((point.v - min) / range) * chartHeight;
      return `${x},${y}`;
    })
    .join(" ");

  const tickIndexes = Array.from(new Set([0, Math.floor((points.length - 1) / 2), points.length - 1]));
  const tickLabels = tickIndexes.map((tickIndex) => formatXAxisTime(points[tickIndex]?.t ?? ""));

  return (
    <div className="mt-4">
      <svg className={`${heightClass} w-full`} viewBox="0 0 100 100" preserveAspectRatio="none">
        <polyline fill="none" stroke="var(--chart-primary)" strokeWidth="2" points={path} />
        {showXAxis ? (
          <>
            <line x1="0" y1={chartBottom} x2="100" y2={chartBottom} stroke="var(--chart-grid)" strokeWidth="0.6" />
            {tickIndexes.map((tickIndex) => {
              const x = points.length === 1 ? 50 : (tickIndex / (points.length - 1)) * 100;
              return <line key={`spark-tick-${tickIndex}`} x1={x} y1={chartBottom} x2={x} y2={chartBottom + 2} stroke="var(--chart-axis)" strokeWidth="0.5" />;
            })}
          </>
        ) : null}
      </svg>
      {showXAxis ? (
        <div className="axis-text mt-1 flex items-center justify-between px-1 text-sm font-semibold leading-none">
          <span>{tickLabels[0]}</span>
          <span>{tickLabels[1]}</span>
          <span>{tickLabels[2]}</span>
        </div>
      ) : null}
    </div>
  );
}

function InflationComparisonChart({
  swedenPoints,
  usaPoints,
}: {
  swedenPoints: SparkPoint[];
  usaPoints: SparkPoint[];
}) {
  const buildPath = (points: SparkPoint[], min: number, range: number) =>
    points
      .map((point, index) => {
        const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100;
        const y = 100 - ((point.v - min) / range) * 100;
        return `${x},${y}`;
      })
      .join(" ");

  const values = [...swedenPoints, ...usaPoints].map((point) => point.v);
  if (values.length < 2) {
    return <div className="chart-empty mt-4 h-64 rounded-xl" />;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const swedenPath = buildPath(swedenPoints, min, range);
  const usaPath = buildPath(usaPoints, min, range);
  const basePoints = swedenPoints.length >= usaPoints.length ? swedenPoints : usaPoints;
  const tickIndexes = Array.from(new Set([0, Math.floor((basePoints.length - 1) / 2), basePoints.length - 1]));
  const tickLabels = tickIndexes.map((tickIndex) => formatXAxisTime(basePoints[tickIndex]?.t ?? ""));

  return (
    <div className="mt-4">
      <svg className="h-64 w-full" viewBox="0 0 100 100" preserveAspectRatio="none" data-testid="inflation-comparison-chart">
        <polyline fill="none" stroke="var(--chart-primary)" strokeWidth="2.6" points={swedenPath} data-testid="inflation-line-sweden" />
        <polyline fill="none" stroke="var(--chart-secondary)" strokeWidth="2.6" points={usaPath} data-testid="inflation-line-usa" />
      </svg>
      <div className="axis-text mt-1 flex items-center justify-between px-1 text-sm font-semibold leading-none">
        <span>{tickLabels[0]}</span>
        <span>{tickLabels[1]}</span>
        <span>{tickLabels[2]}</span>
      </div>
    </div>
  );
}

function inflationRole(item: SummaryItem): string {
  return item.id.includes("se") ? "Sverige" : "USA";
}

function sourceDisplayName(source: string): string {
  if (source === "yahoo_finance") return "Yahoo";
  if (source === "fred") return "FRED";
  return source;
}

export function DashboardView({ commodities, mag7, inflation, inflationSeriesByRange, warnings }: DashboardViewProps) {
  const router = useRouter();
  const [theme, setTheme] = useState<Theme>("light");
  const [activeTab, setActiveTab] = useState<TabId>("commodities");
  const [mag7SortField, setMag7SortField] = useState<Mag7SortField>("ytd_pct");
  const [mag7SortDirection, setMag7SortDirection] = useState<"asc" | "desc">("desc");
  const [selectedMarketChartId, setSelectedMarketChartId] = useState<string | null>(null);
  const [inflationRange, setInflationRange] = useState<InflationRange>("1y");

  useEffect(() => {
    const timer = setInterval(() => {
      router.refresh();
    }, 60_000);
    return () => clearInterval(timer);
  }, [router]);

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("dashboard-theme");
    if (savedTheme === "light" || savedTheme === "dark") {
      setTheme(savedTheme);
      return;
    }
    if (typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      setTheme("dark");
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem("dashboard-theme", theme);
  }, [theme]);

  const commodityItems = commodities?.items ?? EMPTY_ITEMS;
  const mag7Items = mag7?.items ?? EMPTY_ITEMS;
  const inflationItems = inflation?.items ?? EMPTY_ITEMS;

  const commodityStatus = getModuleStatus(commodityItems);
  const mag7Status = getModuleStatus(mag7Items);
  const inflationStatus = getModuleStatus(inflationItems);
  const latestUpdate = commodities?.meta.fetched_at ?? mag7?.meta.fetched_at ?? inflation?.meta.fetched_at;
  const sourceNames = Array.from(
    new Set(
      [commodities?.meta.source, mag7?.meta.source, inflation?.meta.source]
        .filter((source): source is string => Boolean(source))
        .map(sourceDisplayName),
    ),
  );
  const sourceLabel = sourceNames.length > 0 ? sourceNames.join(" + ") : "--";

  const filteredCommodityItems = sortCommoditiesForDisplay(commodityItems);
  const filteredMag7Items = sortMag7Items(
    mag7Items,
    mag7SortField,
    mag7SortDirection,
  );

  const swedenInflationItem = inflationItems.find((item) => item.id.includes("se")) ?? null;
  const usaInflationItem = inflationItems.find((item) => item.id.includes("us")) ?? null;
  const selectedRangeSeries = inflationSeriesByRange[inflationRange];
  const swedenInflationPoints = swedenInflationItem
    ? selectedRangeSeries[swedenInflationItem.id] ?? swedenInflationItem.sparkline
    : [];
  const usaInflationPoints = usaInflationItem ? selectedRangeSeries[usaInflationItem.id] ?? usaInflationItem.sparkline : [];

  const showMarketSections = activeTab === "commodities" || activeTab === "mag7";
  const showMag7Table = activeTab === "mag7";
  const showInflation = activeTab === "inflation";

  const kpiItems = showMag7Table ? topMag7Cards(filteredMag7Items) : filteredCommodityItems;
  const kpiTitle = showMag7Table ? "Magnificent 7" : "Råvaror";
  const kpiEmptyText = showMag7Table ? "Ingen Mag 7-data tillganglig." : "Ingen ravarudata tillganglig.";
  const tableItems = showMag7Table ? filteredMag7Items : filteredCommodityItems;
  const tableLabel = showMag7Table ? "MAG 7" : "RAVAROR";
  const tableFirstColumn = showMag7Table ? "Bolag" : "Ravara / Enhet";
  const tableEmptyText = showMag7Table ? "Data kunde inte laddas for Mag 7." : "Data kunde inte laddas for ravaror.";
  const tableGridClass = showMag7Table ? "grid-cols-7" : "grid-cols-8";
  const selectedMarketChart = kpiItems.find((item) => item.id === selectedMarketChartId) ?? kpiItems[0] ?? null;

  useEffect(() => {
    if (kpiItems.length === 0) {
      setSelectedMarketChartId(null);
      return;
    }
    setSelectedMarketChartId((current) => {
      if (current && kpiItems.some((item) => item.id === current)) return current;
      return kpiItems[0].id;
    });
  }, [activeTab, kpiItems]);

  return (
    <main className="container-shell">
      <header className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <h1 className="section-title text-4xl font-semibold">Marknadsöversikt</h1>
          <p className="text-muted text-sm">
            Snabba KPI:er, tabeller och sparklines med flera datakällor (MVP).
          </p>
        </div>
        <div className="card-surface flex flex-col gap-4 p-4 md:flex-row md:items-center">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-[#f28f3b] text-center text-xl font-semibold leading-10 text-white">
              E
            </div>
            <div>
              <div className="text-sm font-semibold">Ekonomi Dashboard</div>
              <div className="text-muted text-xs">Datakallor: {sourceLabel}</div>
            </div>
          </div>
          <div className="text-muted flex items-center gap-2 text-xs md:ml-auto">
            <span>Senast lyckade uppdatering</span>
            <span className="text-strong font-semibold">{formatUpdateTime(latestUpdate)}</span>
          </div>
          <div className="md:ml-2">
            <button
              type="button"
              className="theme-toggle"
              data-theme={theme}
              onClick={() => setTheme((current) => (current === "light" ? "dark" : "light"))}
            >
              {theme === "light" ? "Morkt lage" : "Ljust lage"}
            </button>
          </div>
        </div>
      </header>

      {warnings.length > 0 ? (
        <section className="warning-surface mt-6 rounded-xl border p-3 text-sm">
          {warnings.join(" ")}
        </section>
      ) : null}

      <section className="mt-6 card-surface p-4">
        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className="tab-pill"
              data-active={tab.id === activeTab}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="badge">Råvaror: {statusLabel(commodityStatus)}</span>
          <span className="badge">Mag 7: {statusLabel(mag7Status)}</span>
          <span className="badge">Inflation: {statusLabel(inflationStatus)}</span>
        </div>
      </section>

      {showMarketSections ? (
        <>
          <section className="mt-8">
            <div className="flex items-center justify-between">
              <h2 className="section-title text-2xl">{kpiTitle}</h2>
            </div>
            <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {kpiItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  data-testid={`kpi-card-${item.id}`}
                  className="card-surface commodity-card kpi-card-80 p-4 text-left transition-transform hover:-translate-y-0.5"
                  data-active={selectedMarketChart?.id === item.id}
                  onClick={() => setSelectedMarketChartId(item.id)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold">{item.name}</div>
                      <div className="text-xs kpi-subtle">{item.unit ?? "--"}</div>
                    </div>
                    <span className="badge">{item.is_stale ? "Stale" : "Live"}</span>
                  </div>
                  <div className="mt-5 kpi-value">{formatValue(item.last)}</div>
                  <div className={`mt-2 text-sm kpi-change ${changeToneClass(item.day_pct)}`}>{formatPercent(item.day_pct)}</div>
                  <Sparkline points={item.sparkline} heightClass="h-16" />
                </button>
              ))}
              {kpiItems.length === 0 ? (
                <div className="card-surface text-muted p-5 text-sm">{kpiEmptyText}</div>
              ) : null}
            </div>
          </section>

          <section className="mt-8">
            <div className="flex items-center justify-between">
              <h2 className="section-title text-2xl">Vald graf</h2>
              <span className="kpi-subtle">Klicka pa en ruta for att byta</span>
            </div>
            {selectedMarketChart ? (
              <article className="card-surface mt-4 p-6" data-testid="selected-market-chart-panel">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">{selectedMarketChart.name}</h3>
                    <p className="text-muted text-xs">
                      {selectedMarketChart.unit ?? "--"} • {selectedMarketChart.price_type ?? "--"}
                    </p>
                  </div>
                  <span className="badge">{selectedMarketChart.is_stale ? "Stale" : "Live"}</span>
                </div>
                <div className="text-muted mt-4 text-sm">
                  Senast: {formatValue(selectedMarketChart.last)} (
                  <span className={changeToneClass(selectedMarketChart.day_pct)}>{formatPercent(selectedMarketChart.day_pct)}</span>)
                </div>
                <Sparkline points={selectedMarketChart.sparkline} heightClass="h-56" showXAxis />
              </article>
            ) : (
              <div className="card-surface text-muted mt-4 p-5 text-sm">Ingen grafdata tillgänglig.</div>
            )}
          </section>
        </>
      ) : null}

      {showMarketSections ? (
        <>
          <section className="mt-10">
            <div className="flex items-center justify-between">
              <h2 className="section-title text-2xl">Tabell</h2>
              <div className="flex items-center gap-2">
                <span className="kpi-subtle">{tableLabel}</span>
                {showMag7Table ? (
                  <>
                    <label className="sr-only" htmlFor="mag7-sort-field">Sortera Mag7 efter</label>
                    <select
                      id="mag7-sort-field"
                      className="select-control rounded-full px-3 py-1 text-xs"
                      value={mag7SortField}
                      onChange={(event) => setMag7SortField(event.target.value as Mag7SortField)}
                    >
                      <option value="ytd_pct">I ar</option>
                      <option value="w1_pct">1V</option>
                      <option value="y1_pct">1 ar</option>
                      <option value="day_pct">Dags%</option>
                      <option value="last">Senast</option>
                      <option value="name">Namn</option>
                    </select>
                    <button
                      className="tab-pill"
                      data-active="false"
                      onClick={() => setMag7SortDirection((current) => (current === "desc" ? "asc" : "desc"))}
                    >
                      {mag7SortDirection === "desc" ? "Fallande" : "Stigande"}
                    </button>
                  </>
                ) : null}
              </div>
            </div>
            <div className="mt-4 table-shell">
              <div className={`table-head table-head-text grid ${tableGridClass} gap-2 px-4 py-3 text-xs font-semibold uppercase tracking-wide`}>
                <div>{tableFirstColumn}</div>
                <div>Senast</div>
                <div>+/-</div>
                <div>1V</div>
                <div>I ar</div>
                <div>1 ar</div>
                {!showMag7Table ? <div>Tid</div> : null}
                <div>Pristyp</div>
              </div>
              {tableItems.length > 0 ? (
                tableItems.map((item) => (
                  <div
                    key={`table-${item.id}`}
                    data-testid={`table-row-${item.id}`}
                    className={`grid ${tableGridClass} gap-2 border-t border-[var(--border)] px-4 py-3 text-sm`}
                  >
                    <div>
                      <div>{item.name}</div>
                      {!showMag7Table ? <div className="text-muted text-xs">{item.unit ?? "--"}</div> : null}
                    </div>
                    <div>{formatValue(item.last)}</div>
                    <div className={changeToneClass(item.day_pct)}>{formatAbsAndPercent(item.day_abs, item.day_pct)}</div>
                    <div className={changeToneClass(item.w1_pct)}>{formatPercent(item.w1_pct)}</div>
                    <div className={changeToneClass(item.ytd_pct)}>{formatPercent(item.ytd_pct)}</div>
                    <div className={changeToneClass(item.y1_pct)}>{formatPercent(item.y1_pct)}</div>
                    {!showMag7Table ? <div>{formatTimestampCell(item.timestamp_local)}</div> : null}
                    <div>{item.price_type ?? "--"}</div>
                  </div>
                ))
              ) : (
                <div className="text-muted px-4 py-6 text-sm">{tableEmptyText}</div>
              )}
            </div>
          </section>
        </>
      ) : null}

      {showInflation ? (
        <section className="mt-8">
          <div className="flex items-center justify-between">
            <h2 className="section-title text-2xl">Inflation: Sverige & USA</h2>
            <span className="kpi-subtle">Gemensam graf</span>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {inflationRanges.map((rangeOption) => (
              <button
                key={`inflation-range-${rangeOption.id}`}
                className="tab-pill"
                data-active={inflationRange === rangeOption.id}
                onClick={() => setInflationRange(rangeOption.id)}
              >
                {rangeOption.label}
              </button>
            ))}
          </div>
          {swedenInflationItem && usaInflationItem ? (
            <article className="card-surface mt-4 p-5" data-testid="inflation-shared-chart-panel">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-muted text-sm">
                  Senast: Sverige {formatValue(swedenInflationItem.last)} / USA {formatValue(usaInflationItem.last)}
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="inline-flex items-center gap-1">
                    <span className="legend-dot-sweden h-2 w-2 rounded-full" />
                    Sverige
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="legend-dot-usa h-2 w-2 rounded-full" />
                    USA
                  </span>
                </div>
              </div>
              <InflationComparisonChart swedenPoints={swedenInflationPoints} usaPoints={usaInflationPoints} />
            </article>
          ) : (
            <div className="card-surface text-muted mt-4 p-5 text-sm">Ingen inflationsdata tillgänglig.</div>
          )}
        </section>
      ) : null}
    </main>
  );
}
