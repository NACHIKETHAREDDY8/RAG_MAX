"""Content hashes that identify documents independently of their filename."""

import hashlib
from pathlib import Path

# Characters of the SHA-256 kept in document ids.
FILE_KEY_LENGTH = 16


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file's bytes, read in blocks."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)

    return digest.hexdigest()


def make_document_id(file_hash: str, section_number: int) -> str:
    """Return the id of one section of a file: '<hash prefix>-<section>'.

    Identical files get identical ids whatever they are called, which is how
    duplicates are recognised. For PDFs the section is the page number.
    """
    return f"{file_hash[:FILE_KEY_LENGTH]}-{section_number}"


def file_key(document_id: str) -> str:
    """Return the part of a document id shared by every section of one file."""
    return document_id.rsplit("-", 1)[0]
