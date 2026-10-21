"""Backend settings from config/backend.yaml (Phase 6). Simulation only."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from shared.config import REPO_ROOT, ConfigError, read_yaml_mapping

DEFAULT_BACKEND_PATH = REPO_ROOT / "config" / "backend.yaml"


class BackendConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1)
    sap_adapter: Literal["mock", "sandbox"]
    close_call_percent: float = Field(ge=0, le=10_000, allow_inf_nan=False)
    planner_key_dir: str | None
    default_page_size: int = Field(ge=1)
    max_page_size: int = Field(ge=1)

    def database_path(self) -> Path:
        path = Path(self.database)
        return path if path.is_absolute() else REPO_ROOT / path


def load_backend_config(path: Path | str | None = None) -> BackendConfig:
    raw = read_yaml_mapping(Path(path) if path is not None else DEFAULT_BACKEND_PATH)
    try:
        cfg = BackendConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"invalid backend settings: {exc}") from exc
    if cfg.default_page_size > cfg.max_page_size:
        raise ConfigError("default_page_size must not exceed max_page_size")
    return cfg
