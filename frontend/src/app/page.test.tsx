import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { calculateOwnerDayDevelopmentSek, DashboardView } from "./dashboard-view";

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

const inflationSeries: Record<string, { t: string; v: number }[]> = {};

function buildSummary(overrides?: Partial<(typeof summary)["meta"]>) {
  return {
    ...summary,
    meta: {
      ...summary.meta,
      ...overrides,
    },
  };
}

test("calculates owner development from the same one-day movement as the holding", () => {
  const dnbDayAbs = 178.0744 - 178.73756;
  const patCurrentValue = 211751.25;

  expect(calculateOwnerDayDevelopmentSek(dnbDayAbs, 178.0744, patCurrentValue)).toBeCloseTo(-788.57, 2);
});

test("renders dashboard with live values", () => {
  render(
    <DashboardView
      commodities={summary}
      mag7={summary}
      inflation={summary}
      inflationSeries={inflationSeries}
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
      inflationSeries={inflationSeries}
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
      inflationSeries={inflationSeries}
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
      inflationSeries={inflationSeries}
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
      inflationSeries={inflationSeries}
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
      inflationSeries={inflationSeries}
      warnings={[]}
    />,
  );

  expect(screen.queryByPlaceholderText(/Sok i/i)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Råvaror" })).toHaveTextContent("Råvaror: Fresh");
  expect(screen.getByRole("button", { name: "Mag 7" })).toHaveTextContent("Mag 7: Fresh");
  expect(screen.getByRole("button", { name: "Index" })).toHaveTextContent("Index: Offline");
  expect(screen.getByRole("button", { name: "Inflation" })).toHaveTextContent("Inflation: Fresh");
  expect(screen.queryByRole("button", { name: "Min Avanza" })).not.toBeInTheDocument();
});

test("shows Min Avanza tab with portfolio cards and value text when enabled", () => {
  const portfolio = {
    enabled: true,
    holdings: [
      {
        id: "se0000000001",
        name: "Exempelbolag B",
        short_name: "EX B",
        isin: "SE0000000001",
        instrument_type: "STOCK",
        market: "XSTO",
        currency: "SEK",
        quantity: 10,
        current_value: 1500.5,
        acquisition_price_sek: 100,
        acquisition_value: 1000,
        gain_abs: 500.5,
        gain_pct: 50.05,
        ticker: "EX-B.ST",
        chart_source: "direct",
        chart_label: null,
        has_chart: true,
        last: 150,
        day_abs: 1,
        day_pct: 0.67,
        w1_pct: 2,
        ytd_pct: 3,
        y1_pct: 4,
        timestamp_local: "2026-02-07T10:00:00Z",
        is_stale: false,
        levels: {
          target_price: 145,
          stop_price: 120,
          currency: "SEK",
          current_price: 150,
          target_distance: -5,
          target_distance_pct: -3.33,
          stop_distance: 30,
          stop_distance_pct: 20,
          match_source: "ticker",
          source: "manual",
          note: null,
        },
        sparkline: [
          { t: "2026-02-06T10:00:00Z", v: 145 },
          { t: "2026-02-07T10:00:00Z", v: 150 },
        ],
        owners: [
          {
            owner_id: "jp",
            owner_label: "JP",
            current_value: 1000.5,
            acquisition_value: 800,
            gain_abs: 200.5,
            gain_pct: 25.06,
            quantity: 6,
          },
          {
            owner_id: "pat",
            owner_label: "Pat",
            current_value: 500,
            acquisition_value: 200,
            gain_abs: 300,
            gain_pct: 150,
            quantity: 4,
          },
        ],
      },
      {
        id: "se0000000002",
        name: "Exempelfond",
        short_name: "Exempelfond",
        isin: "SE0000000002",
        instrument_type: "FUND",
        market: "FUND",
        currency: "SEK",
        quantity: 2.5,
        current_value: 250,
        acquisition_price_sek: 80,
        acquisition_value: 200,
        gain_abs: 50,
        gain_pct: 25,
        ticker: null,
        chart_source: null,
        chart_label: null,
        has_chart: true,
        last: null,
        day_abs: null,
        day_pct: null,
        w1_pct: null,
        ytd_pct: null,
        y1_pct: null,
        timestamp_local: null,
        is_stale: true,
        is_provisional: true,
        levels: {
          target_price: 140,
          stop_price: 120,
          currency: "SEK",
          current_price: 100,
          target_distance: 40,
          target_distance_pct: 40,
          stop_distance: -20,
          stop_distance_pct: -20,
          match_source: "estimated",
          source: "estimated",
          note: null,
        },
        sparkline: [
          { t: "2026-02-06T10:00:00Z", v: 98 },
          { t: "2026-02-07T10:00:00Z", v: 100 },
        ],
        owners: [
          {
            owner_id: "jp",
            owner_label: "JP",
            current_value: 250,
            acquisition_value: 200,
            gain_abs: 50,
            gain_pct: 25,
            quantity: 2.5,
          },
        ],
      },
    ],
    totals: {
      current_value: 1750.5,
      acquisition_value: 1200,
      gain_abs: 550.5,
      gain_pct: 45.88,
      holding_count: 2,
      chart_count: 2,
    },
    accounts: [
      {
        owner_id: "jp",
        owner_label: "JP",
        total_value: 3234.5,
        bank_value: 1234.5,
        available_for_purchase: 0,
        account_count: 2,
        source_file: "2026-06-11_konto.csv",
      },
      {
        owner_id: "pat",
        owner_label: "Pat",
        total_value: 2500,
        bank_value: 2000,
        available_for_purchase: 500,
        account_count: 2,
        source_file: "2026-06-11_konto.csv",
      },
    ],
    meta: {
      source: "local_avanza_export",
      cached: false,
      fetched_at: "2026-02-07T10:00:00Z",
      exchange_rates: {
        sek_to_thb: {
          base: "SEK",
          quote: "THB",
          rate: 3.5,
          fetched_at: "2026-02-07T10:00:00Z",
          source: "frankfurter",
          ticker: "SEKTHB",
          is_fallback: false,
        },
      },
    },
  };

  render(
    <DashboardView
      commodities={summary}
      mag7={summary}
      inflation={summary}
      portfolio={portfolio}
      inflationSeries={inflationSeries}
      warnings={[]}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Min Avanza" }));
  expect(screen.getByText("Min Avanza")).toBeInTheDocument();
  expect(screen.getByText("1 751 kr")).toBeInTheDocument();
  expect(screen.getByTestId("portfolio-card-se0000000001")).toBeInTheDocument();
  expect(screen.getByTestId("portfolio-card-se0000000002")).toBeInTheDocument();
  expect(within(screen.getByTestId("portfolio-card-se0000000002")).getByText("Preliminär")).toBeInTheDocument();
  expect(within(screen.getByTestId("portfolio-card-se0000000001")).getByText("Mål 145 SEK (-3.33%)")).toHaveClass("change-positive");
  expect(within(screen.getByTestId("portfolio-card-se0000000001")).getByText("Stopp 120 SEK (+20.00%)")).toBeInTheDocument();
  expect(within(screen.getByTestId("portfolio-card-se0000000002")).getByText("Stopp 120 SEK (-20.00%)")).toHaveClass("change-negative");
  expect(screen.getByTestId("selected-portfolio-chart-panel")).toBeInTheDocument();
  expect(screen.getByText("Nuvarande värde:")).toBeInTheDocument();
  expect(screen.getByText("1 001 kr, 500 kr")).toBeInTheDocument();
  expect(screen.getByText("800 kr (+25.06%), 200 kr (+150.00%)")).toBeInTheDocument();
  expect(within(screen.getByTestId("selected-portfolio-chart-panel")).getByText("Nu 150 SEK")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Bildspel" }));
  const overlay = screen.getByTestId("slideshow-overlay");
  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  expect(within(overlay).getByRole("heading", { name: "Min Avanza" })).toBeInTheDocument();
  expect(within(overlay).getByText("Totalt inklusive kontanter")).toBeInTheDocument();
  expect(within(overlay).getByText("JP")).toBeInTheDocument();
  expect(within(overlay).getByText("Pat")).toBeInTheDocument();
  expect(within(overlay).getByText("Inköpsvärde 1 200 kr (+45.88%)")).toBeInTheDocument();
  expect(within(overlay).getByText("Totalt innehav")).toBeInTheDocument();
  expect(within(overlay).getByText("5 485 kr")).toBeInTheDocument();
  expect(within(overlay).getByText("19 198 THB")).toBeInTheDocument();
  expect(within(overlay).getByText("1 SEK = 3,50 THB")).toBeInTheDocument();
  expect(within(overlay).getByText("Varav Bankkonto 1 235 kr")).toBeInTheDocument();
  expect(within(overlay).getByText("Varav Bankkonto 2 000 kr")).toBeInTheDocument();
  expect(within(overlay).getByText("Utv. idag +7 kr")).toBeInTheDocument();
  expect(within(overlay).getByText("Utv. idag +3 kr")).toBeInTheDocument();
  expect(within(overlay).getByText("Tillgängligt för köp 500 kr")).toBeInTheDocument();
  expect(within(overlay).getByText("2 485 kr")).toBeInTheDocument();
  expect(within(overlay).getByText("3 000 kr")).toBeInTheDocument();
  expect(within(overlay).getAllByText("Nuvärde:")).toHaveLength(2);
  expect(within(overlay).getAllByText("Inköpsvärde:")).toHaveLength(2);
  expect(within(overlay).getAllByText("Resultat:")).toHaveLength(2);
  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  expect(within(overlay).getByRole("heading", { name: "Exempelbolag B" })).toBeInTheDocument();
  expect(within(overlay).getByText("1 001 kr, 500 kr")).toBeInTheDocument();
  expect(within(overlay).getByText("Inköpsvärde 1 000 kr (+50.05%)")).toBeInTheDocument();
  expect(within(overlay).getByText("800 kr (+25.06%), 200 kr (+150.00%)")).toBeInTheDocument();
  expect(within(overlay).getByText("Mål 145 SEK (-3.33%)")).toHaveClass("change-positive");
  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  expect(within(overlay).getByRole("heading", { name: "Exempelfond" })).toBeInTheDocument();
  expect(within(overlay).getByText("JP")).toBeInTheDocument();
  expect(within(overlay).getAllByText("250 kr")).toHaveLength(1);
  expect(within(overlay).queryByText("200 kr (+25.00%)")).not.toBeInTheDocument();
});

test("keeps JP and Pat ownership separate for SEB AI in the slideshow", () => {
  const portfolio = {
    enabled: true,
    holdings: [
      {
        ...summary.items[0],
        id: "lu2602444262",
        name: "SEB AI",
        short_name: "SEB AI",
        isin: "LU2602444262",
        instrument_type: "FUND",
        market: "FUND",
        currency: "SEK",
        quantity: 53.05997,
        current_value: 10751.01,
        acquisition_price_sek: 202.6,
        acquisition_value: 10750,
        gain_abs: 1.01,
        gain_pct: 0.01,
        day_abs: 0,
        ticker: null,
        chart_source: null,
        chart_label: null,
        has_chart: false,
        is_provisional: true,
        owners: [
          {
            owner_id: "jp",
            owner_label: "JP",
            current_value: 751.01,
            acquisition_value: 750,
            gain_abs: 1.01,
            gain_pct: 0.13,
            quantity: 3.7065,
          },
          {
            owner_id: "pat",
            owner_label: "Pat",
            current_value: 10000,
            acquisition_value: 10000,
            gain_abs: 0,
            gain_pct: 0,
            quantity: 49.35347,
          },
        ],
      },
    ],
    totals: {
      current_value: 10751.01,
      acquisition_value: 10750,
      gain_abs: 1.01,
      gain_pct: 0.01,
      holding_count: 1,
      chart_count: 0,
    },
    accounts: [
      { owner_id: "jp", owner_label: "JP", total_value: 100, bank_value: 100, available_for_purchase: 0, account_count: 1, source_file: "ledger" },
      { owner_id: "pat", owner_label: "Pat", total_value: 500, bank_value: 200, available_for_purchase: 300, account_count: 2, source_file: "ledger" },
    ],
    meta: { source: "local_avanza_export", cached: false, fetched_at: "2026-07-14T10:00:00Z" },
  };

  render(
    <DashboardView
      commodities={summary}
      mag7={summary}
      inflation={null}
      portfolio={portfolio}
      inflationSeries={{}}
      warnings={[]}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Min Avanza" }));
  expect(screen.getByText("751 kr, 10 000 kr")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Bildspel" }));
  const overlay = screen.getByTestId("slideshow-overlay");
  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));

  const jpCard = within(overlay).getByRole("heading", { name: "JP" }).closest(".card-surface");
  const patCard = within(overlay).getByRole("heading", { name: "Pat" }).closest(".card-surface");
  expect(jpCard).not.toBeNull();
  expect(patCard).not.toBeNull();
  expect(within(jpCard as HTMLElement).getByText("1 innehav")).toBeInTheDocument();
  expect(within(jpCard as HTMLElement).getByText("851 kr")).toBeInTheDocument();
  expect(within(jpCard as HTMLElement).getByText("750 kr")).toBeInTheDocument();
  expect(within(jpCard as HTMLElement).getByText("Utv. idag 0 kr")).toBeInTheDocument();
  expect(within(patCard as HTMLElement).getByText("1 innehav")).toBeInTheDocument();
  expect(within(patCard as HTMLElement).getByText("10 500 kr")).toBeInTheDocument();
  expect(within(patCard as HTMLElement).getByText("Utv. idag 0 kr")).toBeInTheDocument();
  expect(within(patCard as HTMLElement).getAllByText("10 000 kr")).toHaveLength(2);
  expect(within(overlay).getByText("11 351 kr")).toBeInTheDocument();
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
      inflationSeries={inflationSeries}
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
      inflationSeries={inflationSeries}
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
      inflationSeries={inflationSeries}
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
      { ...summary.items[0], id: "msci_thailand", name: "MSCI Thailand", unit: "USD", price_type: "iShares MSCI Thailand ETF-proxy" },
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
      inflationSeries={inflationSeries}
      warnings={[]}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Index" }));
  expect(screen.getByText("Index")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-msci_acwi")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-sp500")).toBeInTheDocument();
  expect(screen.getByTestId("kpi-card-msci_thailand")).toBeInTheDocument();
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
      inflationSeries={inflationSeries}
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
      inflationSeries={inflationSeries}
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
      inflationSeries={inflationSeries}
      warnings={[]}
    />,
  );

  const cards = screen.getAllByTestId(/^kpi-card-/);
  expect(cards[0]).toHaveAttribute("data-testid", "kpi-card-gold");
  expect(cards[1]).toHaveAttribute("data-testid", "kpi-card-silver");
  expect(cards[2]).toHaveAttribute("data-testid", "kpi-card-copper");
  expect(cards[3]).toHaveAttribute("data-testid", "kpi-card-zinc");
});


test("renders market range selector with default range and change handler", () => {
  const onMarketRangeChange = vi.fn();

  render(
    <DashboardView
      commodities={summary}
      mag7={summary}
      inflation={summary}
      marketRange="1m"
      onMarketRangeChange={onMarketRangeChange}
      inflationSeries={inflationSeries}
      warnings={[]}
    />,
  );

  expect(screen.getByRole("button", { name: "1 mån" })).toHaveAttribute("data-active", "true");
  fireEvent.click(screen.getByRole("button", { name: "6 mån" }));
  expect(onMarketRangeChange).toHaveBeenCalledWith("6m");
});

test("renders shared inflation graph with fixed twelve month series", () => {
  const inflation = {
    ...summary,
    items: [
      { ...summary.items[0], id: "inflation_se", name: "Sverige KPI" },
      { ...summary.items[0], id: "inflation_us", name: "USA KPI" },
    ],
  };
  const fixedInflationSeries = {
    inflation_se: [{ t: "2025-02-01T00:00:00Z", v: 0.6 }, { t: "2026-02-01T00:00:00Z", v: 1.2 }],
    inflation_us: [{ t: "2025-02-01T00:00:00Z", v: 1.7 }, { t: "2026-02-01T00:00:00Z", v: 2.1 }],
  };

  render(
    <DashboardView
      commodities={summary}
      mag7={summary}
      inflation={inflation}
      inflationSeries={fixedInflationSeries}
      warnings={[]}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Inflation" }));

  expect(screen.getByText("Inflation: Sverige & USA")).toBeInTheDocument();
  expect(screen.getByTestId("inflation-shared-chart-panel")).toBeInTheDocument();
  expect(screen.getByTestId("inflation-line-sweden")).toBeInTheDocument();
  expect(screen.getByTestId("inflation-line-usa")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "6 man" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "12 man" })).not.toBeInTheDocument();
});

