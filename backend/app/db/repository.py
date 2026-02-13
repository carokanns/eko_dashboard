from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.provider_monitor import provider_monitor
from app.db.models import Instrument, JobRun, ProviderEvent, QuoteSnapshot, SeriesPoint
from app.models.summary import SparkPoint, SummaryItem


def upsert_instruments(session: Session, instruments) -> dict[str, int]:
    existing = {
        row.instrument_key: row
        for row in session.query(Instrument).filter(Instrument.instrument_key.in_([i.id for i in instruments]))
    }
    mapping: dict[str, int] = {}

    for item in instruments:
        row = existing.get(item.id)
        if row is None:
            row = Instrument(
                instrument_key=item.id,
                name_sv=item.name_sv,
                ticker=item.ticker,
                module=item.module,
                unit_label=item.unit_label,
                price_type=item.price_type,
                sort_order=item.sort_order,
            )
            session.add(row)
            session.flush()
        else:
            row.name_sv = item.name_sv
            row.ticker = item.ticker
            row.module = item.module
            row.unit_label = item.unit_label
            row.price_type = item.price_type
            row.sort_order = item.sort_order
        mapping[item.id] = row.id

    return mapping


def store_summary_items(
    session: Session,
    instrument_ids: dict[str, int],
    items: list[SummaryItem],
    fetched_at: datetime,
) -> None:
    for item in items:
        instrument_id = instrument_ids.get(item.id)
        if instrument_id is None:
            continue
        session.add(
            QuoteSnapshot(
                instrument_id=instrument_id,
                fetched_at=fetched_at,
                timestamp_local=item.timestamp_local,
                last=item.last,
                day_abs=item.day_abs,
                day_pct=item.day_pct,
                w1_pct=item.w1_pct,
                ytd_pct=item.ytd_pct,
                y1_pct=item.y1_pct,
                is_stale=item.is_stale,
            )
        )


def replace_series_points(
    session: Session,
    instrument_id: int,
    series_type: str,
    range_key: str,
    points: list[SparkPoint],
    fetched_at: datetime,
) -> None:
    session.execute(
        delete(SeriesPoint).where(
            SeriesPoint.instrument_id == instrument_id,
            SeriesPoint.series_type == series_type,
            SeriesPoint.range_key == range_key,
        )
    )
    for point in points:
        session.add(
            SeriesPoint(
                instrument_id=instrument_id,
                series_type=series_type,
                range_key=range_key,
                point_time=point.t,
                value=point.v,
                fetched_at=fetched_at,
            )
        )


def create_job_run(session: Session, job_name: str, started_at: datetime) -> JobRun:
    job = JobRun(job_name=job_name, started_at=started_at, status="running", ok_count=0, fail_count=0)
    session.add(job)
    session.flush()
    return job


def complete_job_run(
    session: Session,
    job_run: JobRun,
    *,
    finished_at: datetime,
    status: str,
    ok_count: int,
    fail_count: int,
    notes: str | None,
) -> None:
    job_run.finished_at = finished_at
    job_run.status = status
    job_run.ok_count = ok_count
    job_run.fail_count = fail_count
    job_run.notes = notes


def record_provider_stats_snapshot(session: Session, created_at: datetime) -> None:
    stats = provider_monitor.snapshot()
    for provider, values in stats.items():
        session.add(
            ProviderEvent(
                provider=provider,
                event_type="stats_snapshot",
                message=(
                    f"attempts={values.get('attempts', 0)} "
                    f"success={values.get('success', 0)} fail={values.get('fail', 0)} "
                    f"retries={values.get('retries', 0)}"
                ),
                created_at=created_at,
            )
        )
