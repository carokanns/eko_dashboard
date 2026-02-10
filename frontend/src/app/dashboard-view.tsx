"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import type { SummaryItem, SummaryResponse } from "@/lib/api";

const tabs = [
  { id: "commodities", label: "Råvaror" },
  { id: "mag7", label: "Mag 7" },
  { id: "inflation", label: "Inflation" },
  { id: "charts", label: "Grafer" },
] as const;

type TabId = (typeof tabs)[number]["id"];

type DashboardViewProps = {
  commodities: SummaryResponse | null;
  mag7: SummaryResponse | null;
  inflation: SummaryResponse | null;
  warnings: string[];
};

type ModuleStatus = "fresh" | "partial" | "stale" | "offline";

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

function formatUpdateTime(timestamp: string | undefined): string {
  if (!timestamp) return "--:--";
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "--:--";
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

function matchesSearch(item: SummaryItem, query: string): boolean {
  const trimmed = query.trim().toLowerCase();
  if (!trimmed) return true;
  return item.name.toLowerCase().includes(trimmed) || item.id.toLowerCase().includes(trimmed);
}

function sortMag7ByYtd(items: SummaryItem[], direction: "asc" | "desc"): SummaryItem[] {
  const sorted = [...items];
  sorted.sort((a, b) => {
    const ay = a.ytd_pct ?? Number.NEGATIVE_INFINITY;
    const by = b.ytd_pct ?? Number.NEGATIVE_INFINITY;
    return direction === "desc" ? by - ay : ay - by;
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

function Sparkline({ points }: { points: { t: string; v: number }[] }) {
  if (points.length < 2) {
    return <div className="mt-4 h-20 rounded-xl bg-[linear-gradient(90deg,#1b2a41,transparent)] opacity-20" />;
  }

  const values = points.map((p) => p.v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const path = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * 100;
      const y = 100 - ((point.v - min) / range) * 100;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg className="mt-4 h-20 w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
      <polyline fill="none" stroke="#1b2a41" strokeWidth="2" points={path} />
    </svg>
  );
}

function inflationRole(item: SummaryItem): string {
  return item.id.includes("se") ? "Sverige" : "USA";
}

export function DashboardView({ commodities, mag7, inflation, warnings }: DashboardViewProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabId>("commodities");
  const [searchQuery, setSearchQuery] = useState("");
  const [mag7SortDirection, setMag7SortDirection] = useState<"asc" | "desc">("desc");
  const [selectedChartId, setSelectedChartId] = useState<string | null>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      router.refresh();
    }, 60_000);
    return () => clearInterval(timer);
  }, [router]);

  const commodityItems = commodities?.items ?? EMPTY_ITEMS;
  const mag7Items = mag7?.items ?? EMPTY_ITEMS;
  const inflationItems = inflation?.items ?? EMPTY_ITEMS;

  const commodityStatus = getModuleStatus(commodityItems);
  const mag7Status = getModuleStatus(mag7Items);
  const inflationStatus = getModuleStatus(inflationItems);
  const dashboardStatus: ModuleStatus = warnings.length > 0
    ? "partial"
    : [commodityStatus, mag7Status, inflationStatus].every((status) => status === "offline")
      ? "offline"
      : [commodityStatus, mag7Status, inflationStatus].every((status) => status === "fresh")
        ? "fresh"
        : [commodityStatus, mag7Status, inflationStatus].every((status) => status === "stale")
          ? "stale"
          : "partial";

  const latestUpdate = commodities?.meta.fetched_at ?? mag7?.meta.fetched_at ?? inflation?.meta.fetched_at;

  const filteredCommodityItems = commodityItems.filter((item) => matchesSearch(item, searchQuery));
  const filteredMag7Items = sortMag7ByYtd(
    mag7Items.filter((item) => matchesSearch(item, searchQuery)),
    mag7SortDirection,
  );

  const filteredInflationItems = inflationItems.filter((item) => matchesSearch(item, searchQuery));

  const selectedChart =
    filteredInflationItems.find((item) => item.id === selectedChartId) ?? filteredInflationItems[0] ?? null;

  const showMarketSections = activeTab === "commodities" || activeTab === "mag7";
  const showInflation = activeTab === "inflation";
  const showCharts = activeTab === "charts";

  const kpiItems = activeTab === "mag7" ? topMag7Cards(filteredMag7Items) : filteredCommodityItems;
  const kpiTitle = activeTab === "mag7" ? "Mag 7" : "Ravaror";
  const kpiEmptyText =
    activeTab === "mag7" ? "Ingen Mag 7-data tillganglig." : "Ingen ravarudata tillganglig.";
  const tableItems = activeTab === "mag7" ? filteredMag7Items : filteredCommodityItems;
  const tableLabel = activeTab === "mag7" ? "MAG 7" : "RAVAROR";
  const tableFirstColumn = activeTab === "mag7" ? "Bolag" : "Ravara";
  const tableEmptyText =
    activeTab === "mag7" ? "Data kunde inte laddas for Mag 7." : "Data kunde inte laddas for ravaror.";

  return (
    <main className="container-shell">
      <header className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="badge w-fit">Finansiell Dashboard</div>
          <h1 className="section-title text-4xl font-semibold">Marknadsoversikt</h1>
          <p className="text-sm text-[#5a524a]">
            Snabba KPI:er, tabeller och sparklines med Yahoo Finance (MVP).
          </p>
        </div>
        <div className="card-surface flex flex-col gap-4 p-4 md:flex-row md:items-center">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-[#f28f3b] text-center text-xl font-semibold leading-10 text-white">
              E
            </div>
            <div>
              <div className="text-sm font-semibold">Ekonomi Dashboard</div>
              <div className="text-xs text-[#6b625a]">Datakalla: Yahoo</div>
            </div>
          </div>
          <div className="flex-1">
            <input
              className="w-full rounded-full border border-[var(--border)] bg-white px-4 py-2 text-sm"
              placeholder={`Sok i ${activeTab === "mag7" ? "Mag 7" : activeTab === "inflation" || activeTab === "charts" ? "inflation" : "ravaror"}`}
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>
          <div className="flex items-center gap-2 text-xs text-[#6b625a]">
            <span>Senast lyckade uppdatering</span>
            <span className="font-semibold text-[#2f2720]">{formatUpdateTime(latestUpdate)}</span>
            <span className="badge">{statusLabel(dashboardStatus)}</span>
          </div>
        </div>
      </header>

      {warnings.length > 0 ? (
        <section className="mt-6 rounded-xl border border-[#d4b8ab] bg-[#fff4ef] p-3 text-sm text-[#7b3f2e]">
          {warnings.join(" ")}
        </section>
      ) : null}

      <section className="mt-6 grid gap-3 md:grid-cols-4">
        <div className="card-surface p-3 text-sm">
          <div className="kpi-subtle">Dashboard status</div>
          <div className="mt-1 font-semibold">{statusLabel(dashboardStatus)}</div>
        </div>
        <div className="card-surface p-3 text-sm">
          <div className="kpi-subtle">Råvaror</div>
          <div className="mt-1 font-semibold">{statusLabel(commodityStatus)}</div>
        </div>
        <div className="card-surface p-3 text-sm">
          <div className="kpi-subtle">Mag 7</div>
          <div className="mt-1 font-semibold">{statusLabel(mag7Status)}</div>
        </div>
        <div className="card-surface p-3 text-sm">
          <div className="kpi-subtle">Inflation</div>
          <div className="mt-1 font-semibold">{statusLabel(inflationStatus)}</div>
        </div>
      </section>

      <section className="mt-10 card-surface p-4">
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
      </section>

      {showMarketSections ? (
        <>
          <section className="mt-8">
            <div className="flex items-center justify-between">
              <h2 className="section-title text-2xl">{kpiTitle}</h2>
              <span className="kpi-subtle">KPI-kort</span>
            </div>
            <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {kpiItems.map((item) => (
                <article key={item.id} data-testid={`kpi-card-${item.id}`} className="card-surface commodity-card p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold">{item.name}</div>
                      <div className="text-xs kpi-subtle">{item.unit ?? "--"}</div>
                    </div>
                    <span className="badge">{item.is_stale ? "Stale" : "Live"}</span>
                  </div>
                  <div className="mt-6 kpi-value">{formatValue(item.last)}</div>
                  <div className="mt-2 text-sm kpi-change">{formatPercent(item.day_pct)}</div>
                  <Sparkline points={item.sparkline} />
                </article>
              ))}
              {kpiItems.length === 0 ? (
                <div className="card-surface p-5 text-sm text-[#6b625a]">{kpiEmptyText}</div>
              ) : null}
            </div>
          </section>

          <section className="mt-10">
            <div className="flex items-center justify-between">
              <h2 className="section-title text-2xl">Tabell</h2>
              <span className="kpi-subtle">{tableLabel}</span>
            </div>
            <div className="mt-4 table-shell">
              <div className="table-head grid grid-cols-7 gap-2 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[#534a42]">
                <div>{tableFirstColumn}</div>
                <div>Senast</div>
                <div>+/-</div>
                <div>1V</div>
                <div>I ar</div>
                <div>1 ar</div>
                <div>Pristyp</div>
              </div>
              {tableItems.length > 0 ? (
                tableItems.map((item) => (
                  <div
                    key={`table-${item.id}`}
                    data-testid={`table-row-${item.id}`}
                    className="grid grid-cols-7 gap-2 border-t border-[var(--border)] px-4 py-3 text-sm"
                  >
                    <div>{item.name}</div>
                    <div>{formatValue(item.last)}</div>
                    <div>{formatPercent(item.day_pct)}</div>
                    <div>{formatPercent(item.w1_pct)}</div>
                    <div>{formatPercent(item.ytd_pct)}</div>
                    <div>{formatPercent(item.y1_pct)}</div>
                    <div>{item.price_type ?? "--"}</div>
                  </div>
                ))
              ) : (
                <div className="px-4 py-6 text-sm text-[#6b625a]">{tableEmptyText}</div>
              )}
            </div>
          </section>
        </>
      ) : null}

      {showInflation ? (
        <section className="mt-8">
          <div className="flex items-center justify-between">
            <h2 className="section-title text-2xl">Inflation: Sverige & USA</h2>
            <span className="kpi-subtle">Samma yta som Råvaror/Mag 7</span>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {filteredInflationItems.map((item) => (
              <article key={item.id} data-testid={`inflation-card-${item.id}`} className="card-surface p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold">{inflationRole(item)}</div>
                    <div className="text-xs kpi-subtle">{item.name}</div>
                  </div>
                  <span className="badge">{item.is_stale ? "Stale" : "Live"}</span>
                </div>
                <div className="mt-4 text-3xl font-semibold">{formatValue(item.last)}</div>
                <div className="mt-1 text-sm text-[#6b625a]">{formatPercent(item.y1_pct)} senaste 12 månaderna</div>
                <Sparkline points={item.sparkline} />
              </article>
            ))}
          </div>
          {filteredInflationItems.length === 0 ? (
            <div className="card-surface mt-4 p-5 text-sm text-[#6b625a]">Ingen inflationsdata tillgänglig.</div>
          ) : null}
        </section>
      ) : null}

      {showCharts ? (
        <section className="mt-8">
          <div className="flex items-center justify-between">
            <h2 className="section-title text-2xl">Grafer</h2>
            <span className="kpi-subtle">Välj graf i rutorna</span>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {filteredInflationItems.map((item) => (
              <button
                key={`chart-selector-${item.id}`}
                className="tab-pill"
                data-active={selectedChart?.id === item.id}
                onClick={() => setSelectedChartId(item.id)}
              >
                {inflationRole(item)}
              </button>
            ))}
          </div>
          {selectedChart ? (
            <article className="card-surface mt-4 p-6" data-testid="selected-chart-panel">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold">{inflationRole(selectedChart)} inflation</h3>
                  <p className="text-xs text-[#6b625a]">{selectedChart.name}</p>
                </div>
                <span className="badge">{selectedChart.is_stale ? "Stale" : "Live"}</span>
              </div>
              <div className="mt-4 text-sm text-[#6b625a]">Senast: {formatValue(selectedChart.last)} ({formatPercent(selectedChart.day_pct)})</div>
              <Sparkline points={selectedChart.sparkline} />
            </article>
          ) : (
            <div className="card-surface mt-4 p-5 text-sm text-[#6b625a]">Ingen grafdata tillgänglig.</div>
          )}
        </section>
      ) : null}

      <section className="mt-10 card-surface p-6">
        <div className="flex items-center justify-between">
          <h2 className="section-title text-2xl">Mag 7</h2>
          <button
            className="tab-pill"
            data-active="false"
            onClick={() => setMag7SortDirection((current) => (current === "desc" ? "asc" : "desc"))}
          >
            Sortera YTD {mag7SortDirection === "desc" ? "↓" : "↑"}
          </button>
        </div>
        {filteredMag7Items.length > 0 ? (
          <div className="mt-4 space-y-3">
            {filteredMag7Items.map((item) => (
              <div
                key={`mag7-${item.id}`}
                data-testid={`mag7-row-${item.id}`}
                className="flex items-center justify-between border-b border-[var(--border)] pb-3 text-sm"
              >
                <span>
                  {item.name} ({item.id.toUpperCase()})
                </span>
                <span>
                  {formatValue(item.last)} / {formatPercent(item.ytd_pct)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-[#6b625a]">Mag 7-data kunde inte laddas.</p>
        )}
        <p className="mt-3 text-xs text-[#6b625a]">Auto-refresh: 60 sekunder.</p>
      </section>
    </main>
  );
}
