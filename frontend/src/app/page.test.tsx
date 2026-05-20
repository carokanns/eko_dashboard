import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { DashboardView } from "./dashboard-view";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: vi.fn(),
  }),
}));

const summary = {
  items: [
    {
      id: "brent",
      name: "Brentolja",
      unit: "USD/fat",
      price_type: "Spot",
      last: 82.5,
      day_abs: 1.2,
      day_pct: 1.47,
      w1_pct: 2.12,
      ytd_pct: 5.31,
      y1_pct: 8.65,
      timestamp_local: "2026-02-07T10:00:00Z",
      is_stale: false,
      sparkline: [],
    },
  ],
  meta: {
    source: "yahoo_finance",
    cached: false,
    fetched_at: "2026-02-07T10:00:00Z",
  },
};

const inflationSeriesByRange: Record<"3m" | "6m" | "1y", Record<string, { t: string; v: number }[]>> = {
  "3m": {},
  "6m": {},
  "1y": {},
};

function buildSummary(overrides?: Partial<(typeof summary)["meta"]>) {
  return {
    ...summary,
    meta: {
      ...summary.meta,
      ...overrides,
    },
  };
}

test("renders dashboard with live values", () => {
  render(
    <DashboardView
      commodities={summary}
      mag7={summary}
      inflation={summary}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );
  expect(screen.getByText("Marknadsöversikt")).toBeInTheDocument();
  expect(screen.getAllByText("Brentolja").length).toBeGreaterThan(0);
  expect(screen.getAllByText("82.50").length).toBeGreaterThan(0);
  expect(screen.getByText("Råvaror: Fresh")).toBeInTheDocument();
});

test("renders stale indicator and warning fallback", () => {
  render(
    <DashboardView
      commodities={null}
      mag7={null}
      inflation={null}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={["Kunde inte hamta ravaror just nu."]}
    />,
  );
  expect(screen.getByText("Kunde inte hamta ravaror just nu.")).toBeInTheDocument();
  expect(screen.getByText("Råvaror: Offline")).toBeInTheDocument();
  expect(screen.getByText("Mag 7: Offline")).toBeInTheDocument();
  expect(screen.getByText("Index: Offline")).toBeInTheDocument();
  expect(screen.getByText("Inflation: Offline")).toBeInTheDocument();
  expect(screen.getByText("Ingen ravarudata tillganglig.")).toBeInTheDocument();
});

