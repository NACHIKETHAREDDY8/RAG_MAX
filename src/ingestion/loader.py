from pathlib import Path
import hashlib


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