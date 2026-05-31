"use client";

import { FormEvent, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

export function LoginForm() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ password }),
    });

    if (!response.ok) {
      setError("Fel lösenord.");
      return;
    }

    startTransition(() => {
      router.refresh();
    });
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <section className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center">
        <form className="card-surface flex flex-col gap-5 p-6" onSubmit={handleSubmit}>
          <div>
            <p className="kpi-subtle">Ekonomi Dashboard</p>
            <h1 className="section-title mt-2 text-3xl font-semibold text-strong">Logga in</h1>
          </div>
          <label className="flex flex-col gap-2 text-sm font-semibold text-strong">
            Lösenord
            <input
              className="rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-4 py-3 text-base text-strong outline-none transition focus:border-[var(--accent-2)]"
              autoComplete="current-password"
              autoFocus
              name="password"
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>
          {error ? <p className="warning-surface rounded-lg border px-4 py-3 text-sm">{error}</p> : null}
          <button
            className="rounded-lg bg-[var(--accent-3)] px-4 py-3 font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isPending || !password}
            type="submit"
          >
            {isPending ? "Loggar in..." : "Öppna dashboard"}
          </button>
        </form>
      </section>
    </main>
  );
}
