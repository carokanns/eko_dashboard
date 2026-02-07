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
  render(<DashboardView commodities={summary} mag7={summary} warnings={[]} />);
  expect(screen.getByText("Marknadsoversikt")).toBeInTheDocument();
  expect(screen.getAllByText("Brentolja").length).toBeGreaterThan(0);
  expect(screen.getAllByText("82.50").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Fresh")[0]).toBeInTheDocument();
});

test("renders stale indicator and warning fallback", () => {
  render(<DashboardView commodities={null} mag7={null} warnings={["Kunde inte hamta ravaror just nu."]} />);
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

  render(<DashboardView commodities={mixed} mag7={summary} warnings={[]} />);
  expect(screen.getAllByText("Live").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Stale").length).toBeGreaterThan(0);
});

test("handles cached and invalid fetched_at without crashing", () => {
  const cachedWithInvalidDate = buildSummary({ cached: true, fetched_at: "not-a-date" });
  render(<DashboardView commodities={cachedWithInvalidDate} mag7={null} warnings={[]} />);
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
  render(<DashboardView commodities={commodities} mag7={null} warnings={[]} />);
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
  render(<DashboardView commodities={summary} mag7={mag7} warnings={[]} />);
  let mag7Rows = screen.getAllByTestId(/^mag7-row-/);
  expect(mag7Rows[0]).toHaveAttribute("data-testid", "mag7-row-nvda");
  fireEvent.click(screen.getByRole("button", { name: /Sortera YTD/i }));
  mag7Rows = screen.getAllByTestId(/^mag7-row-/);
  expect(mag7Rows[0]).toHaveAttribute("data-testid", "mag7-row-aapl");
});
