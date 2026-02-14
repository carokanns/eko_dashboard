#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class Assessment:
    score: int
    level: str
    summary: str
    reasons: list[str]
    fetched_at: str | None
    data_points: dict[str, Any]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # SQLite may store timestamps without explicit timezone.
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fetch_latest_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    sql = """
    WITH latest AS (
      SELECT instrument_id, MAX(fetched_at) AS max_fetched_at
      FROM quote_snapshot
      GROUP BY instrument_id
    )
    SELECT
      i.instrument_key,
      i.name_sv,
      i.module,
      q.fetched_at,
      q.last,
      q.day_pct,
      q.ytd_pct,
      q.y1_pct,
      q.is_stale
    FROM quote_snapshot q
    JOIN instrument i ON i.id = q.instrument_id
    JOIN latest l
      ON l.instrument_id = q.instrument_id
     AND l.max_fetched_at = q.fetched_at
    ORDER BY i.module, i.sort_order;
    """
    return conn.execute(sql).fetchall()


def _pick(rows: list[sqlite3.Row], key: str) -> sqlite3.Row | None:
    for row in rows:
        if row["instrument_key"] == key:
            return row
    return None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def assess(rows: list[sqlite3.Row]) -> Assessment:
    if not rows:
        return Assessment(
            score=0,
            level="okänt",
            summary="Ingen snapshot-data hittades i databasen.",
            reasons=["Kör schedulern först för att fylla quote_snapshot."],
            fetched_at=None,
            data_points={},
        )

    latest_dt = max((_parse_dt(row["fetched_at"]) for row in rows), default=None)
    fetched_at = latest_dt.isoformat() if latest_dt else None

    score = 0
    reasons: list[str] = []
    data_points: dict[str, Any] = {}

    inflation_us = _pick(rows, "inflation_us")
    if inflation_us and inflation_us["last"] is not None:
        us_cpi = float(inflation_us["last"])
        data_points["inflation_us_yoy"] = us_cpi
        if us_cpi <= 2.5:
            score += 2
            reasons.append(f"USA KPI är låg/modererad ({us_cpi:.2f}%), vilket stödjer mjuklandning.")
        elif us_cpi <= 3.5:
            score += 0
            reasons.append(f"USA KPI är hanterbar men över idealnivå ({us_cpi:.2f}%).")
        else:
            score -= 2
            reasons.append(f"USA KPI är hög ({us_cpi:.2f}%), vilket ökar ränte-/tillväxtrisk.")
    else:
        reasons.append("USA KPI saknas i senaste snapshot.")

    mag7_rows = [row for row in rows if row["module"] == "mag7"]
    mag7_day = [float(row["day_pct"]) for row in mag7_rows if row["day_pct"] is not None]
    mag7_ytd = [float(row["ytd_pct"]) for row in mag7_rows if row["ytd_pct"] is not None]
    if mag7_rows:
        pos = len([v for v in mag7_day if v > 0])
        breadth = pos / len(mag7_rows)
        avg_day = _mean(mag7_day)
        avg_ytd = _mean(mag7_ytd)
        data_points["mag7_breadth_positive_share"] = round(breadth, 3)
        data_points["mag7_avg_day_pct"] = None if avg_day is None else round(avg_day, 3)
        data_points["mag7_avg_ytd_pct"] = None if avg_ytd is None else round(avg_ytd, 3)

        if breadth >= 0.6:
            score += 1
            reasons.append(f"Mag7-bredden är stark ({pos}/{len(mag7_rows)} positiva i dag).")
        elif breadth <= 0.4:
            score -= 1
            reasons.append(f"Mag7-bredden är svag ({pos}/{len(mag7_rows)} positiva i dag).")
        else:
            reasons.append(f"Mag7-bredden är blandad ({pos}/{len(mag7_rows)} positiva i dag).")

        if avg_ytd is not None:
            if avg_ytd >= 10:
                score += 1
                reasons.append(f"Mag7 årsstart-trend är stark (snitt YTD {avg_ytd:.1f}%).")
            elif avg_ytd <= -5:
                score -= 1
                reasons.append(f"Mag7 årsstart-trend är svag (snitt YTD {avg_ytd:.1f}%).")
    else:
        reasons.append("Mag7-data saknas i senaste snapshot.")

    brent = _pick(rows, "brent")
    wti = _pick(rows, "wti")
    copper = _pick(rows, "copper")

    if brent and brent["last"] is not None:
        brent_last = float(brent["last"])
        data_points["brent_usd"] = brent_last
        if brent_last >= 95:
            score -= 1
            reasons.append(f"Brent är hög ({brent_last:.2f}), inflationsrisk upp.")
        elif brent_last <= 60:
            score += 1
            reasons.append(f"Brent är låg ({brent_last:.2f}), dämpar kostnadstryck.")

    if wti and wti["last"] is not None:
        data_points["wti_usd"] = float(wti["last"])

    if copper and copper["day_pct"] is not None:
        copper_day = float(copper["day_pct"])
        data_points["copper_day_pct"] = copper_day
        if copper_day > 1.0:
            score += 1
            reasons.append(f"Koppar stiger tydligt i dag ({copper_day:.2f}%), stöd för cyklisk aktivitet.")
        elif copper_day < -1.0:
            score -= 1
            reasons.append(f"Koppar faller tydligt i dag ({copper_day:.2f}%), svagare tillväxtsignal.")

    stale_count = len([row for row in rows if row["is_stale"]])
    data_points["stale_count"] = stale_count
    if stale_count > 0:
        reasons.append(f"Datakvalitet: {stale_count} instrument markerade som stale.")

    if score >= 3:
        level = "positivt"
        summary = "Övergripande läge i USA ser konstruktivt ut med risk-on bias."
    elif score <= -2:
        level = "försiktigt"
        summary = "Övergripande läge i USA ser skört ut med ökad makrorisk."
    else:
        level = "blandat"
        summary = "Övergripande läge i USA är blandat utan tydlig regimdominans."

    return Assessment(
        score=score,
        level=level,
        summary=summary,
        reasons=reasons,
        fetched_at=fetched_at,
        data_points=data_points,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Läser dashboard-databasen och ger ett enkelt makro-omdöme för USA."
    )
    parser.add_argument(
        "--db-path",
        default="backend/data/dashboard.db",
        help="Sökväg till SQLite-databasen.",
    )
    parser.add_argument(
        "--format",
        choices=("md", "text", "json"),
        default="md",
        help="Utskriftsformat. Standard: md.",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        raise SystemExit(f"Databasfil saknas: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = _fetch_latest_rows(conn)
    finally:
        conn.close()

    result = assess(rows)

    if args.format == "json":
        print(
            json.dumps(
                {
                    "score": result.score,
                    "level": result.level,
                    "summary": result.summary,
                    "fetched_at": result.fetched_at,
                    "reasons": result.reasons,
                    "data_points": result.data_points,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.format == "text":
        print("USA makro-omdöme")
        print(f"Nivå: {result.level} (score {result.score})")
        if result.fetched_at:
            print(f"Senaste datahämtning: {result.fetched_at}")
        print(f"Sammanfattning: {result.summary}")
        print("Drivare:")
        for reason in result.reasons:
            print(f"- {reason}")
        return 0

    print("# USA makro-omdöme")
    print("")
    print(f"- **Nivå:** `{result.level}` (score `{result.score}`)")
    if result.fetched_at:
        print(f"- **Senaste datahämtning:** `{result.fetched_at}`")
    print(f"- **Sammanfattning:** {result.summary}")
    print("")
    print("## Drivare")
    print("")
    for reason in result.reasons:
        print(f"- {reason}")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
