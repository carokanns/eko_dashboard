import { NextRequest } from "next/server";
import { afterEach, expect, test, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.resetModules();
});

test("proxies dashboard API requests with backend token", async () => {
  vi.stubEnv("API_BASE_URL", "https://backend.example.com");
  vi.stubEnv("BACKEND_API_TOKEN", "secret-token");
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), {
      headers: { "content-type": "application/json" },
      status: 200,
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  const { GET } = await import("./route");
  const request = new NextRequest("http://localhost/api/dashboard/indexes/summary?range=1m");
  const response = await GET(request, { params: Promise.resolve({ slug: ["indexes", "summary"] }) });

  expect(response.status).toBe(200);
  expect(fetchMock).toHaveBeenCalledWith(
    "https://backend.example.com/api/indexes/summary?range=1m",
    expect.objectContaining({
      cache: "no-store",
      headers: expect.any(Headers),
    }),
  );
  const headers = fetchMock.mock.calls[0][1].headers as Headers;
  expect(headers.get("x-dashboard-token")).toBe("secret-token");
});
