from src.ingestion.cleaner import clean_text
from src.ingestion.loader import (
    load_pdf,
    generate_document_id,
    get_file_metadata,
)
from src.tokenization.tokenizer import (
    count_tokens,
    validate_chunk_tokens,
)
from src.ingestion.models import Document
from src.ingestion.parser import parse_pdf
from src.chunking.fixed import fixed_size_chunk
from pathlib import Path


def ingest_pdf(file_path: str) -> list[Document]:
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


def main():
    documents_folder = Path("documents")

    pdf_files = list(documents_folder.glob("*.pdf"))

    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name}")

        documents = ingest_pdf(str(pdf_file))

        print(f"Extracted {len(documents)} pages")

        for document in documents:
            print("=" * 50)
            print(f"Document ID: {document.document_id}")
            print(f"Source: {document.source}")
            print(f"Filename: {document.filename}")
            print(f"Page: {document.page_number}")
            print(f"Text: {document.text[:500]}")

            # Phase 3: Fixed-size chunking
            chunks = fixed_size_chunk(
                text=document.text,
                document_id=document.document_id,
                metadata=document.metadata,
                chunk_size=500,
                overlap=50,
            )

            print(f"Total chunks: {len(chunks)}")

            # Display first 5 chunks for testing
            MAX_CHUNK_TOKENS = 500

            for chunk in chunks[:5]:
                token_count = count_tokens(chunk.text)

                validation = validate_chunk_tokens(
                    chunk.text,
                    MAX_CHUNK_TOKENS,
                )

                print("-" * 40)
                print(f"Chunk ID: {chunk.chunk_id}")
                print(f"Chunk Index: {chunk.chunk_index}")
                print(f"Text Length: {len(chunk.text)}")
                print(f"Token Count: {token_count}")
                print(f"Max Tokens: {MAX_CHUNK_TOKENS}")
                print(f"Valid: {validation['valid']}")
                print(f"Text: {chunk.text[:200]}")
                print(f"Metadata: {chunk.metadata}")


if __name__ == "__main__":
    main()