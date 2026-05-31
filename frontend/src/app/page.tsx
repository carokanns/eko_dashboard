import { cookies } from "next/headers";

import { DASHBOARD_SESSION_COOKIE, isValidSessionValue } from "@/lib/auth";

import { DashboardPage } from "./dashboard-page";
import { LoginForm } from "./login-form";

export default async function Home() {
  const cookieStore = await cookies();
  const sessionValue = cookieStore.get(DASHBOARD_SESSION_COOKIE)?.value;

  if (!isValidSessionValue(sessionValue)) {
    return <LoginForm />;
  }

  return <DashboardPage />;
}
