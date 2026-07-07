"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { MarketRange, PortfolioAccountValue, PortfolioHolding, PortfolioSummaryResponse, SparkPoint, SummaryItem, SummaryResponse } from "@/lib/api";
import {
  changeToneClass,
  formatAbsAndPercent,
  formatLevelPrice,
  formatPercent,
  formatSek,
  formatSekToThbRate,
  formatThb,
  formatTimestampCell,
  formatUpdateTime,
  formatValue,
  sourceDisplayName,
} from "./dashboard-format";

const tabs = [
  { id: "commodities", label: "Råvaror" },
  { id: "mag7", label: "Mag 7" },
  { id: "indexes", label: "Index" },
  { id: "inflation", label: "Inflation" },
  { id: "portfolio", label: "Min Avanza" },
] as const;

type TabId = (typeof tabs)[number]["id"];

type DashboardViewProps = {
  commodities: SummaryResponse | null;
  mag7: SummaryResponse | null;
  indexes?: SummaryResponse | null;
  inflation: SummaryResponse | null;
  portfolio?: PortfolioSummaryResponse | null;
  marketRange?: MarketRange;
  onMarketRangeChange?: (range: MarketRange) => void;
  marketSeriesByModule?: Record<"commodities" | "mag7" | "indexes", Record<string, SparkPoint[]>>;
  portfolioSeries?: Record<string, SparkPoint[]>;
  inflationSeries: Record<string, SparkPoint[]>;
  warnings: string[];
};

type ModuleStatus = "fresh" | "partial" | "stale" | "offline";
type Theme = "light" | "dark";
type PortfolioOwnerSummary = {
  owner_id: string;
  owner_label: string;
  current_value: number;
  acquisition_value: number;
  gain_abs: number;
  gain_pct: number | null;
  bank_value: number;
  total_with_bank: number;
  holding_count: number;
};
type SlideshowSlide =
  | {
      id: string;
      type: "market";
      group: "Råvaror" | "Mag 7" | "Index";
      item: SummaryItem;
    }
  | {
      id: string;
      type: "portfolio-summary";
      group: "Min Avanza";
      totals: PortfolioSummaryResponse["totals"];
      sekToThbRate: number;
      owners: PortfolioOwnerSummary[];
    }
  | {
      id: string;
      type: "portfolio";
      group: "Min Avanza";
      holding: PortfolioHolding;
    }
  | {
      id: string;
      type: "inflation";
      group: "Inflation";
      title: string;
      swedenItem: SummaryItem;
      usaItem: SummaryItem;
      swedenPoints: SparkPoint[];
      usaPoints: SparkPoint[];
    };

const marketRanges: Array<{ id: MarketRange; label: string }> = [
  { id: "1m", label: "1 mån" },
  { id: "3m", label: "3 mån" },
  { id: "6m", label: "6 mån" },
  { id: "1y", label: "12 mån" },
];

const EMPTY_ITEMS: SummaryItem[] = [];
const EMPTY_PORTFOLIO_ITEMS: PortfolioHolding[] = [];
const SLIDESHOW_LOG_KEY = "dashboard-slideshow-log";
const SLIDESHOW_LOG_LIMIT = 2000;
const DEFAULT_SEK_TO_THB_RATE = 3.43;

type BrowserMemoryInfo = {
  usedJSHeapSize?: number;
  totalJSHeapSize?: number;
  jsHeapSizeLimit?: number;
};

type SlideshowLogEntry = {
  at: string;
  event: string;
  index: number;
  slideId: string | null;
  nextIndex?: number;
  nextSlideId?: string | null;
  trigger?: string;
  elapsedSincePreviousMs?: number;
  slideCount: number;
  intervalSeconds: number;
  marketRangeLabel: string;
  isPaused: boolean;
  visibilityState: DocumentVisibilityState;
  userAgent: string;
  memory?: BrowserMemoryInfo;
};

function readSlideshowLog(): SlideshowLogEntry[] {
  try {
    const rawLog = window.localStorage.getItem(SLIDESHOW_LOG_KEY);
    if (!rawLog) return [];
    const parsed = JSON.parse(rawLog);
    return Array.isArray(parsed) ? (parsed as SlideshowLogEntry[]) : [];
  } catch {
    return [];
  }
}

function captureBrowserMemory(): BrowserMemoryInfo | undefined {
  const performanceWithMemory = performance as Performance & { memory?: BrowserMemoryInfo };
  return performanceWithMemory.memory;
}

function writeSlideshowLog(entry: SlideshowLogEntry) {
  try {
    const currentLog = readSlideshowLog();
    const previousAt = currentLog.at(-1)?.at;
    const elapsedSincePreviousMs = previousAt ? Date.parse(entry.at) - Date.parse(previousAt) : undefined;
    const nextEntry = { ...entry, elapsedSincePreviousMs };
    const nextLog = [...currentLog, nextEntry].slice(-SLIDESHOW_LOG_LIMIT);
    window.localStorage.setItem(SLIDESHOW_LOG_KEY, JSON.stringify(nextLog));
  } catch {
    // A diagnostic log must never affect the dashboard itself.
  }
}

