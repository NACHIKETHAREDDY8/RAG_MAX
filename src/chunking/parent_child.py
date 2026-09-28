from src.chunking.base import Chunker, require_overlap, require_positive
from src.chunking.models import Chunk
from src.chunking.recursive import RecursiveChunker


class ParentChildChunker(Chunker):
    """Search small chunks, answer from the large chunk around them.

    The text is split recursively into parents of up to parent_size
    characters, and each parent into children of up to child_size. Only
    children are embedded, so a match is precise; each child carries its
    parent's text as context, so the LLM sees the surrounding paragraphs
    too. Children never cross a parent boundary.

    Parents are returned with retrievable=False and ids "<prefix>_parent_<n>";
    children keep the usual "<prefix>_chunk_<n>" ids and point to their
    parent through parent_id.
    """

    name = "parent_child"
    provides_context = True

    def __init__(
        self,
        parent_size: int = 2000,
        child_size: int = 400,
        child_overlap: int = 0,
    ) -> None:
        require_positive(parent_size=parent_size, child_size=child_size)
        require_overlap(child_overlap, child_size, "child_size")
        if child_size > parent_size:
            raise ValueError("child_size cannot exceed parent_size")
        self.parent_size = parent_size
        self.child_size = child_size
        self.child_overlap = child_overlap

    def _chunk(self, text: str, document_id: str, metadata: dict, prefix: str) -> list[Chunk]:
        parent_splitter = RecursiveChunker(self.parent_size)
        child_splitter = RecursiveChunker(self.child_size, self.child_overlap)
        parents = self._chunks_from_spans(
            text,
            parent_splitter.spans(text, 0, len(text)),
            document_id,
            metadata,
            prefix,
            stem="parent",
            level=0,
            retrievable=False,
        )
        chunks = []
        children = 0

        for parent in parents:
            chunks.append(parent)
            for start, end in child_splitter.spans(text, parent.start, parent.end):
                chunks.append(
                    Chunk(
                        chunk_id=f"{prefix}_chunk_{children}",
                        document_id=document_id,
                        text=text[start:end],
                        chunk_index=children,
                        metadata=metadata.copy(),
                        start=start,
                        end=end,
                        strategy=self.name,
                        parent_id=parent.chunk_id,
                        level=1,
                        context_id=parent.chunk_id,
                        context=parent.text,
                    )
                )
                children += 1

        return chunks
