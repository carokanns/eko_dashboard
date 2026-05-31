import { createHash, timingSafeEqual } from "node:crypto";

export const DASHBOARD_SESSION_COOKIE = "dashboard_session";

export function dashboardPassword(): string | null {
  const password = process.env.DASHBOARD_PASSWORD?.trim();
  return password || null;
}

export function sessionValueForPassword(password: string): string {
  return createHash("sha256").update(password).digest("hex");
}

export function isValidSessionValue(value: string | undefined): boolean {
  const password = dashboardPassword();
  if (!password) return true;
  if (!value) return false;

  const expected = Buffer.from(sessionValueForPassword(password));
  const actual = Buffer.from(value);
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}

export function isValidDashboardPassword(candidate: string): boolean {
  const password = dashboardPassword();
  if (!password) return true;

  const expected = Buffer.from(password);
  const actual = Buffer.from(candidate);
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}
