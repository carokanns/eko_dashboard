import { fireEvent, render, screen } from "@testing-library/react";
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
  expect(screen.getByText("Marknadsoversikt")).toBeInTheDocument();
  expect(screen.getAllByText("Brentolja").length).toBeGreaterThan(0);
  expect(screen.getAllByText("82.50").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Fresh")[0]).toBeInTheDocument();
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
  expect(screen.getAllByText("Partial").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Offline").length).toBeGreaterThan(0);
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

test("filters items based on search input", () => {
  const commodities = {
    ...summary,
    items: [
      summary.items[0],
      {
        ...summary.items[0],
        id: "gold",
        name: "Guld",
      },
    ],
  };
  render(
    <DashboardView
      commodities={commodities}
      mag7={null}
      inflation={null}
      inflationSeriesByRange={inflationSeriesByRange}
      warnings={[]}
    />,
  );
  fireEvent.change(screen.getAllByPlaceholderText("Sok i ravaror")[0], { target: { value: "guld" } });
  expect(screen.getAllByText("Guld").length).toBeGreaterThan(0);
  expect(screen.queryByText("Brentolja")).not.toBeInTheDocument();
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