test("renders both live and stale badges for partial commodity data", () => {
  const mixed = {
    ...summary,
    items: [
      summary.items[0],
      {
        ...summary.items[0],
        id: "wti",
        name: "WTI-olja",
        is_stale: true,
        last: null,
        day_pct: null,
      },
    ],
  };

  render(
    <DashboardView
      commodities={mixed}
      mag7={summary}
      inflation={summary}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );
  expect(screen.getAllByText("Live").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Stale").length).toBeGreaterThan(0);
});

test("handles cached and invalid fetched_at without crashing", () => {
  const cachedWithInvalidDate = buildSummary({ cached: true, fetched_at: "not-a-date" });
  render(
    <DashboardView
      commodities={cachedWithInvalidDate}
      mag7={null}
      inflation={null}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );
  expect(screen.getAllByText("--:--").length).toBeGreaterThan(0);
});

test("applies saved theme after mount", async () => {
  window.localStorage.setItem("dashboard-theme", "dark");

  render(
    <DashboardView
      commodities={summary}
      mag7={summary}
      inflation={summary}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );

  expect(await screen.findByRole("button", { name: "Ljust lage" })).toHaveAttribute("data-theme", "dark");
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
});

test("removes search box and shows status inside tabs", () => {
  render(
    <DashboardView
      commodities={summary}
      mag7={summary}
      inflation={summary}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );

  expect(screen.queryByPlaceholderText(/Sok i/i)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Råvaror" })).toHaveTextContent("Råvaror: Fresh");
  expect(screen.getByRole("button", { name: "Mag 7" })).toHaveTextContent("Mag 7: Fresh");
  expect(screen.getByRole("button", { name: "Index" })).toHaveTextContent("Index: Offline");
  expect(screen.getByRole("button", { name: "Inflation" })).toHaveTextContent("Inflation: Fresh");
});

test("sorts Mag7 table with sort controls", () => {
  const mag7 = {
    ...summary,
    items: [
      { ...summary.items[0], id: "aapl", name: "Apple", ytd_pct: 2.0, last: 190.0 },
      { ...summary.items[0], id: "nvda", name: "Nvidia", ytd_pct: 9.0, last: 120.0 },
    ],
  };
  render(
    <DashboardView
      commodities={summary}
      mag7={mag7}
      inflation={summary}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Mag 7" }));
  let rows = screen.getAllByTestId(/^table-row-/);
  expect(rows[0]).toHaveAttribute("data-testid", "table-row-nvda");
  fireEvent.change(screen.getByLabelText("Sortera Mag7 efter"), { target: { value: "last" } });
  rows = screen.getAllByTestId(/^table-row-/);
  expect(rows[0]).toHaveAttribute("data-testid", "table-row-aapl");
  fireEvent.click(screen.getByRole("button", { name: "Fallande" }));
  rows = screen.getAllByTestId(/^table-row-/);
  expect(rows[0]).toHaveAttribute("data-testid", "table-row-nvda");
});

test("Mag 7 tab shows top 6 cards, selected chart and table", () => {
  const mag7 = {
    ...summary,
    items: [
      { ...summary.items[0], id: "aapl", name: "Apple" },
      { ...summary.items[0], id: "msft", name: "Microsoft" },
      { ...summary.items[0], id: "googl", name: "Alphabet" },
      { ...summary.items[0], id: "amzn", name: "Amazon" },
      { ...summary.items[0], id: "nvda", name: "Nvidia" },
      { ...summary.items[0], id: "meta", name: "Meta" },
      { ...summary.items[0], id: "tsla", name: "Tesla" },
    ],
  };

  render(
    <DashboardView
      commodities={summary}
      mag7={mag7}
      inflation={summary}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Mag 7" }));
  expect(screen.getByText("MAG 7")).toBeInTheDocument();
  expect(screen.getByText("Magnificent 7")).toBeInTheDocument();
  expect(screen.getByTestId("selected-market-chart-panel")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-msft")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-nvda")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-aapl")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-amzn")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-googl")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-meta")).toBeInTheDocument();
  expect(screen.queryByTestId("kpi-card-tsla")).not.toBeInTheDocument();
  expect(screen.getAllByTestId(/^kpi-card-/)).toHaveLength(6);
});

test("switches table content to Mag7 when Mag 7 tab is selected", () => {
  const commodities = {
    ...summary,
    items: [{ ...summary.items[0], id: "brent", name: "Brentolja" }],
  };
  const mag7 = {
    ...summary,
    items: [{ ...summary.items[0], id: "aapl", name: "Apple" }],
  };

  render(
    <DashboardView
      commodities={commodities}
      mag7={mag7}
      inflation={summary}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );
  expect(screen.getByTestId("table-row-brent")).toBeInTheDocument();
  expect(screen.queryByTestId("table-row-aapl")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Mag 7" }));
  expect(screen.getByText("MAG 7")).toBeInTheDocument();
  expect(screen.getByTestId("table-row-aapl")).toBeInTheDocument();
  expect(screen.queryByTestId("table-row-brent")).not.toBeInTheDocument();
});

test("Index tab shows index cards and selected chart without table", () => {
  const indexes = {
    ...summary,
    items: [
      { ...summary.items[0], id: "msci_acwi", name: "MSCI ACWI", unit: "punkter", price_type: "Globalt aktieindex" },
      { ...summary.items[0], id: "sp500", name: "S&P 500", unit: "punkter", price_type: "USA large cap" },
      { ...summary.items[0], id: "nasdaq_100", name: "Nasdaq 100", unit: "punkter", price_type: "USA teknologi" },
      { ...summary.items[0], id: "stoxx_europe_600", name: "STOXX Europe 600", unit: "punkter", price_type: "Europa brett" },
      { ...summary.items[0], id: "omxs30", name: "OMXS30", unit: "punkter", price_type: "Sverige large cap" },
      { ...summary.items[0], id: "msci_emerging_markets", name: "MSCI Emerging Markets", unit: "punkter", price_type: "Tillväxtmarknader" },
      { ...summary.items[0], id: "bloomberg_commodity", name: "Bloomberg Commodity Index", unit: "punkter", price_type: "Råvaruindex" },
      { ...summary.items[0], id: "us_10y_yield", name: "US 10Y-ränta", unit: "indexpunkter", price_type: "CBOE 10Y yield" },
      { ...summary.items[0], id: "dxy", name: "DXY / USD-index", unit: "punkter", price_type: "Dollarindex" },
      { ...summary.items[0], id: "vix", name: "VIX", unit: "punkter", price_type: "Volatilitet" },
    ],
  };

  render(
    <DashboardView
      commodities={summary}
      mag7={summary}
      indexes={indexes}
      inflation={summary}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Index" }));
  expect(screen.getByText("Index")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-msci_acwi")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-sp500")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-vix")).toBeInTheDocument();
  expect(screen.getByTestId("selected-market-chart-panel")).toBeInTheDocument();
  expect(screen.queryByText("Tabell")).not.toBeInTheDocument();
});

test("clicking KPI card updates selected market chart panel", () => {
  const commodities = {
    ...summary,
    items: [
      { ...summary.items[0], id: "brent", name: "Brentolja" },
      { ...summary.items[0], id: "gold", name: "Guld" },
    ],
  };

  render(
    <DashboardView
      commodities={commodities}
      mag7={summary}
      inflation={summary}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );

  expect(screen.getByTestId("selected-market-chart-panel")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("kpi-card-gold"));
  expect(screen.getByRole("heading", { name: "Guld" })).toBeInTheDocument();
});

test("selected market chart shows weekly ticks and price levels", () => {
  const commodities = {
    ...summary,
    items: [
      {
        ...summary.items[0],
        sparkline: [
          { t: "2026-02-02T10:00:00Z", v: 80 },
          { t: "2026-02-09T10:00:00Z", v: 82 },
          { t: "2026-02-16T10:00:00Z", v: 84 },
        ],
      },
    ],
  };

  render(
    <DashboardView
      commodities={commodities}
      mag7={summary}
      inflation={summary}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );

  expect(screen.getByText("v06")).toBeInTheDocument();
  expect(screen.getByText("v07")).toBeInTheDocument();
  expect(screen.getByText("v08")).toBeInTheDocument();
  expect(screen.getByText("84.00")).toBeInTheDocument();
  expect(screen.getByText("82.00")).toBeInTheDocument();
  expect(screen.getByText("80.00")).toBeInTheDocument();
});

test("orders commodity KPI cards with gold silver copper first row and zinc first in second row", () => {
  const commodities = {
    ...summary,
    items: [
      { ...summary.items[0], id: "brent", name: "Brentolja" },
      { ...summary.items[0], id: "wti", name: "WTI-olja" },
      { ...summary.items[0], id: "gold", name: "Guld" },
      { ...summary.items[0], id: "silver", name: "Silver" },
      { ...summary.items[0], id: "copper", name: "Koppar" },
      { ...summary.items[0], id: "zinc", name: "Zink" },
    ],
  };

  render(
    <DashboardView
      commodities={commodities}
      mag7={summary}
      inflation={summary}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );

  const cards = screen.getAllByTestId(/^kpi-card-/);
  expect(cards[0]).toHaveAttribute("data-testid", "kpi-card-gold");
  expect(cards[1]).toHaveAttribute("data-testid", "kpi-card-silver");
  expect(cards[2]).toHaveAttribute("data-testid", "kpi-card-copper");
  expect(cards[3]).toHaveAttribute("data-testid", "kpi-card-zinc");
});


test("renders shared inflation graph and allows range switch", () => {
  const inflation = {
    ...summary,
    items: [
      { ...summary.items[0], id: "inflation_se", name: "Sverige KPI" },
      { ...summary.items[0], id: "inflation_us", name: "USA KPI" },
    ],
  };
  const rangeSeries = {
    "3m": {
      inflation_se: [{ t: "2026-01-01T00:00:00Z", v: 1.0 }, { t: "2026-02-01T00:00:00Z", v: 1.2 }],
      inflation_us: [{ t: "2026-01-01T00:00:00Z", v: 2.0 }, { t: "2026-02-01T00:00:00Z", v: 2.1 }],
    },
    "6m": {
      inflation_se: [{ t: "2025-08-01T00:00:00Z", v: 0.8 }, { t: "2026-02-01T00:00:00Z", v: 1.2 }],
      inflation_us: [{ t: "2025-08-01T00:00:00Z", v: 1.9 }, { t: "2026-02-01T00:00:00Z", v: 2.1 }],
    },
    "1y": {
      inflation_se: [{ t: "2025-02-01T00:00:00Z", v: 0.6 }, { t: "2026-02-01T00:00:00Z", v: 1.2 }],
      inflation_us: [{ t: "2025-02-01T00:00:00Z", v: 1.7 }, { t: "2026-02-01T00:00:00Z", v: 2.1 }],
    },
  };

  render(
    <DashboardView
      commodities={summary}
      mag7={summary}
      inflation={inflation}
      inflationSeriesByRange={rangeSeries}
      warnings={[]}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Inflation" }));

  expect(screen.getByText("Inflation: Sverige & USA")).toBeInTheDocument();
  expect(screen.getByTestId("inflation-shared-chart-panel")).toBeInTheDocument();
  expect(screen.getByTestId("inflation-line-sweden")).toBeInTheDocument();
  expect(screen.getByTestId("inflation-line-usa")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "6 man" }));
  expect(screen.getByRole("button", { name: "6 man" })).toHaveAttribute("data-active", "true");
  fireEvent.click(screen.getByRole("button", { name: "12 man" }));
  expect(screen.getByRole("button", { name: "12 man" })).toHaveAttribute("data-active", "true");
});

test("opens slideshow with interval choice, table rows and controls", () => {
  const commodities = {
    ...summary,
    items: [
      { ...summary.items[0], id: "gold", name: "Guld" },
      { ...summary.items[0], id: "brent", name: "Brentolja" },
    ],
  };
  const mag7 = {
    ...summary,
    items: [{ ...summary.items[0], id: "aapl", name: "Apple" }],
  };
  const inflation = {
    ...summary,
    items: [
      { ...summary.items[0], id: "inflation_se", name: "Sverige KPI" },
      { ...summary.items[0], id: "inflation_us", name: "USA KPI" },
    ],
  };
  const rangeSeries = {
    "3m": {},
    "6m": {},
    "1y": {
      inflation_se: [{ t: "2025-02-01T00:00:00Z", v: 0.6 }, { t: "2026-02-01T00:00:00Z", v: 1.2 }],
      inflation_us: [{ t: "2025-02-01T00:00:00Z", v: 1.7 }, { t: "2026-02-01T00:00:00Z", v: 2.1 }],
    },
  };

  render(
    <DashboardView
      commodities={commodities}
      mag7={mag7}
      indexes={{
        ...summary,
        items: [{ ...summary.items[0], id: "msci_acwi", name: "MSCI ACWI" }],
      }}
      inflation={inflation}
      inflationSeriesByRange={rangeSeries}
      warnings={[]}
    />,
  );

  expect(screen.getByRole("combobox", { name: "Bildspelsintervall" })).toHaveValue("10");
  fireEvent.change(screen.getByRole("combobox", { name: "Bildspelsintervall" }), { target: { value: "15" } });
  fireEvent.click(screen.getByRole("button", { name: "Bildspel" }));

  const overlay = screen.getByTestId("slideshow-overlay");
  expect(within(overlay).getByRole("heading", { name: "Guld" })).toBeInTheDocument();
  expect(within(overlay).getByText("15 s")).toBeInTheDocument();

  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  expect(within(overlay).getByRole("heading", { name: "Brentolja" })).toBeInTheDocument();

  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  expect(within(overlay).getByRole("heading", { name: "Apple" })).toBeInTheDocument();

  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  expect(within(overlay).getByRole("heading", { name: "MSCI ACWI" })).toBeInTheDocument();

  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  expect(within(overlay).getByRole("heading", { name: "Inflation: Sverige & USA" })).toBeInTheDocument();

  fireEvent.click(within(overlay).getByRole("button", { name: "Pausa" }));
  expect(within(overlay).getByText("Pausad")).toBeInTheDocument();
  fireEvent.click(within(overlay).getByRole("button", { name: "Föregående" }));
  expect(within(overlay).getByRole("heading", { name: "MSCI ACWI" })).toBeInTheDocument();
  fireEvent.click(within(overlay).getByRole("button", { name: "Stäng" }));
  expect(screen.queryByTestId("slideshow-overlay")).not.toBeInTheDocument();
});
