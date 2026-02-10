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
  render(<DashboardView commodities={summary} mag7={summary} inflation={summary} warnings={[]} />);
  expect(screen.getByText("Marknadsoversikt")).toBeInTheDocument();
  expect(screen.getAllByText("Brentolja").length).toBeGreaterThan(0);
  expect(screen.getAllByText("82.50").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Fresh")[0]).toBeInTheDocument();
});

test("renders stale indicator and warning fallback", () => {
  render(<DashboardView commodities={null} mag7={null} inflation={null} warnings={["Kunde inte hamta ravaror just nu."]} />);
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

  render(<DashboardView commodities={mixed} mag7={summary} inflation={summary} warnings={[]} />);
  expect(screen.getAllByText("Live").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Stale").length).toBeGreaterThan(0);
});

test("handles cached and invalid fetched_at without crashing", () => {
  const cachedWithInvalidDate = buildSummary({ cached: true, fetched_at: "not-a-date" });
  render(<DashboardView commodities={cachedWithInvalidDate} mag7={null} inflation={null} warnings={[]} />);
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
  render(<DashboardView commodities={commodities} mag7={null} inflation={null} warnings={[]} />);
  fireEvent.change(screen.getAllByPlaceholderText("Sok i ravaror")[0], { target: { value: "guld" } });
  expect(screen.getAllByText("Guld").length).toBeGreaterThan(0);
  expect(screen.queryByText("Brentolja")).not.toBeInTheDocument();
});

test("sorts Mag7 by YTD when toggle is clicked", () => {
  const mag7 = {
    ...summary,
    items: [
      { ...summary.items[0], id: "aapl", name: "Apple", ytd_pct: 2.0 },
      { ...summary.items[0], id: "nvda", name: "Nvidia", ytd_pct: 9.0 },
    ],
  };
  render(<DashboardView commodities={summary} mag7={mag7} inflation={summary} warnings={[]} />);
  let mag7Rows = screen.getAllByTestId(/^mag7-row-/);
  expect(mag7Rows[0]).toHaveAttribute("data-testid", "mag7-row-nvda");
  fireEvent.click(screen.getByRole("button", { name: /Sortera YTD/i }));
  mag7Rows = screen.getAllByTestId(/^mag7-row-/);
  expect(mag7Rows[0]).toHaveAttribute("data-testid", "mag7-row-aapl");
});

test("shows top 6 Mag7 companies in KPI cards when Mag 7 tab is selected", () => {
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

  render(<DashboardView commodities={summary} mag7={mag7} inflation={summary} warnings={[]} />);
  fireEvent.click(screen.getByRole("button", { name: "Mag 7" }));

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

  render(<DashboardView commodities={commodities} mag7={mag7} inflation={summary} warnings={[]} />);
  expect(screen.getByTestId("table-row-brent")).toBeInTheDocument();
  expect(screen.queryByTestId("table-row-aapl")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Mag 7" }));
  expect(screen.getByText("MAG 7")).toBeInTheDocument();
  expect(screen.getByTestId("table-row-aapl")).toBeInTheDocument();
  expect(screen.queryByTestId("table-row-brent")).not.toBeInTheDocument();
});


test("renders inflation cards for Sweden and USA", () => {
  const inflation = {
    ...summary,
    items: [
      { ...summary.items[0], id: "inflation_se", name: "Sverige KPI" },
      { ...summary.items[0], id: "inflation_us", name: "USA KPI" },
    ],
  };

  render(<DashboardView commodities={summary} mag7={summary} inflation={inflation} warnings={[]} />);
  fireEvent.click(screen.getByRole("button", { name: "Inflation" }));

  expect(screen.getByText("Inflation: Sverige & USA")).toBeInTheDocument();
  expect(screen.getByTestId("inflation-card-inflation_se")).toBeInTheDocument();
  expect(screen.getByTestId("inflation-card-inflation_us")).toBeInTheDocument();
});

test("charts tab switches selected graph panel", () => {
  const inflation = {
    ...summary,
    items: [
      { ...summary.items[0], id: "inflation_se", name: "Sverige KPI" },
      { ...summary.items[0], id: "inflation_us", name: "USA KPI" },
    ],
  };

  render(<DashboardView commodities={summary} mag7={summary} inflation={inflation} warnings={[]} />);
  fireEvent.click(screen.getByRole("button", { name: "Grafer" }));

  expect(screen.getByTestId("selected-chart-panel")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "USA" }));
  expect(screen.getByText("USA inflation")).toBeInTheDocument();
});
