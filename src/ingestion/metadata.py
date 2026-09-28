"""Metadata attached to every Document of a file."""

import json
from pathlib import Path

from src.ingestion.detection import DetectedType
from src.ingestion.errors import MetadataError

# Fields a <name>.meta.json file next to a document may set. document_id,
# filename, page and source_type are derived from the file itself.
SIDECAR_FIELDS = {"department", "category", "date", "author", "tenant_id", "title"}
SIDECAR_SUFFIX = ".meta.json"


def sidecar_path(file_path: Path) -> Path:
    """Return where the optional metadata file for a document lives."""
    return file_path.with_suffix(SIDECAR_SUFFIX)


def is_sidecar(file_path: Path) -> bool:
    return file_path.name.lower().endswith(SIDECAR_SUFFIX)


def load_sidecar_metadata(file_path: Path) -> dict:
    """Read the metadata file stored next to a document, if there is one."""
    path = sidecar_path(file_path)

    if not path.exists():
        return {}

    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise MetadataError(f"{path.name} is not valid JSON: {error}") from error

    if not isinstance(metadata, dict):
        raise MetadataError(f"{path.name} must contain a JSON object.")

    unknown = set(metadata) - SIDECAR_FIELDS
    if unknown:
        raise MetadataError(
            f"{path.name} has unsupported fields {sorted(unknown)}; "
            f"allowed fields are {sorted(SIDECAR_FIELDS)}."
        )

    for field, value in metadata.items():
        if not isinstance(value, str):
            raise MetadataError(f"{path.name}: {field} must be a string.")

    return metadata


def build_metadata(
    path: Path,
    detected: DetectedType,
    format_metadata: dict,
    file_hash: str,
) -> dict:
    """Combine file facts, what the format records, and the sidecar file.

    Later sources win. The sidecar wins over the format because embedded
    authors are often just the account name of whoever exported the file.
    """
    return {
        "file_size": path.stat().st_size,
        "source_type": detected.file_type.value,
        "mime_type": detected.mime_type,
        "file_hash": file_hash,
        **format_metadata,
        **load_sidecar_metadata(path),
    }
