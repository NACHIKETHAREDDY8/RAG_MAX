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
from src.chunking.models import Chunk
from src.embeddings.provider import OpenAIEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.generation.llm import OpenAILLM
from src.generation.prompt import format_sources
from src.generation.service import RAGService
from src.vector_store.base import VectorStore
from src.vector_store.faiss_store import FAISSVectorStore
from src.vector_store.models import SearchResult, VectorRecord
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


def index_chunks(
    chunks: list[Chunk],
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
) -> None:
    """Embed chunks and store their vectors with the chunk content."""
    embeddings = embedding_service.embed_chunks(chunks)
    records = [
        VectorRecord(
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            embedding=embedding,
            metadata=chunk.metadata,
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]
    vector_store.add_many(records)


def query_chunks(
    question: str,
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
    top_k: int = 5,
) -> list[SearchResult]:
    """Embed a question and return its most similar stored chunks."""
    query_embedding = embedding_service.embed_query(question)
    return vector_store.search(query_embedding, top_k=top_k)


def create_rag_service() -> RAGService:
    """Create the application RAG service using the shared configuration."""
    embedding_service = EmbeddingService(OpenAIEmbeddingProvider())
    vector_store = FAISSVectorStore()
    llm = OpenAILLM()
    return RAGService(embedding_service, vector_store, llm)


def answer_question(
    question: str,
    rag_service: RAGService,
    top_k: int = 5,
) -> str:
    """Generate a grounded answer through the application RAG service."""
    return rag_service.answer(question, top_k=top_k)


def run_question_loop(rag_service: RAGService, top_k: int = 5) -> None:
    """Read terminal questions and print grounded RAG answers."""
    print("Ask a question, or type 'exit' to quit.")

    while True:
        question = input("Question: ").strip()

        if question.lower() in {"exit", "quit"}:
            break

        if not question:
            continue

        answer, context = rag_service.answer_with_context(question, top_k=top_k)
        print(f"Answer: {answer}")

        sources = format_sources(context)
        if sources:
            print("Sources:")
            for source in sources:
                print(f"- {source}")


def main():
    documents_folder = Path("documents")

    pdf_files = list(documents_folder.glob("*.pdf"))
    rag_service = create_rag_service()

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
            index_chunks(
                chunks,
                rag_service.embedding_service,
                rag_service.vector_store,
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

    run_question_loop(rag_service)


if __name__ == "__main__":
    main()