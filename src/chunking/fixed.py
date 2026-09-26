from typing import List

from src.chunking.models import Chunk


def fixed_size_chunk(
    text: str,
    document_id: str,
    metadata: dict,
    chunk_size: int = 500,
    overlap: int = 50,
    chunk_id_prefix: str | None = None,
) -> List[Chunk]:

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if overlap < 0:
        raise ValueError("overlap cannot be negative")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    if chunk_id_prefix is None:
        chunk_id_prefix = document_id

    chunks = []

    start = 0
    chunk_index = 0
    step = chunk_size - overlap

    while start < len(text):

        end = start + chunk_size
        chunk_text = text[start:end]
        chunk = Chunk(
            chunk_id=f"{chunk_id_prefix}_chunk_{chunk_index}",
            document_id=document_id,
            text=chunk_text,
            chunk_index=chunk_index,
            metadata=metadata.copy(),
        )

        chunks.append(chunk)
        chunk_index += 1
        start += step

    return chunks