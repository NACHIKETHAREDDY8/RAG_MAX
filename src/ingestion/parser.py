from pathlib import Path
from pypdf import PdfReader

def parse_pdf(file_path: Path) -> list[dict]:
    reader = PdfReader(file_path)

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        pages.append(
            {
                "page_number": page_number,
                "text": text,
            }
        )
    return pages


def parse_pdf_metadata(file_path: Path) -> dict:
    """Return the author and creation date embedded in a PDF, when present."""
    info = PdfReader(file_path).metadata
    metadata = {}

    if info is None:
        return metadata

    if info.author and info.author.strip():
        metadata["author"] = info.author.strip()

    try:
        created = info.creation_date
    except ValueError:
        # Some PDF writers store dates pypdf cannot parse; the date is optional.
        created = None

    if created:
        metadata["date"] = created.date().isoformat()

    return metadata