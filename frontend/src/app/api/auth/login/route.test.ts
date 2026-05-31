import { NextRequest } from "next/server";
import { afterEach, expect, test, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
});

test("rejects invalid dashboard password", async () => {
  vi.stubEnv("DASHBOARD_PASSWORD", "secret");
  const { POST } = await import("./route");
  const request = new NextRequest("http://localhost/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ password: "wrong" }),
  });

  const response = await POST(request);
  expect(response.status).toBe(401);
});

test("sets session cookie for valid dashboard password", async () => {
  vi.stubEnv("DASHBOARD_PASSWORD", "secret");
  const { POST } = await import("./route");
  const request = new NextRequest("http://localhost/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ password: "secret" }),
  });

  const response = await POST(request);
  expect(response.status).toBe(200);
  expect(response.headers.get("set-cookie")).toContain("dashboard_session=");
  expect(response.headers.get("set-cookie")).toContain("HttpOnly");
});
