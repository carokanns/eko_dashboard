import { NextRequest, NextResponse } from "next/server";

import {
  DASHBOARD_SESSION_COOKIE,
  dashboardPassword,
  isValidDashboardPassword,
  sessionValueForPassword,
} from "@/lib/auth";

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => null)) as { password?: string } | null;
  const password = body?.password ?? "";

  if (!isValidDashboardPassword(password)) {
    return NextResponse.json({ detail: "Invalid password" }, { status: 401 });
  }

  const configuredPassword = dashboardPassword() ?? password;
  const response = NextResponse.json({ ok: true });
  response.cookies.set(DASHBOARD_SESSION_COOKIE, sessionValueForPassword(configuredPassword), {
    httpOnly: true,
    maxAge: 60 * 60 * 24 * 30,
    path: "/",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
  });
  return response;
}
