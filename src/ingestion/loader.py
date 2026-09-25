from pathlib import Path
import hashlib

from src.ingestion.cleaner import clean_text
from src.ingestion.models import Document
from src.ingestion.parser import parse_pdf

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
        "file_type": file_path.suffix.lower(),
    }

def ingest_pdf(file_path: str) -> list[Document]:
    """Return one cleaned Document per non-empty PDF page."""
    pdf_path = load_pdf(file_path)
    pages = parse_pdf(pdf_path)
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
            metadata=get_file_metadata(pdf_path),
        )

        documents.append(document)

    return documents
