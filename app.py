import sys

import config
from logger import get_logger
from src.container import build_container
from src.generation.prompt import format_sources
from src.indexing.service import IndexingService
from src.ingestion.detection import FileType
from src.ingestion.errors import IngestionError
from src.ingestion.pipeline import IngestionPipeline, find_documents
from src.services.rag_service import RAGService

logger = get_logger(__name__)


def index_documents(
    indexing_service: IndexingService,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    """Index every supported file in the documents folder that is not stored yet.

    Files that cannot be ingested (unsupported, invalid, unreadable) are
    reported and skipped; other files are still indexed.
    """
    if indexing_service.count():
        print(
            f"Loaded {indexing_service.count()} stored chunks "
            f"from {config.VECTOR_STORE_PATH}"
        )

    newly_indexed = 0
    refreshed = 0

    # Save whatever was embedded even if a later file fails, so paid
    # embedding work is not lost.
    try:
        for path in find_documents(config.DOCUMENTS_DIR):
            print(f"Processing: {path.name}")

            try:
                result = ingestion_pipeline.ingest(path)
            except IngestionError as error:
                print(f"Skipped {path.name}: {error}")
                continue

            if not result.documents:
                print(f"No text found in {path.name}, skipping")
                continue

            unit = "page" if result.file_type is FileType.PDF else "section"
            count = len(result.documents)
            print(f"Extracted {count} {unit}{'' if count == 1 else 's'}")

            for document in result.documents:
                added = indexing_service.index_document(document)

                if not added:
                    updated = indexing_service.refresh_metadata(document)
                    refreshed += updated

                    if updated:
                        print(f"Updated metadata of {document.label}")
                    elif duplicate_of := indexing_service.duplicate_of(document):
                        print(f"Duplicate of {duplicate_of}, skipping {document.label}")
                    else:
                        print(f"Already indexed, skipping {document.label}")
                    continue

                newly_indexed += added
                print(f"Total chunks: {added}")
    finally:
        if newly_indexed or refreshed:
            indexing_service.save()
            print(
                f"Saved {indexing_service.count()} chunks "
                f"to {config.VECTOR_STORE_PATH}"
            )


def run_question_loop(rag_service: RAGService) -> None:
    """Read terminal questions and print grounded RAG answers."""
    print("Ask a question, or type 'exit' to quit.")

    while True:
        question = input("Question: ").strip()

        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue

        try:
            answer, context = rag_service.answer_with_context(question)
        except Exception:
            logger.exception("Could not answer the question. Try again or type 'exit'.")
            continue

        print(f"Answer: {answer}")

        sources = format_sources(context)
        if sources:
            print("Sources:")
            for source in sources:
                print(f"- {source}")


def main() -> None:
    # Console output may contain characters the terminal's default codepage
    # cannot encode (arrows, dashes), which would otherwise crash printing.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        container = build_container()
        index_documents(container.indexing_service, container.ingestion_pipeline)
        run_question_loop(container.rag_service)
    except Exception:
        logger.exception("%s stopped because of an error.", config.APP_NAME)
        sys.exit(1)


if __name__ == "__main__":
    main()
