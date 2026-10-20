"""Shared fixtures for the simulator tests."""

from pathlib import Path

import pytest

from shared.config import BoxConfig, ProductConfig, load_box_config, load_product_config
from simulator.scenario import Scenario

REFERENCE_CONFIG = Path(__file__).resolve().parent.parent / "config" / "product_team_document.yaml"


@pytest.fixture(scope="session")
def box() -> BoxConfig:
    return load_box_config()


@pytest.fixture(scope="session")
def product() -> ProductConfig:
    """The ACTIVE product profile (config/product_default.yaml)."""
    return load_product_config()


@pytest.fixture(scope="session")
def reference_product() -> ProductConfig:
    """The REFERENCE profile with the team document's values (for the worked examples)."""
    return load_product_config(REFERENCE_CONFIG)


@pytest.fixture
def make_scenario():
    """Build a small scenario with constant 22 C ambient; override any field."""

    def build(**overrides) -> Scenario:
        values = {
            "id": "test",
            "title": "test",
            "description": "test scenario",
            "seed": 1,
            "duration_h": 24,
            "sample_interval_s": 600,
            "ambient": [(0, 22), (24, 22)],
            "events": [],
        }
        values.update(overrides)
        return Scenario(**values)

    return build
