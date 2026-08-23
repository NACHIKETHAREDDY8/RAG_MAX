from src.chunking.fixed import fixed_size_chunk


text = (
    "Artificial intelligence is a field of computer science. "
    "Machine learning is a subset of artificial intelligence. "
    "Deep learning uses neural networks to learn patterns from data. "
    "Natural language processing helps computers understand human language."
)

document_id = "test_document"

metadata = {
    "filename": "test.pdf"
}


chunks = fixed_size_chunk(
    text=text,
    document_id=document_id,
    metadata=metadata,
    chunk_size=100,
    overlap=20,
)


print(f"Total chunks: {len(chunks)}")

for chunk in chunks:
    print("\n--------------------")
    print(f"Chunk ID: {chunk.chunk_id}")
    print(f"Document ID: {chunk.document_id}")
    print(f"Chunk Index: {chunk.chunk_index}")
    print(f"Text: {chunk.text}")
    print(f"Metadata: {chunk.metadata}")