import { NextRequest, NextResponse } from "next/server";

const backendBaseUrl = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
const backendApiToken = process.env.BACKEND_API_TOKEN;

export async function GET(request: NextRequest, context: { params: Promise<{ slug: string[] }> }) {
  const { slug } = await context.params;
  const backendPath = slug.join("/");
  const search = request.nextUrl.search;
  const backendUrl = `${backendBaseUrl}/api/${backendPath}${search}`;
  const headers = new Headers();
  if (backendApiToken) {
    headers.set("x-dashboard-token", backendApiToken);
  }

  try {
    const response = await fetch(backendUrl, { cache: "no-store", headers });
    const contentType = response.headers.get("content-type") ?? "application/json";
    const body = await response.text();

    return new NextResponse(body, {
      status: response.status,
      headers: {
        "content-type": contentType,
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        detail: "Proxy request failed.",
        error: error instanceof Error ? error.message : "unknown",
      },
      { status: 502 },
    );
  }
}
