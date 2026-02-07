const tabs = [
  { id: "commodities", label: "Råvaror" },
  { id: "mag7", label: "Mag 7" },
  { id: "inflation", label: "Inflation" },
  { id: "charts", label: "Grafer" },
];

const kpis = [
  { name: "Brentolja", unit: "USD/fat", value: "--", change: "--" },
  { name: "WTI-olja", unit: "USD/fat", value: "--", change: "--" },
  { name: "Guld", unit: "USD/uns", value: "--", change: "--" },
  { name: "Silver", unit: "USD/uns", value: "--", change: "--" },
  { name: "Koppar", unit: "USD/pund", value: "--", change: "--" },
  { name: "Zink", unit: "USD/ton", value: "--", change: "--" },
];

export default function Home() {
  return (
    <main className="container-shell">
      <header className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="badge w-fit">Finansiell Dashboard</div>
          <h1 className="section-title text-4xl font-semibold">
            Marknadsöversikt
          </h1>
          <p className="text-sm text-[#5a524a]">
            Snabba KPI:er, tabeller och sparklines med Yahoo Finance (MVP).
          </p>
        </div>
        <div className="card-surface flex flex-col gap-4 p-4 md:flex-row md:items-center">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-[#f28f3b] text-center text-xl font-semibold text-white leading-10">
              E
            </div>
            <div>
              <div className="text-sm font-semibold">Ekonomi Dashboard</div>
              <div className="text-xs text-[#6b625a]">Datakälla: Yahoo</div>
            </div>
          </div>
          <div className="flex-1">
            <input
              className="w-full rounded-full border border-[var(--border)] bg-white px-4 py-2 text-sm"
              placeholder="Sök i aktiv tabell"
            />
          </div>
          <div className="flex items-center gap-2 text-xs text-[#6b625a]">
            <span>Senast uppdaterad</span>
            <span className="font-semibold text-[#2f2720]">--:--</span>
            <span className="badge">Stale</span>
          </div>
        </div>
      </header>

      <section className="mt-10 card-surface p-4">
        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className="tab-pill"
              data-active={tab.id === "commodities"}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="section-title text-2xl">Råvaror</h2>
          <span className="kpi-subtle">KPI-kort</span>
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {kpis.map((kpi) => (
            <article key={kpi.name} className="card-surface p-5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-semibold">{kpi.name}</div>
                  <div className="text-xs text-[#6b625a]">{kpi.unit}</div>
                </div>
                <span className="badge">{kpi.name.slice(0, 2)}</span>
              </div>
              <div className="mt-6 kpi-value">{kpi.value}</div>
              <div className="mt-2 text-sm text-[#2f6f6a]">{kpi.change}</div>
              <div className="mt-4 h-12 rounded-xl bg-[linear-gradient(90deg,#1b2a41,transparent)] opacity-20" />
            </article>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <div className="flex items-center justify-between">
          <h2 className="section-title text-2xl">Tabell</h2>
          <span className="kpi-subtle">RÅVAROR</span>
        </div>
        <div className="mt-4 table-shell">
          <div className="table-head grid grid-cols-7 gap-2 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[#534a42]">
            <div>Råvara</div>
            <div>Senast</div>
            <div>+/-</div>
            <div>1V</div>
            <div>I år</div>
            <div>1 år</div>
            <div>Pristyp</div>
          </div>
          <div className="px-4 py-6 text-sm text-[#6b625a]">
            Data kommer att fyllas från backend när API är kopplat.
          </div>
        </div>
      </section>

      <section className="mt-10 card-surface p-6">
        <h2 className="section-title text-2xl">Mag 7</h2>
        <p className="mt-2 text-sm text-[#6b625a]">
          Tabell med YTD-sortering kommer här.
        </p>
      </section>
    </main>
  );
}
