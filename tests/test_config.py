"""Tests for the central configuration."""

from pathlib import Path

import pytest

from src.config import PipelineConfig


def test_default_raw_files_exist() -> None:
    config = PipelineConfig()
    assert config.customers_path.exists()
    assert config.orders_path.exists()


def test_paths_can_be_overridden(tmp_path: Path) -> None:
    config = PipelineConfig(lakehouse_dir=tmp_path / "out")
    assert config.lakehouse_dir == tmp_path / "out"


def test_misspelled_timezone_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown time zone"):
        PipelineConfig(default_timezone="Europe/Berln")