function exportSlideshowLog() {
  const log = readSlideshowLog();
  const blob = new Blob([JSON.stringify(log, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `dashboard-slideshow-log-${new Date().toISOString().replaceAll(":", "-")}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function portfolioTotalWithBank(owners: PortfolioOwnerSummary[]): number {
  return owners.reduce((sum, owner) => sum + owner.total_with_bank, 0);
}

function PortfolioLevelsLine({ holding, compact = false, align = "left" }: { holding: PortfolioHolding; compact?: boolean; align?: "left" | "right" }) {
  const levels = holding.levels;
  if (!levels) return null;
  const currency = levels.currency ?? holding.currency;
  const prefix = levels.source === "estimated" ? "Est." : levels.source === "manual+estimated" ? "Delvis est." : null;
  const targetReached = levels.current_price !== null && levels.target_price !== null && levels.current_price >= levels.target_price;
  const stopReached = levels.current_price !== null && levels.stop_price !== null && levels.current_price <= levels.stop_price;
  return (
    <div className={`text-muted flex flex-wrap gap-x-3 gap-y-1 ${align === "right" ? "justify-end text-right" : ""} ${compact ? "mt-3 text-xs" : "mt-2 text-sm"}`}>
      {prefix ? <span>{prefix}</span> : null}
      <span>Nu {formatLevelPrice(levels.current_price, currency)}</span>
      {levels.target_price !== null ? (
        <span className={targetReached ? "change-positive" : undefined}>
          Mål {formatLevelPrice(levels.target_price, currency)}
          {levels.target_distance_pct !== null ? ` (${formatPercent(levels.target_distance_pct)})` : ""}
        </span>
      ) : null}
      {levels.stop_price !== null ? (
        <span className={stopReached ? "change-negative" : undefined}>
          Stopp {formatLevelPrice(levels.stop_price, currency)}
          {levels.stop_distance_pct !== null ? ` (${formatPercent(levels.stop_distance_pct)})` : ""}
        </span>
      ) : null}
    </div>
  );
}

function formatOwnerSekValues(holding: PortfolioHolding, field: "current_value" | "acquisition_value"): string {
  if (!holding.owners.length) return formatSek(holding[field]);
  return holding.owners.map((owner) => formatSek(owner[field])).join(", ");
}

function formatOwnerAcquisitionValues(holding: PortfolioHolding): string {
  if (!holding.owners.length) return formatSek(holding.acquisition_value);
  return holding.owners
    .map((owner) => `${formatSek(owner.acquisition_value)} (${formatPercent(owner.gain_pct)})`)
    .join(", ");
}

function formatSlideshowOwnerLine(holding: PortfolioHolding): string | null {
  if (holding.owners.length !== 1) return null;
  return holding.owners[0]?.owner_label ?? null;
}

function buildPortfolioOwnerSummaries(items: PortfolioHolding[], accounts: PortfolioAccountValue[]): PortfolioOwnerSummary[] {
  const summaries = new Map<string, PortfolioOwnerSummary>();
  for (const holding of items) {
    for (const owner of holding.owners) {
      const current = summaries.get(owner.owner_id) ?? {
        owner_id: owner.owner_id,
        owner_label: owner.owner_label,
        current_value: 0,
        acquisition_value: 0,
        gain_abs: 0,
        gain_pct: null,
        bank_value: 0,
        total_with_bank: 0,
        holding_count: 0,
      };
      current.current_value += owner.current_value;
      current.acquisition_value += owner.acquisition_value ?? 0;
      current.gain_abs += owner.gain_abs ?? 0;
      current.holding_count += 1;
      summaries.set(owner.owner_id, current);
    }
  }

  for (const account of accounts) {
    const current = summaries.get(account.owner_id) ?? {
      owner_id: account.owner_id,
      owner_label: account.owner_label,
      current_value: 0,
      acquisition_value: 0,
      gain_abs: 0,
      gain_pct: null,
      bank_value: 0,
      total_with_bank: 0,
      holding_count: 0,
    };
    current.bank_value = account.bank_value;
    summaries.set(account.owner_id, current);
  }

  const ownerOrder: Record<string, number> = { jp: 0, pat: 1 };
  return [...summaries.values()]
    .map((owner) => ({
      ...owner,
      current_value: Math.round(owner.current_value),
      acquisition_value: Math.round(owner.acquisition_value),
      gain_abs: Math.round(owner.gain_abs),
      bank_value: Math.round(owner.bank_value),
      total_with_bank: Math.round(owner.current_value + owner.bank_value),
      gain_pct: owner.acquisition_value ? (owner.gain_abs / owner.acquisition_value) * 100 : null,
    }))
    .sort((a, b) => (ownerOrder[a.owner_id] ?? 99) - (ownerOrder[b.owner_id] ?? 99));
}

function getModuleStatus(items: Array<{ is_stale: boolean }>): ModuleStatus {
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

function withSeriesFallback(items: SummaryItem[], seriesById: Record<string, SparkPoint[]>): SummaryItem[] {
  return items.map((item) => {
    const points = seriesById[item.id];
    if (!points || points.length === 0) return item;
    return { ...item, sparkline: points };
  });
}

function portfolioWithSeriesFallback(items: PortfolioHolding[], seriesById: Record<string, SparkPoint[]>): PortfolioHolding[] {
  return items.map((item) => {
    const points = seriesById[item.id];
    if (!points || points.length === 0) return item;
    return { ...item, sparkline: points, has_chart: true };
  });
}

function formatXAxisTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "--";
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  return `${date.getUTCFullYear()}-${month}`;
}

function isoWeekLabel(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "--";
  const normalized = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const dayNumber = normalized.getUTCDay() || 7;
  normalized.setUTCDate(normalized.getUTCDate() + 4 - dayNumber);
  const yearStart = new Date(Date.UTC(normalized.getUTCFullYear(), 0, 1));
  const weekNumber = Math.ceil(((normalized.getTime() - yearStart.getTime()) / 86_400_000 + 1) / 7);
  return `v${String(weekNumber).padStart(2, "0")}`;
}

function weeklyTickIndexes(points: SparkPoint[]): number[] {
  const seenWeeks = new Set<string>();
  const indexes = points.reduce<number[]>((result, point, index) => {
    const label = isoWeekLabel(point.t);
    if (label !== "--" && !seenWeeks.has(label)) {
      seenWeeks.add(label);
      result.push(index);
    }
    return result;
  }, []);

  if (indexes.length <= 8) return indexes;
  const step = Math.ceil(indexes.length / 8);
  return indexes.filter((_, index) => index % step === 0);
}

function Sparkline({
  points,
  heightClass = "h-20",
  showXAxis = false,
}: {
  points: SparkPoint[];
  heightClass?: string;
  showXAxis?: boolean;
}) {
  if (points.length < 2) {
    return <div className={`mt-4 ${heightClass} rounded-xl chart-empty`} />;
  }

  const values = points.map((p) => p.v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const rawRange = max - min;
  const range = rawRange || 1;
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

  const tickIndexes = showXAxis
    ? weeklyTickIndexes(points)
    : Array.from(new Set([0, Math.floor((points.length - 1) / 2), points.length - 1]));
  const tickLabels = tickIndexes.map((tickIndex) =>
    showXAxis ? isoWeekLabel(points[tickIndex]?.t ?? "") : formatXAxisTime(points[tickIndex]?.t ?? ""),
  );
  const yAxisValues = rawRange === 0 ? [min + range, min + range / 2, min] : [max, min + range / 2, min];

  return (
    <div className="mt-4">
      <div className={showXAxis ? "chart-with-axis" : ""}>
        <svg className={`${heightClass} w-full`} viewBox="0 0 100 100" preserveAspectRatio="none">
          {showXAxis ? (
            <>
              {yAxisValues.map((_, index) => {
                const y = chartTop + (index / 2) * chartHeight;
                return <line key={`spark-grid-${index}`} x1="0" y1={y} x2="100" y2={y} stroke="var(--chart-grid)" strokeWidth="0.5" />;
              })}
              <line x1="0" y1={chartBottom} x2="100" y2={chartBottom} stroke="var(--chart-grid)" strokeWidth="0.6" />
              {tickIndexes.map((tickIndex) => {
                const x = points.length === 1 ? 50 : (tickIndex / (points.length - 1)) * 100;
                return <line key={`spark-tick-${tickIndex}`} x1={x} y1={chartTop} x2={x} y2={chartBottom + 2} stroke="var(--chart-axis)" strokeWidth="0.25" opacity="0.45" />;
              })}
            </>
          ) : null}
          <polyline
            fill="none"
            stroke="var(--chart-primary)"
            strokeWidth={showXAxis ? "1.8" : "1.5"}
            points={path}
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        {showXAxis ? (
          <div className={`${heightClass} axis-text chart-y-axis text-xs font-semibold`}>
            {yAxisValues.map((value, index) => (
              <span key={`${index}-${value}`}>{formatValue(value)}</span>
            ))}
          </div>
        ) : null}
      </div>
      {showXAxis ? (
        <div className="axis-text chart-x-axis mt-2 text-sm font-semibold leading-none">
          {tickIndexes.map((tickIndex, index) => {
            const x = points.length === 1 ? 50 : (tickIndex / (points.length - 1)) * 100;
            return (
              <span key={`${tickIndex}-${tickLabels[index]}`} style={{ left: `${x}%` }}>
                {tickLabels[index]}
              </span>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function InflationComparisonChart({
  swedenPoints,
  usaPoints,
  heightClass = "h-64",
}: {
  swedenPoints: SparkPoint[];
  usaPoints: SparkPoint[];
  heightClass?: string;
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
    return <div className={`chart-empty mt-4 ${heightClass} rounded-xl`} />;
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
      <svg className={`${heightClass} w-full`} viewBox="0 0 100 100" preserveAspectRatio="none" data-testid="inflation-comparison-chart">
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

function SlideshowOverlay({
  slides,
  activeIndex,
  intervalSeconds,
  marketRangeLabel,
  isPaused,
  onClose,
  onNext,
  onPrevious,
  onTogglePause,
  onExportLog,
}: {
  slides: SlideshowSlide[];
  activeIndex: number;
  intervalSeconds: number;
  marketRangeLabel: string;
  isPaused: boolean;
  onClose: () => void;
  onNext: () => void;
  onPrevious: () => void;
  onTogglePause: () => void;
  onExportLog: () => void;
}) {
  const activeSlide = slides[activeIndex] ?? null;

  return (
    <div className="slideshow-overlay" role="dialog" aria-modal="true" aria-label="Bildspel" data-testid="slideshow-overlay">
      <div className="slideshow-shell">
        {activeSlide ? (
          <article className="slideshow-card">
            <div className="slideshow-controls slideshow-slide-controls">
              <span className="badge">{slides.length > 0 ? `${activeIndex + 1} / ${slides.length}` : "0 / 0"}</span>
              <span className="badge">{isPaused ? "Pausad" : `${intervalSeconds} s`}</span>
              <span className="badge">{marketRangeLabel}</span>
              <button type="button" className="slideshow-control" onClick={onPrevious}>
                Föregående
              </button>
              <button type="button" className="slideshow-control" onClick={onTogglePause}>
                {isPaused ? "Spela" : "Pausa"}
              </button>
              <button type="button" className="slideshow-control" onClick={onNext}>
                Nästa
              </button>
              <button type="button" className="slideshow-control" onClick={onExportLog}>
                Logg
              </button>
              <button type="button" className="slideshow-control slideshow-close" onClick={onClose}>
                Stäng
              </button>
            </div>
            {activeSlide.type === "market" ? (
              <>
                <div className="slideshow-heading">
                  <div>
                    <h3 className="section-title text-5xl">{activeSlide.item.name}</h3>
                    <p className="text-muted mt-2 text-sm">
                      {activeSlide.group} • {activeSlide.item.is_stale ? "Stale" : "Live"} • {activeSlide.item.unit ?? "--"} • {activeSlide.item.price_type ?? "--"}
                    </p>
                  </div>
                  <div className="slideshow-value-block">
                    <div className="kpi-subtle">Senast</div>
                    <div className="slideshow-value">{formatValue(activeSlide.item.last)}</div>
                    <div className={`text-lg font-semibold ${changeToneClass(activeSlide.item.day_pct)}`}>
                      {formatAbsAndPercent(activeSlide.item.day_abs, activeSlide.item.day_pct)}
                    </div>
                  </div>
                </div>
                <Sparkline points={activeSlide.item.sparkline} heightClass="h-[55vh]" showXAxis />
              </>
            ) : activeSlide.type === "portfolio-summary" ? (
              <>
                <div className="slideshow-heading">
                  <div>
                    <h3 className="section-title text-5xl">Min Avanza</h3>
                    <p className="text-muted mt-2 text-sm">
                      {activeSlide.group} • JP och Pat • {activeSlide.totals.holding_count} innehav • {activeSlide.totals.chart_count} grafer
                    </p>
                  </div>
                  <div className="slideshow-value-block">
                    <div className="kpi-subtle">Totalt inklusive bankkonto</div>
                    <div className="slideshow-value slideshow-total-value">{formatSek(portfolioTotalWithBank(activeSlide.owners))}</div>
                    <div className="slideshow-total-subvalue">{formatThb(portfolioTotalWithBank(activeSlide.owners) * activeSlide.sekToThbRate)}</div>
                    <div className="slideshow-total-rate">{formatSekToThbRate(activeSlide.sekToThbRate)}</div>
                  </div>
                </div>
                <div className="mt-8 text-center">
                  <div className="kpi-subtle">Totalt innehav</div>
                  <div className="text-4xl font-semibold">{formatSek(activeSlide.totals.current_value)}</div>
                  <div className={`mt-2 text-lg font-semibold ${changeToneClass(activeSlide.totals.gain_pct)}`}>
                    Inköpsvärde {formatSek(activeSlide.totals.acquisition_value)} ({formatPercent(activeSlide.totals.gain_pct)})
                  </div>
                </div>
                <div className="mt-8 grid gap-4 md:grid-cols-2">
                  {activeSlide.owners.map((owner) => (
                    <div key={owner.owner_id} className="card-surface p-5">
                      <div className="flex items-center justify-between gap-3">
                        <h4 className="text-2xl font-semibold">{owner.owner_label}</h4>
                        <span className="badge">{owner.holding_count} innehav</span>
                      </div>
                      <div className="mt-5 text-4xl font-semibold">{formatSek(owner.total_with_bank)}</div>
                      <div className="text-muted mt-2 text-base font-semibold">
                        Varav Bankkonto {formatSek(owner.bank_value)}
                      </div>
                      <div className="text-muted mt-5 grid max-w-md grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-base font-semibold">
                        <span>Nuvärde:</span>
                        <span>{formatSek(owner.current_value)}</span>
                        <span>Inköpsvärde:</span>
                        <span>{formatSek(owner.acquisition_value)}</span>
                        <span>Resultat:</span>
                        <span className={changeToneClass(owner.gain_pct)}>
                          {formatSek(owner.gain_abs)} ({formatPercent(owner.gain_pct)})
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : activeSlide.type === "portfolio" ? (
              <>
                <div className="slideshow-heading">
                  <div>
                    <h3 className="section-title text-5xl">{activeSlide.holding.name}</h3>
                    <p className="text-muted mt-2 text-sm">
                      {activeSlide.group} • {activeSlide.holding.ticker ?? "--"} • {activeSlide.holding.instrument_type}
                    </p>
                  </div>
                  <div className="slideshow-value-block">
                    <div className="kpi-subtle">Nuvarande värde</div>
                    <div className="slideshow-value">{formatSek(activeSlide.holding.current_value)}</div>
                    <div className={`text-lg font-semibold ${changeToneClass(activeSlide.holding.gain_pct)}`}>
                      Inköpsvärde {formatSek(activeSlide.holding.acquisition_value)} ({formatPercent(activeSlide.holding.gain_pct)})
                    </div>
                    {formatSlideshowOwnerLine(activeSlide.holding) ? (
                      <div className="text-muted text-base font-semibold">
                        {formatSlideshowOwnerLine(activeSlide.holding)}
                      </div>
                    ) : activeSlide.holding.owners.length ? (
                      <div className="text-muted text-base font-semibold">
                        {formatOwnerSekValues(activeSlide.holding, "current_value")}
                      </div>
                    ) : null}
                    {activeSlide.holding.owners.length > 1 ? (
                      <div className="text-muted text-sm">
                        {formatOwnerAcquisitionValues(activeSlide.holding)}
                      </div>
                    ) : null}
                    <PortfolioLevelsLine holding={activeSlide.holding} align="right" />
                  </div>
                </div>
                <Sparkline points={activeSlide.holding.sparkline} heightClass="h-[55vh]" showXAxis />
              </>
            ) : (
              <>
                <div className="slideshow-heading">
                  <div>
                    <h3 className="section-title text-5xl">{activeSlide.title}</h3>
                    <p className="text-muted mt-2 text-sm">
                      {activeSlide.group} • {activeSlide.swedenItem.is_stale || activeSlide.usaItem.is_stale ? "Stale" : "Live"} • Gemensam graf för Sverige och USA
                    </p>
                  </div>
                  <div className="slideshow-value-block">
                    <div className="kpi-subtle">Senast</div>
                    <div className="text-2xl font-semibold">
                      Sverige {formatValue(activeSlide.swedenItem.last)} / USA {formatValue(activeSlide.usaItem.last)}
                    </div>
                    <div className="text-muted text-sm">
                      Förändring: Sverige {formatPercent(activeSlide.swedenItem.day_pct)} / USA {formatPercent(activeSlide.usaItem.day_pct)}
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex items-center gap-4 text-sm font-semibold">
                  <span className="inline-flex items-center gap-2">
                    <span className="legend-dot-sweden h-3 w-3 rounded-full" />
                    Sverige
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <span className="legend-dot-usa h-3 w-3 rounded-full" />
                    USA
                  </span>
                </div>
                <InflationComparisonChart
                  swedenPoints={activeSlide.swedenPoints}
                  usaPoints={activeSlide.usaPoints}
                  heightClass="h-[55vh]"
                />
              </>
            )}
          </article>
        ) : (
          <div className="slideshow-card text-muted">Ingen grafdata tillgänglig för bildspel.</div>
        )}
      </div>
    </div>
  );
}

function resolvePreferredTheme(): Theme {
  const savedTheme = window.localStorage.getItem("dashboard-theme");
  if (savedTheme === "light" || savedTheme === "dark") return savedTheme;
  if (typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

export function DashboardView({
  commodities,
  mag7,
  indexes,
  inflation,
  portfolio,
  marketRange = "1m",
  onMarketRangeChange,
  marketSeriesByModule = { commodities: {}, mag7: {}, indexes: {} },
  portfolioSeries = {},
  inflationSeries,
  warnings,
}: DashboardViewProps) {
  const [theme, setTheme] = useState<Theme>("light");
  const [hasResolvedTheme, setHasResolvedTheme] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("commodities");
  const [mag7SortField, setMag7SortField] = useState<Mag7SortField>("ytd_pct");
  const [mag7SortDirection, setMag7SortDirection] = useState<"asc" | "desc">("desc");
  const [selectedMarketChartId, setSelectedMarketChartId] = useState<string | null>(null);
  const [isSlideshowOpen, setIsSlideshowOpen] = useState(false);
  const [slideshowIntervalSeconds, setSlideshowIntervalSeconds] = useState(10);
  const [slideshowIndex, setSlideshowIndex] = useState(0);
  const [isSlideshowPaused, setIsSlideshowPaused] = useState(false);
  const previousSlideshowOpenRef = useRef(false);
  const previousSlideshowIndexRef = useRef(0);
  const previousSlideshowPausedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setTheme(resolvePreferredTheme());
      setHasResolvedTheme(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!hasResolvedTheme) return;
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem("dashboard-theme", theme);
  }, [hasResolvedTheme, theme]);

  const commodityItems = commodities?.items ?? EMPTY_ITEMS;
  const mag7Items = mag7?.items ?? EMPTY_ITEMS;
  const indexItems = indexes?.items ?? EMPTY_ITEMS;
  const inflationItems = inflation?.items ?? EMPTY_ITEMS;
  const portfolioItems = portfolio?.holdings ?? EMPTY_PORTFOLIO_ITEMS;
  const hasPortfolio = portfolio?.enabled === true;

  const commodityStatus = getModuleStatus(commodityItems);
  const mag7Status = getModuleStatus(mag7Items);
  const indexStatus = getModuleStatus(indexItems);
  const inflationStatus = getModuleStatus(inflationItems);
  const portfolioStatus = getModuleStatus(portfolioItems);
  const tabStatuses: Record<TabId, ModuleStatus> = {
    commodities: commodityStatus,
    mag7: mag7Status,
    indexes: indexStatus,
    inflation: inflationStatus,
    portfolio: portfolioStatus,
  };
  const latestUpdate = commodities?.meta.fetched_at ?? mag7?.meta.fetched_at ?? indexes?.meta.fetched_at ?? inflation?.meta.fetched_at ?? portfolio?.meta.fetched_at;
  const sourceNames = Array.from(
    new Set(
      [commodities?.meta.source, mag7?.meta.source, indexes?.meta.source, inflation?.meta.source, portfolio?.meta.source]
        .filter((source): source is string => Boolean(source))
        .map(sourceDisplayName),
    ),
  );
  const sourceLabel = sourceNames.length > 0 ? sourceNames.join(" + ") : "--";

  const filteredCommodityItems = useMemo(
    () => sortCommoditiesForDisplay(withSeriesFallback(commodityItems, marketSeriesByModule.commodities)),
    [commodityItems, marketSeriesByModule.commodities],
  );
  const filteredMag7Items = useMemo(
    () => sortMag7Items(withSeriesFallback(mag7Items, marketSeriesByModule.mag7), mag7SortField, mag7SortDirection),
    [mag7Items, mag7SortDirection, mag7SortField, marketSeriesByModule.mag7],
  );
  const filteredIndexItems = useMemo(
    () => withSeriesFallback(indexItems, marketSeriesByModule.indexes),
    [indexItems, marketSeriesByModule.indexes],
  );
  const filteredPortfolioItems = useMemo(
    () => portfolioWithSeriesFallback(portfolioItems, portfolioSeries),
    [portfolioItems, portfolioSeries],
  );

  const swedenInflationItem = inflationItems.find((item) => item.id.includes("se")) ?? null;
  const usaInflationItem = inflationItems.find((item) => item.id.includes("us")) ?? null;
  const swedenInflationPoints = useMemo(
    () => (swedenInflationItem ? inflationSeries[swedenInflationItem.id] ?? swedenInflationItem.sparkline : []),
    [inflationSeries, swedenInflationItem],
  );
  const usaInflationPoints = useMemo(
    () => (usaInflationItem ? inflationSeries[usaInflationItem.id] ?? usaInflationItem.sparkline : []),
    [inflationSeries, usaInflationItem],
  );

  const showMarketSections = activeTab === "commodities" || activeTab === "mag7" || activeTab === "indexes";
  const showMag7Table = activeTab === "mag7";
  const showIndexCards = activeTab === "indexes";
  const showInflation = activeTab === "inflation";
  const showPortfolio = activeTab === "portfolio" && hasPortfolio;
  const visibleTabs = hasPortfolio ? tabs : tabs.filter((tab) => tab.id !== "portfolio");
  const marketRangeLabel = marketRanges.find((rangeOption) => rangeOption.id === marketRange)?.label ?? marketRange;

  const kpiItems = showMag7Table ? topMag7Cards(filteredMag7Items) : showIndexCards ? filteredIndexItems : filteredCommodityItems;
  const kpiTitle = showMag7Table ? "Magnificent 7" : showIndexCards ? "Index" : "Råvaror";
  const kpiEmptyText = showMag7Table
    ? "Ingen Mag 7-data tillganglig."
    : showIndexCards
      ? "Ingen indexdata tillganglig."
      : "Ingen ravarudata tillganglig.";
  const tableItems = showMag7Table ? filteredMag7Items : filteredCommodityItems;
  const tableLabel = showMag7Table ? "MAG 7" : "RAVAROR";
  const tableFirstColumn = showMag7Table ? "Bolag" : "Ravara / Enhet";
  const tableEmptyText = showMag7Table ? "Data kunde inte laddas for Mag 7." : "Data kunde inte laddas for ravaror.";
  const tableGridClass = showMag7Table ? "grid-cols-7" : "grid-cols-8";
  const selectedMarketChart = kpiItems.find((item) => item.id === selectedMarketChartId) ?? kpiItems[0] ?? null;
  const selectedPortfolioHolding = filteredPortfolioItems.find((item) => item.id === selectedMarketChartId) ?? filteredPortfolioItems[0] ?? null;
  const portfolioAccounts = useMemo(() => portfolio?.accounts ?? [], [portfolio?.accounts]);
  const portfolioOwnerSummaries = useMemo(() => buildPortfolioOwnerSummaries(filteredPortfolioItems, portfolioAccounts), [filteredPortfolioItems, portfolioAccounts]);
  const sekToThbRate = portfolio?.meta.exchange_rates?.sek_to_thb?.rate ?? DEFAULT_SEK_TO_THB_RATE;
  const slideshowSlides: SlideshowSlide[] = useMemo(
    () => [
      ...filteredCommodityItems.map((item) => ({
        id: `commodity-${item.id}`,
        type: "market" as const,
        group: "Råvaror" as const,
        item,
      })),
      ...filteredMag7Items.map((item) => ({
        id: `mag7-${item.id}`,
        type: "market" as const,
        group: "Mag 7" as const,
        item,
      })),
      ...filteredIndexItems.map((item) => ({
        id: `index-${item.id}`,
        type: "market" as const,
        group: "Index" as const,
        item,
      })),
      ...(portfolio && filteredPortfolioItems.length > 0
        ? [
            {
              id: "portfolio-summary",
              type: "portfolio-summary" as const,
              group: "Min Avanza" as const,
              totals: portfolio.totals,
              sekToThbRate,
              owners: portfolioOwnerSummaries,
            },
          ]
        : []),
      ...filteredPortfolioItems
        .filter((holding) => holding.has_chart && holding.sparkline.length >= 2)
        .map((holding) => ({
          id: `portfolio-${holding.id}`,
          type: "portfolio" as const,
          group: "Min Avanza" as const,
          holding,
        })),
      ...(swedenInflationItem && usaInflationItem
        ? [
            {
              id: "inflation-comparison",
              type: "inflation" as const,
              group: "Inflation" as const,
              title: "Inflation: Sverige & USA",
              swedenItem: swedenInflationItem,
              usaItem: usaInflationItem,
              swedenPoints: swedenInflationPoints,
              usaPoints: usaInflationPoints,
            },
          ]
        : []),
    ],
    [filteredCommodityItems, filteredIndexItems, filteredMag7Items, filteredPortfolioItems, portfolio, portfolioOwnerSummaries, sekToThbRate, swedenInflationItem, swedenInflationPoints, usaInflationItem, usaInflationPoints],
  );
  const safeSlideshowIndex = slideshowSlides.length > 0 ? Math.min(slideshowIndex, slideshowSlides.length - 1) : 0;
  const activeSlideshowSlide = slideshowSlides[safeSlideshowIndex] ?? null;
  const logSlideshowEvent = useCallback((event: string, index = safeSlideshowIndex, slide = activeSlideshowSlide, paused = isSlideshowPaused, nextIndex?: number, trigger?: string) => {
    writeSlideshowLog({
      at: new Date().toISOString(),
      event,
      index,
      slideId: slide?.id ?? null,
      nextIndex,
      nextSlideId: nextIndex === undefined ? undefined : (slideshowSlides[nextIndex]?.id ?? null),
      trigger,
      slideCount: slideshowSlides.length,
      intervalSeconds: slideshowIntervalSeconds,
      marketRangeLabel,
      isPaused: paused,
      visibilityState: document.visibilityState,
      userAgent: navigator.userAgent,
      memory: captureBrowserMemory(),
    });
  }, [activeSlideshowSlide, isSlideshowPaused, marketRangeLabel, safeSlideshowIndex, slideshowIntervalSeconds, slideshowSlides]);
  const openSlideshow = () => {
    setSlideshowIndex(0);
    setIsSlideshowPaused(false);
    setIsSlideshowOpen(true);
  };
  const advanceSlideshow = useCallback((direction: 1 | -1, trigger: string) => {
    setSlideshowIndex((current) => {
      if (slideshowSlides.length === 0) return 0;
      const nextIndex = (current + direction + slideshowSlides.length) % slideshowSlides.length;
      logSlideshowEvent("advance", current, slideshowSlides[current] ?? null, isSlideshowPaused, nextIndex, trigger);
      return nextIndex;
    });
  }, [isSlideshowPaused, logSlideshowEvent, slideshowSlides]);
  const goToNextSlide = () => {
    advanceSlideshow(1, "button");
  };
  const goToPreviousSlide = () => {
    advanceSlideshow(-1, "button");
  };

  useEffect(() => {
    if (!isSlideshowOpen || isSlideshowPaused || slideshowSlides.length <= 1) return undefined;
    const timer = window.setInterval(() => {
      advanceSlideshow(1, "timer");
    }, slideshowIntervalSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [advanceSlideshow, isSlideshowOpen, isSlideshowPaused, slideshowIntervalSeconds, slideshowSlides.length]);

  useEffect(() => {
    if (!isSlideshowOpen) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsSlideshowOpen(false);
      } else if (event.key === "ArrowRight") {
        advanceSlideshow(1, "keyboard");
      } else if (event.key === "ArrowLeft") {
        advanceSlideshow(-1, "keyboard");
      } else if (event.key === " ") {
        event.preventDefault();
        setIsSlideshowPaused((current) => !current);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [advanceSlideshow, isSlideshowOpen]);

  useEffect(() => {
    const wasOpen = previousSlideshowOpenRef.current;
    const previousIndex = previousSlideshowIndexRef.current;
    const previousPaused = previousSlideshowPausedRef.current;
    if (isSlideshowOpen && !wasOpen) {
      logSlideshowEvent("open");
    } else if (!isSlideshowOpen && wasOpen) {
      logSlideshowEvent("close", previousIndex, slideshowSlides[previousIndex] ?? null, previousPaused);
    } else if (isSlideshowOpen && safeSlideshowIndex !== previousIndex) {
      logSlideshowEvent("slide");
    } else if (isSlideshowOpen && isSlideshowPaused !== previousPaused) {
      logSlideshowEvent(isSlideshowPaused ? "pause" : "resume");
    }

    if (isSlideshowOpen) {
      previousSlideshowIndexRef.current = safeSlideshowIndex;
      previousSlideshowPausedRef.current = isSlideshowPaused;
    } else if (wasOpen) {
      previousSlideshowIndexRef.current = 0;
      previousSlideshowPausedRef.current = false;
    }
    previousSlideshowOpenRef.current = isSlideshowOpen;
  }, [isSlideshowOpen, isSlideshowPaused, logSlideshowEvent, safeSlideshowIndex, slideshowSlides]);

  useEffect(() => {
    if (!isSlideshowOpen) return undefined;
    const timer = window.setInterval(() => {
      logSlideshowEvent("heartbeat");
    }, 15_000);
    return () => window.clearInterval(timer);
  }, [isSlideshowOpen, logSlideshowEvent]);

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
        <div className="flex flex-wrap items-center gap-2">
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              className="tab-pill"
              data-active={tab.id === activeTab}
              aria-label={tab.label}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}: {statusLabel(tabStatuses[tab.id])}
            </button>
          ))}
          <button
            type="button"
            className="tab-pill"
            data-active="false"
            aria-label="Bildspel"
            onClick={openSlideshow}
          >
            Bildspel
          </button>
          <div className="flex flex-wrap items-center gap-2" aria-label="Tidsspann marknadsgrafer">
            {marketRanges.map((rangeOption) => (
              <button
                key={`market-range-${rangeOption.id}`}
                type="button"
                className="tab-pill"
                data-active={marketRange === rangeOption.id}
                onClick={() => onMarketRangeChange?.(rangeOption.id)}
              >
                {rangeOption.label}
              </button>
            ))}
          </div>
          <label className="sr-only" htmlFor="slideshow-interval">Bildspelsintervall</label>
          <select
            id="slideshow-interval"
            className="select-control rounded-full px-3 py-2 text-sm font-semibold"
            aria-label="Bildspelsintervall"
            value={slideshowIntervalSeconds}
            onChange={(event) => setSlideshowIntervalSeconds(Number(event.target.value))}
          >
            <option value={5}>5 sek</option>
            <option value={10}>10 sek</option>
            <option value={15}>15 sek</option>
            <option value={30}>30 sek</option>
          </select>
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

      {showPortfolio ? (
        <>
          <section className="mt-8">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="section-title text-2xl">Min Avanza</h2>
                <div className="text-muted mt-2 text-sm">
                  Totalt: <span className="text-strong font-semibold">{formatSek(portfolio.totals.current_value)}</span>
                  {" "}• Inköpsvärde: <span className="text-strong font-semibold">{formatSek(portfolio.totals.acquisition_value)}</span>
                  {" "}• Resultat: <span className={changeToneClass(portfolio.totals.gain_pct)}>{formatSek(portfolio.totals.gain_abs)} ({formatPercent(portfolio.totals.gain_pct)})</span>
                </div>
              </div>
              <span className="kpi-subtle">{portfolio.totals.holding_count} innehav • {portfolio.totals.chart_count} grafer</span>
            </div>
            <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {filteredPortfolioItems.map((holding) => (
                <button
                  key={holding.id}
                  type="button"
                  data-testid={`portfolio-card-${holding.id}`}
                  className="card-surface commodity-card kpi-card-80 p-4 text-left transition-transform hover:-translate-y-0.5"
                  data-active={selectedPortfolioHolding?.id === holding.id}
                  onClick={() => setSelectedMarketChartId(holding.id)}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold">{holding.name}</div>
                      <div className="text-xs kpi-subtle">{holding.instrument_type} • {holding.chart_label ?? holding.ticker ?? "Ingen graf"}</div>
                    </div>
                    <span className="badge">{holding.has_chart ? "Graf" : "Värde"}</span>
                  </div>
                  <div className="mt-5 kpi-value">{formatSek(holding.current_value)}</div>
                  <div className={`mt-2 text-sm kpi-change ${changeToneClass(holding.gain_pct)}`}>
                    {formatSek(holding.gain_abs)} ({formatPercent(holding.gain_pct)})
                  </div>
                  <PortfolioLevelsLine holding={holding} compact />
                  <Sparkline points={holding.sparkline} heightClass="h-16" />
                </button>
              ))}
              {filteredPortfolioItems.length === 0 ? (
                <div className="card-surface text-muted p-5 text-sm">Ingen portfoliodata tillgänglig.</div>
              ) : null}
            </div>
          </section>

          <section className="mt-8">
            <div className="flex items-center justify-between">
              <h2 className="section-title text-2xl">Vald graf</h2>
              <span className="kpi-subtle">Klicka pa en ruta for att byta</span>
            </div>
            {selectedPortfolioHolding ? (
              <article className="card-surface mt-4 p-6" data-testid="selected-portfolio-chart-panel">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold">{selectedPortfolioHolding.name}</h3>
                    <p className="text-muted text-xs">
                      {selectedPortfolioHolding.quantity.toLocaleString("sv-SE")} st/andelar • {selectedPortfolioHolding.chart_label ?? selectedPortfolioHolding.ticker ?? "ingen ticker"} • {selectedPortfolioHolding.instrument_type}
                    </p>
                  </div>
                  <span className="badge">{selectedPortfolioHolding.has_chart ? "Graf" : "Endast värde"}</span>
                </div>
                <div className="text-muted mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm">
                  <span>Nuvarande värde: <span className="text-strong font-semibold">{formatOwnerSekValues(selectedPortfolioHolding, "current_value")}</span></span>
                  <span>Inköpsvärde: <span className="text-strong font-semibold">{formatOwnerAcquisitionValues(selectedPortfolioHolding)}</span></span>
                  <span>Resultat: <span className={changeToneClass(selectedPortfolioHolding.gain_pct)}>{formatSek(selectedPortfolioHolding.gain_abs)} ({formatPercent(selectedPortfolioHolding.gain_pct)})</span></span>
                  {selectedPortfolioHolding.chart_source === "proxy" ? <span>Graf: <span className="text-strong font-semibold">proxy</span></span> : null}
                  {selectedPortfolioHolding.valuation_is_stale ? <span>Fondkurs: <span className="text-strong font-semibold">senast kända</span></span> : null}
                </div>
                <PortfolioLevelsLine holding={selectedPortfolioHolding} />
                <Sparkline points={selectedPortfolioHolding.sparkline} heightClass="h-56" showXAxis />
              </article>
            ) : (
              <div className="card-surface text-muted mt-4 p-5 text-sm">Ingen portfoliodata tillgänglig.</div>
            )}
          </section>
        </>
      ) : null}

      {showMarketSections && !showIndexCards ? (
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
            <span className="kpi-subtle">12 mån</span>
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

      {isSlideshowOpen ? (
        <SlideshowOverlay
          slides={slideshowSlides}
          activeIndex={safeSlideshowIndex}
          intervalSeconds={slideshowIntervalSeconds}
          marketRangeLabel={marketRangeLabel}
          isPaused={isSlideshowPaused}
          onClose={() => setIsSlideshowOpen(false)}
          onNext={goToNextSlide}
          onPrevious={goToPreviousSlide}
          onTogglePause={() => setIsSlideshowPaused((current) => !current)}
          onExportLog={exportSlideshowLog}
        />
      ) : null}
    </main>
  );
}
