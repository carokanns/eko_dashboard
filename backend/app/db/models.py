from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Instrument(Base):
    __tablename__ = "instrument"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name_sv: Mapped[str] = mapped_column(String(255))
    ticker: Mapped[str] = mapped_column(String(64), index=True)
    module: Mapped[str] = mapped_column(String(32), index=True)
    unit_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class QuoteSnapshot(Base):
    __tablename__ = "quote_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instrument.id", ondelete="CASCADE"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timestamp_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last: Mapped[float | None] = mapped_column(Float, nullable=True)
    day_abs: Mapped[float | None] = mapped_column(Float, nullable=True)
    day_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    w1_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    y1_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=True)

    instrument: Mapped[Instrument] = relationship()


class SeriesPoint(Base):
    __tablename__ = "series_point"
    __table_args__ = (
        UniqueConstraint("instrument_id", "series_type", "range_key", "point_time", name="uq_series_point"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instrument.id", ondelete="CASCADE"), index=True)
    series_type: Mapped[str] = mapped_column(String(32), index=True)
    range_key: Mapped[str] = mapped_column(String(16), index=True)
    point_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    value: Mapped[float] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class JobRun(Base):
    __tablename__ = "job_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    ok_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProviderEvent(Base):
    __tablename__ = "provider_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
