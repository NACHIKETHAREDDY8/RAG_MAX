import pytest

from src.chunking.fixed import fixed_size_chunk


TEXT = (
    "Artificial intelligence is a field of computer science. "
    "Machine learning is a subset of artificial intelligence. "
    "Deep learning uses neural networks to learn patterns from data. "
    "Natural language processing helps computers understand human language."
)


def test_chunks_overlap_and_cover_text():
    chunks = fixed_size_chunk(
        text=TEXT,
        document_id="test_document",
        metadata={"filename": "test.pdf"},
        chunk_size=100,
        overlap=20,
    )

    assert [chunk.chunk_id for chunk in chunks][:2] == [
        "test_document_chunk_0",
        "test_document_chunk_1",
    ]
    assert all(len(chunk.text) <= 100 for chunk in chunks)
    assert chunks[1].text[:20] == chunks[0].text[-20:]
    assert chunks[0].text + "".join(chunk.text[20:] for chunk in chunks[1:]) == TEXT


def test_chunk_metadata_is_copied():
    metadata = {"filename": "test.pdf"}

    chunks = fixed_size_chunk(TEXT, "doc", metadata, chunk_size=100, overlap=20)
    chunks[0].metadata["changed"] = True

    assert "changed" not in metadata
    assert "changed" not in chunks[1].metadata


def test_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValueError):
        fixed_size_chunk(TEXT, "doc", {}, chunk_size=10, overlap=10)


def test_fixed_size_chunk_uses_chunk_id_prefix():
    chunks = fixed_size_chunk(
        "abcdef", "doc", {}, chunk_size=4, overlap=0, chunk_id_prefix="t:doc"
    )

    assert [chunk.chunk_id for chunk in chunks] == ["t:doc_chunk_0", "t:doc_chunk_1"]
    assert {chunk.document_id for chunk in chunks} == {"doc"}
