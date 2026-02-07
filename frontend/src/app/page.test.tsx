import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import Home from "./page";

test("renders dashboard header", () => {
  render(<Home />);
  expect(screen.getByText("Marknadsöversikt")).toBeInTheDocument();
  expect(screen.getByText("Finansiell Dashboard")).toBeInTheDocument();
});
