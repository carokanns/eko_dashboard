export function formatValue(value: number | null, precision = 2): string {
  if (value === null) return "--";
  return value.toFixed(precision);
}

export function formatSek(value: number | null, precision = 0): string {
  if (value === null) return "--";
  return `${value.toLocaleString("sv-SE", {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  })} kr`;
}

export function formatThb(value: number | null): string {
  if (value === null) return "--";
  return `${value.toLocaleString("sv-SE", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })} THB`;
}

export function formatSekToThbRate(value: number): string {
  return `1 SEK = ${value.toLocaleString("sv-SE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} THB`;
}

export function formatPercent(value: number | null): string {
  if (value === null) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatSignedValue(value: number | null, precision = 2): string {
  if (value === null) return "--";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(precision)}`;
}

export function formatLevelPrice(value: number | null, currency: string | null | undefined): string {
  if (value === null) return "--";
  const formatted = value.toLocaleString("sv-SE", {
    minimumFractionDigits: value >= 100 ? 0 : 2,
    maximumFractionDigits: value >= 100 ? 0 : 2,
  });
  return currency ? `${formatted} ${currency}` : formatted;
}

export function formatAbsAndPercent(dayAbs: number | null, dayPct: number | null): string {
  if (dayAbs === null && dayPct === null) return "--";
  if (dayAbs === null) return formatPercent(dayPct);
  if (dayPct === null) return formatSignedValue(dayAbs);
  return `${formatSignedValue(dayAbs)} (${formatPercent(dayPct)})`;
}

export function changeToneClass(value: number | null): string {
  if (value === null) return "change-neutral";
  if (value > 0) return "change-positive";
  if (value < 0) return "change-negative";
  return "change-neutral";
}

export function formatUpdateTime(timestamp: string | undefined): string {
  if (!timestamp) return "--:--";
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "--:--";
  return date.toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" });
}

export function formatTimestampCell(timestamp: string | null | undefined): string {
  if (!timestamp) return "--";
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "--";
  return date.toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" });
}

export function sourceDisplayName(source: string): string {
  if (source === "yahoo_finance") return "Yahoo";
  if (source === "fred") return "FRED";
  if (source === "local_avanza_export") return "Avanza CSV";
  return source;
}
