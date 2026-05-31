import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { LoginForm } from "./login-form";

const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh,
  }),
}));

beforeEach(() => {
  refresh.mockClear();
  vi.unstubAllGlobals();
});

test("shows error when password is rejected", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: false }),
  );

  render(<LoginForm />);
  fireEvent.change(screen.getByLabelText("Lösenord"), { target: { value: "fel" } });
  fireEvent.click(screen.getByRole("button", { name: "Öppna dashboard" }));

  expect(await screen.findByText("Fel lösenord.")).toBeInTheDocument();
  expect(refresh).not.toHaveBeenCalled();
});

test("refreshes dashboard after accepted password", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true }),
  );

  render(<LoginForm />);
  fireEvent.change(screen.getByLabelText("Lösenord"), { target: { value: "ratt" } });
  fireEvent.click(screen.getByRole("button", { name: "Öppna dashboard" }));

  await waitFor(() => expect(refresh).toHaveBeenCalled());
});