test("opens slideshow with interval choice, table rows and controls", () => {
  const onMarketRangeChange = vi.fn();
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
  const fixedInflationSeries = {
    inflation_se: [{ t: "2025-02-01T00:00:00Z", v: 0.6 }, { t: "2026-02-01T00:00:00Z", v: 1.2 }],
    inflation_us: [{ t: "2025-02-01T00:00:00Z", v: 1.7 }, { t: "2026-02-01T00:00:00Z", v: 2.1 }],
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
      inflationSeries={fixedInflationSeries}
      onMarketRangeChange={onMarketRangeChange}
      warnings={[]}
    />,
  );

  expect(screen.getByRole("combobox", { name: "Bildspelsintervall" })).toHaveValue("10");
  fireEvent.change(screen.getByRole("combobox", { name: "Bildspelsintervall" }), { target: { value: "15" } });
  fireEvent.click(screen.getByRole("button", { name: "Bildspel" }));

  const overlay = screen.getByTestId("slideshow-overlay");
  expect(within(overlay).getByRole("heading", { name: "Guld" })).toBeInTheDocument();
  const overlayInterval = within(overlay).getByRole("combobox", { name: "Bildspelsintervall i bildspel" });
  const overlayRange = within(overlay).getByRole("combobox", { name: "Tidsspann i bildspel" });
  expect(overlayInterval).toHaveValue("15");
  expect(overlayRange).toHaveValue("1m");
  fireEvent.change(overlayInterval, { target: { value: "30" } });
  fireEvent.change(overlayRange, { target: { value: "6m" } });
  expect(overlayInterval).toHaveValue("30");
  expect(onMarketRangeChange).toHaveBeenCalledWith("6m");

  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  expect(within(overlay).getByRole("heading", { name: "Brentolja" })).toBeInTheDocument();

  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  expect(within(overlay).getByRole("heading", { name: "Apple" })).toBeInTheDocument();

  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  expect(within(overlay).getByRole("heading", { name: "MSCI ACWI" })).toBeInTheDocument();

  fireEvent.click(within(overlay).getByRole("button", { name: "Nästa" }));
  expect(within(overlay).getByRole("heading", { name: "Inflation: Sverige & USA" })).toBeInTheDocument();

  fireEvent.click(within(overlay).getByRole("button", { name: "Pausa" }));
  expect(within(overlay).queryByText("Pausad")).not.toBeInTheDocument();
  expect(overlayInterval).toHaveValue("30");
  fireEvent.click(within(overlay).getByRole("button", { name: "Föregående" }));
  expect(within(overlay).getByRole("heading", { name: "MSCI ACWI" })).toBeInTheDocument();
  fireEvent.click(within(overlay).getByRole("button", { name: "Stäng" }));
  expect(screen.queryByTestId("slideshow-overlay")).not.toBeInTheDocument();
});
