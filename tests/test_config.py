from pathlib import Path

import pytest

from src.config import ConfigError, load_searches
from src.models import SearchConfig


def test_load_searches_reads_valid_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "searches.yaml"
    config_path.write_text(
        """
searches:
  - search_name: triangle_homes
    enabled: true
    location: "Durham, NC"
    max_price: 450000
    min_beds: 3
    min_baths: 2.5
    property_types:
      - single_family
      - condo
        """.strip(),
        encoding="utf-8",
    )

    searches = load_searches(config_path)

    assert searches == [
        SearchConfig(
            search_name="triangle_homes",
            enabled=True,
            location="Durham, NC",
            max_price=450000,
            min_beds=3.0,
            min_baths=2.5,
            property_types=["single_family", "condo"],
            max_hoa=None,
            min_sqft=None,
            keywords_include=[],
            keywords_exclude=[],
        )
    ]


def test_load_searches_raises_readable_error_for_missing_required_field(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "searches.yaml"
    config_path.write_text(
        """
searches:
  - search_name: raleigh_primary
    enabled: true
    location: "Raleigh, NC"
    min_beds: 3
    min_baths: 2
    property_types:
      - single_family
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(
        ConfigError,
        match="Search 'raleigh_primary' is missing required fields: max_price",
    ):
        load_searches(config_path)


def test_sample_search_config_loads_successfully() -> None:
    searches = load_searches(Path("config/searches.yaml"))

    assert len(searches) == 1
    assert searches[0].search_name == "raleigh_primary"
    assert searches[0].property_types == ["single_family", "townhome"]
