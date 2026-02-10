from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from urllib.parse import urlencode
from urllib.request import urlopen


FRED_GRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


@dataclass
class FredPoint:
    t: datetime
    value: float


def fetch_series(series_id: str) -> list[FredPoint]:
    query = urlencode({"id": series_id})
    with urlopen(f"{FRED_GRAPH_CSV_URL}?{query}", timeout=20) as response:
        payload = response.read().decode("utf-8")

    points: list[FredPoint] = []
    reader = csv.DictReader(StringIO(payload))
    for row in reader:
        value = row.get(series_id)
        if value in (None, "", "."):
            continue
        observation_date = row.get("observation_date")
        if not observation_date:
            continue
        try:
            parsed = datetime.strptime(observation_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            numeric = float(value)
        except ValueError:
            continue
        points.append(FredPoint(t=parsed, value=numeric))
    return points
