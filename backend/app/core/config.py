from __future__ import annotations

from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, Field


class InstrumentConfig(BaseModel):
    id: str
    name_sv: str
    ticker: str
    unit_label: str | None = None
    price_type: str | None = None
    badge_symbol: str | None = None
    precision: int = 2
    display_group: str | None = None
    sort_order: int = 0
    module: str = Field(default="commodities")


class InstrumentsFile(BaseModel):
    instruments: List[InstrumentConfig]


def repo_root() -> Path:
    # backend/app/core/config.py -> repo root
    return Path(__file__).resolve().parents[3]


def default_config_path() -> Path:
    return repo_root() / "config" / "instruments.example.yaml"


def load_instruments(path: Path | None = None) -> list[InstrumentConfig]:
    config_path = path or default_config_path()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    parsed = InstrumentsFile(**data)
    return parsed.instruments
