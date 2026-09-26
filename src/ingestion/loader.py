from pathlib import Path
import hashlib
import json

from src.ingestion.cleaner import clean_text
from src.ingestion.models import Document
from src.ingestion.parser import parse_pdf, parse_pdf_metadata

# Fields a <name>.meta.json file next to a PDF may set. document_id, filename,
# page and source_type are derived from the file itself.
SIDECAR_FIELDS = {"department", "category", "date", "author", "tenant_id"}

def load_pdf(file_path: str) -> Path:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported.")

    return path

def generate_document_id(file_path: Path, page_number: int) -> str:
    file_bytes = file_path.read_bytes()

    file_hash = hashlib.sha256(file_bytes).hexdigest()

    return f"{file_hash[:16]}-{page_number}"

def get_file_metadata(file_path: Path) -> dict:
    return {
        "file_size": file_path.stat().st_size,
        "source_type": file_path.suffix.lower().lstrip("."),
    }

def sidecar_path(file_path: Path) -> Path:
    """Return where the optional metadata file for a document lives."""
    return file_path.with_suffix(".meta.json")

def load_sidecar_metadata(file_path: Path) -> dict:
    """Read the metadata file stored next to a document, if there is one."""
    path = sidecar_path(file_path)

    if not path.exists():
        return {}

    metadata = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(metadata, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")

    unknown = set(metadata) - SIDECAR_FIELDS
    if unknown:
        raise ValueError(
            f"{path.name} has unsupported fields {sorted(unknown)}; "
            f"allowed fields are {sorted(SIDECAR_FIELDS)}."
        )

    for field, value in metadata.items():
        if not isinstance(value, str):
            raise ValueError(f"{path.name}: {field} must be a string.")

    return metadata

def get_document_metadata(file_path: Path) -> dict:
    """Combine file facts, embedded PDF metadata and the sidecar file.

    The sidecar wins, since embedded authors are often just the account
    name of whoever exported the PDF.
    """
    return {
        **get_file_metadata(file_path),
        **parse_pdf_metadata(file_path),
        **load_sidecar_metadata(file_path),
    }

def ingest_pdf(file_path: str) -> list[Document]:
    """Return one cleaned Document per non-empty PDF page."""
    pdf_path = load_pdf(file_path)
    pages = parse_pdf(pdf_path)
    metadata = get_document_metadata(pdf_path)
    documents = []

    for page in pages:
        cleaned_text = clean_text(page["text"])

        if not cleaned_text:
            continue

        document = Document(
            document_id=generate_document_id(
                pdf_path,
                page["page_number"],
            ),
            source=str(pdf_path),
            filename=pdf_path.name,
            page_number=page["page_number"],
            text=cleaned_text,
            metadata=metadata.copy(),
        )

        documents.append(document)

    return documents
