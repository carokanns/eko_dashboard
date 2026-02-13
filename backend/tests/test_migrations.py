from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.db.migrations import upgrade_to_head
from app.db.session import reset_database_engine


def test_upgrade_to_head_creates_schema(monkeypatch, tmp_path):
    db_file = tmp_path / "migration-check.db"
    monkeypatch.setenv("APP_DATABASE_URL", f"sqlite:///{db_file}")
    reset_database_engine()

    upgrade_to_head()

    engine = create_engine(f"sqlite:///{db_file}")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "alembic_version" in tables
    assert "instrument" in tables
    assert "quote_snapshot" in tables
    assert "series_point" in tables
    assert "job_run" in tables
    assert "provider_event" in tables

    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "20260214_0001"

    engine.dispose()
    if Path(db_file).exists():
        Path(db_file).unlink()
