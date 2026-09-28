from src.chunking.base import Chunker, require_positive
from src.chunking.models import Chunk
from src.chunking.spans import Span, pack, trim
from src.chunking.structure import (
    build_sections,
    group_sections,
    parse_blocks,
    section_units,
    structured_spans,
)

LEVELS = ("document", "section", "paragraph", "chunk")
CONTEXT_LEVELS = ("section", "paragraph")


class HierarchicalChunker(Chunker):
    """A tree of chunks: document → section → paragraph → chunk.

    Sections follow headings (as in the structure chunker) and are split
    into parts of at most section_max_chars; paragraphs are consecutive
    blocks packed up to paragraph_max_chars; leaf chunks are the paragraph's
    blocks (or their sentences, rows, items and lines) packed up to
    chunk_size. Every chunk's parent_id is the chunk one level up and its
    level is its depth (0 = document).

    Only leaves are embedded. Each leaf carries the text of its ancestor at
    context_level ("section" or "paragraph") as context, and, with
    include_section_path, starts with its heading path.
    """

    name = "hierarchical"
    provides_context = True

    def __init__(
        self,
        section_max_chars: int = 3000,
        paragraph_max_chars: int = 1000,
        chunk_size: int = 400,
        min_section_chars: int = 200,
        context_level: str = "section",
        include_section_path: bool = True,
        detect_plain_headings: bool = True,
    ) -> None:
        require_positive(
            section_max_chars=section_max_chars,
            paragraph_max_chars=paragraph_max_chars,
            chunk_size=chunk_size,
        )
        if not chunk_size <= paragraph_max_chars <= section_max_chars:
            raise ValueError("Sizes must satisfy chunk_size <= paragraph_max_chars <= section_max_chars")
        if context_level not in CONTEXT_LEVELS:
            raise ValueError(f"context_level must be one of {', '.join(CONTEXT_LEVELS)}")
        self.section_max_chars = section_max_chars
        self.paragraph_max_chars = paragraph_max_chars
        self.chunk_size = chunk_size
        self.min_section_chars = min_section_chars
        self.context_level = context_level
        self.include_section_path = include_section_path
        self.detect_plain_headings = detect_plain_headings

    def _chunk(self, text: str, document_id: str, metadata: dict, prefix: str) -> list[Chunk]:
        counters = dict.fromkeys(LEVELS, 0)
        chunks: list[Chunk] = []

        def add(level: int, span: Span, parent: Chunk | None, path: tuple[str, ...], **fields) -> Chunk:
            stem = LEVELS[level]
            chunk_metadata = metadata.copy()
            if path:
                chunk_metadata["section_path"] = " > ".join(path)
            chunk = Chunk(
                chunk_id=f"{prefix}_{stem}_{counters[stem]}",
                document_id=document_id,
                text=text[span[0] : span[1]],
                chunk_index=counters[stem],
                metadata=chunk_metadata,
                start=span[0],
                end=span[1],
                strategy=self.name,
                parent_id=parent.chunk_id if parent else None,
                level=level,
                **fields,
            )
            counters[stem] += 1
            chunks.append(chunk)
            return chunk

        document = add(0, trim(text, 0, len(text)), None, (), retrievable=False)
        sections = build_sections(parse_blocks(text, self.detect_plain_headings))

        for group in group_sections(sections, self.min_section_chars, self.section_max_chars):
            path = group[0].path
            heading = group[0].heading
            units = [
                unit
                for section in group
                for unit in section_units(text, section, self.paragraph_max_chars)
            ]

            for part in _within(pack(units, self.section_max_chars), units):
                section = add(1, (part[0][0], part[-1][1]), document, path, retrievable=False)

                for paragraph_units in _within(pack(part, self.paragraph_max_chars), part):
                    paragraph = add(
                        2,
                        (paragraph_units[0][0], paragraph_units[-1][1]),
                        section,
                        path,
                        retrievable=False,
                    )
                    context = section if self.context_level == "section" else paragraph

                    for span in structured_spans(
                        text,
                        paragraph.start,
                        paragraph.end,
                        self.chunk_size,
                        self.detect_plain_headings,
                    ):
                        leaf = add(
                            3,
                            span,
                            paragraph,
                            path,
                            context_id=context.chunk_id,
                            context=context.text,
                        )
                        # As in StructureChunker: no path above a top-level heading.
                        starts_with_heading = heading is not None and span[0] == heading.start
                        if self.include_section_path and path and not (
                            starts_with_heading and len(path) == 1
                        ):
                            leaf.text = f"{' > '.join(path)}\n{leaf.text}"

        return chunks


def _within(groups: list[Span], units: list[Span]) -> list[list[Span]]:
    """For each packed span, the units it was packed from."""
    return [[unit for unit in units if start <= unit[0] and unit[1] <= end] for start, end in groups]
