"""Checks a file must pass before it is read."""

from pathlib import Path

from src.ingestion.errors import FileValidationError


def validate_file(file_path: str | Path, max_size_bytes: int) -> Path:
    """Return the file's path if it exists, is a non-empty file, and is small enough."""
    path = Path(file_path)

    if not path.exists():
        raise FileValidationError(f"File not found: {file_path}")

    if not path.is_file():
        raise FileValidationError(f"Not a file: {file_path}")

    size = path.stat().st_size

    if size == 0:
        raise FileValidationError(f"{path.name} is empty.")

    if size > max_size_bytes:
        raise FileValidationError(
            f"{path.name} is {size / 1_048_576:.1f} MB; the limit is "
            f"{max_size_bytes / 1_048_576:.1f} MB."
        )

    return path
