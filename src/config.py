"""YAML configuration loading for search definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.models import SearchConfig

DEFAULT_SEARCHES_PATH = Path("config/searches.yaml")
REQUIRED_SEARCH_FIELDS = (
    "search_name",
    "location",
    "max_price",
    "min_beds",
    "min_baths",
    "property_types",
    "enabled",
)


class ConfigError(ValueError):
    """Raised when the search configuration file is missing or invalid."""


def load_searches(path: str | Path = DEFAULT_SEARCHES_PATH) -> list[SearchConfig]:
    """Load and validate searches from a YAML configuration file."""

    config_path = Path(path)

    if not config_path.exists():
        raise ConfigError(f"Search config file not found: {config_path}")

    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Unable to read search config file: {config_path}") from exc

    try:
        raw_config = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in search config file: {config_path}") from exc

    if raw_config is None:
        raise ConfigError(f"Search config file is empty: {config_path}")

    if not isinstance(raw_config, dict):
        raise ConfigError(
            f"Search config file must contain a top-level mapping: {config_path}"
        )

    raw_searches = raw_config.get("searches")
    if raw_searches is None:
        raise ConfigError(
            f"Search config file must include a top-level 'searches' list: {config_path}"
        )

    if not isinstance(raw_searches, list):
        raise ConfigError(
            f"Search config 'searches' value must be a list: {config_path}"
        )

    searches = [
        _build_search_config(raw_search, index)
        for index, raw_search in enumerate(raw_searches, start=1)
    ]
    _ensure_unique_search_names(searches, config_path)
    return searches


def _ensure_unique_search_names(
    searches: list[SearchConfig],
    config_path: Path,
) -> None:
    seen_search_names: set[str] = set()

    for search in searches:
        if search.search_name in seen_search_names:
            raise ConfigError(
                f"Duplicate search_name '{search.search_name}' found in {config_path}"
            )
        seen_search_names.add(search.search_name)


def _build_search_config(raw_search: Any, index: int) -> SearchConfig:
    if not isinstance(raw_search, dict):
        raise ConfigError(f"Search #{index} must be a mapping of field names to values.")

    missing_fields = [
        field_name for field_name in REQUIRED_SEARCH_FIELDS if field_name not in raw_search
    ]
    label = _search_label(raw_search, index)
    if missing_fields:
        missing_text = ", ".join(missing_fields)
        raise ConfigError(f"{label} is missing required fields: {missing_text}")

    return SearchConfig(
        search_name=_require_string(raw_search["search_name"], "search_name", label),
        enabled=_require_bool(raw_search["enabled"], "enabled", label),
        location=_require_string(raw_search["location"], "location", label),
        max_price=_require_int(raw_search["max_price"], "max_price", label, minimum=1),
        min_beds=_require_number(raw_search["min_beds"], "min_beds", label, minimum=0),
        min_baths=_require_number(
            raw_search["min_baths"], "min_baths", label, minimum=0
        ),
        property_types=_require_string_list(
            raw_search["property_types"],
            "property_types",
            label,
            allow_empty=False,
        ),
        max_hoa=_optional_int(raw_search.get("max_hoa"), "max_hoa", label, minimum=0),
        min_sqft=_optional_int(
            raw_search.get("min_sqft"),
            "min_sqft",
            label,
            minimum=0,
        ),
        keywords_include=_optional_string_list(
            raw_search.get("keywords_include"),
            "keywords_include",
            label,
        ),
        keywords_exclude=_optional_string_list(
            raw_search.get("keywords_exclude"),
            "keywords_exclude",
            label,
        ),
    )


def _search_label(raw_search: dict[str, Any], index: int) -> str:
    raw_search_name = raw_search.get("search_name")
    if isinstance(raw_search_name, str) and raw_search_name.strip():
        return f"Search '{raw_search_name.strip()}'"
    return f"Search #{index}"


def _require_string(value: Any, field_name: str, search_label: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{search_label} field '{field_name}' must be a string.")

    normalized_value = value.strip()
    if not normalized_value:
        raise ConfigError(f"{search_label} field '{field_name}' cannot be empty.")

    return normalized_value


def _require_bool(value: Any, field_name: str, search_label: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{search_label} field '{field_name}' must be true or false.")
    return value


def _require_int(
    value: Any,
    field_name: str,
    search_label: str,
    *,
    minimum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{search_label} field '{field_name}' must be an integer.")

    if value < minimum:
        raise ConfigError(
            f"{search_label} field '{field_name}' must be at least {minimum}."
        )

    return value


def _optional_int(
    value: Any,
    field_name: str,
    search_label: str,
    *,
    minimum: int,
) -> int | None:
    if value is None:
        return None
    return _require_int(value, field_name, search_label, minimum=minimum)


def _require_number(
    value: Any,
    field_name: str,
    search_label: str,
    *,
    minimum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(
            f"{search_label} field '{field_name}' must be a number."
        )

    normalized_value = float(value)
    if normalized_value < minimum:
        raise ConfigError(
            f"{search_label} field '{field_name}' must be at least {minimum}."
        )

    return normalized_value


def _require_string_list(
    value: Any,
    field_name: str,
    search_label: str,
    *,
    allow_empty: bool,
) -> list[str]:
    if not isinstance(value, list):
        raise ConfigError(f"{search_label} field '{field_name}' must be a list.")

    normalized_values = [_normalize_list_item(item, field_name, search_label) for item in value]
    if not allow_empty and not normalized_values:
        raise ConfigError(f"{search_label} field '{field_name}' must not be empty.")

    return normalized_values


def _optional_string_list(
    value: Any,
    field_name: str,
    search_label: str,
) -> list[str]:
    if value is None:
        return []
    return _require_string_list(value, field_name, search_label, allow_empty=True)


def _normalize_list_item(value: Any, field_name: str, search_label: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(
            f"{search_label} field '{field_name}' must contain only strings."
        )

    normalized_value = value.strip()
    if not normalized_value:
        raise ConfigError(
            f"{search_label} field '{field_name}' must not contain empty strings."
        )

    return normalized_value
