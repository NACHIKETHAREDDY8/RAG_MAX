from collections.abc import Mapping
from typing import Any


def validate_filters(filters: Mapping[str, Any] | None) -> None:
    """Reject filters that are not a mapping of metadata field to value."""
    if filters is not None and not isinstance(filters, Mapping):
        raise TypeError("filters must be a mapping of metadata field to value.")


def matches_filters(metadata: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
    """Return True when metadata has every filter field with an equal value.

    A record missing a filtered field never matches, so records without a
    tenant_id cannot leak into a tenant-filtered search.
    """
    return all(
        field in metadata and metadata[field] == value
        for field, value in filters.items()
    )
