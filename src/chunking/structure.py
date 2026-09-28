"""Chunking that follows a document's own structure: sections and blocks."""

import re
from dataclasses import dataclass, field

from src.chunking.base import Chunker, require_positive
from src.chunking.models import Chunk
from src.chunking.sentence import fit_span
from src.chunking.spans import Span, hard_split, pack, split_by_pattern, split_sentences

_FENCE = re.compile(r"\s*(```|~~~)")
_HEADING = re.compile(r"(#{1,6})\s+(.+?)\s*#*\s*$")
_SETEXT = re.compile(r"\s*(=+|-+)\s*$")
_LIST_ITEM = re.compile(r"\s*(?:[-*+•]|\d+[.)])\s+")
_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"}


@dataclass
class Block:
    """One structural unit: heading, paragraph, list, table or code."""

    kind: str
    start: int
    end: int
    level: int = 0
    title: str = ""


@dataclass
class Section:
    """A heading (None before the first one) and the blocks up to the next heading."""

    path: tuple[str, ...]
    heading: Block | None
    blocks: list[Block] = field(default_factory=list)

    @property
    def start(self) -> int:
        return (self.heading or self.blocks[0]).start

    @property
    def end(self) -> int:
        return (self.blocks[-1] if self.blocks else self.heading).end


def parse_blocks(text: str, detect_plain_headings: bool = True) -> list[Block]:
    """Split text into blocks.

    Recognises Markdown (# and underlined headings, fenced code, | tables,
    - and 1. lists) and, with detect_plain_headings, the short title-case
    lines that extracted PDFs, DOCX and HTML use as headings once their
    formatting is gone.
    """
    lines = []
    position = 0
    for part in text.split("\n"):
        lines.append((position, position + len(part)))
        position += len(part) + 1

    blocks = []
    index = 0

    def line(i: int) -> str:
        return text[lines[i][0] : lines[i][1]]

    # A plain heading is a title-like line followed by body text, or by
    # another plain heading ("Leave Policy" then "Annual Leave").
    plain_heading = [False] * len(lines)
    if detect_plain_headings:
        following = None
        for i in reversed(range(len(lines))):
            if not line(i).strip():
                continue
            if following is not None and _looks_like_title(line(i)):
                plain_heading[i] = plain_heading[following] or _is_body(
                    line(following), line(i)
                )
            following = i

    def starts_block(i: int) -> bool:
        current = line(i)
        return bool(
            not current.strip()
            or _FENCE.match(current)
            or _HEADING.match(current)
            or _is_table_row(current)
            or _LIST_ITEM.match(current)
            or plain_heading[i]
        )

    while index < len(lines):
        current = line(index)
        start = lines[index][0]

        if not current.strip():
            index += 1
            continue

        if fence := _FENCE.match(current):
            marker = fence.group(1)
            last = index + 1
            while last < len(lines) and not line(last).strip().startswith(marker):
                last += 1
            last = min(last, len(lines) - 1)
            blocks.append(Block("code", start, lines[last][1]))
            index = last + 1
            continue

        if heading := _HEADING.match(current):
            blocks.append(
                Block("heading", start, lines[index][1], len(heading.group(1)), heading.group(2))
            )
            index += 1
            continue

        if (
            index + 1 < len(lines)
            and _SETEXT.match(line(index + 1))
            and not _LIST_ITEM.match(current)
        ):
            level = 1 if "=" in line(index + 1) else 2
            blocks.append(
                Block("heading", start, lines[index + 1][1], level, current.strip())
            )
            index += 2
            continue

        if plain_heading[index]:
            # Below any Markdown heading, so a file mixing both nests them.
            blocks.append(Block("heading", start, lines[index][1], 7, current.strip().rstrip(":")))
            index += 1
            continue

        if _is_table_row(current):
            kind = "table"
        elif _LIST_ITEM.match(current):
            kind = "list"
        else:
            kind = "paragraph"

        last = index
        while last + 1 < len(lines) and line(last + 1).strip():
            following = line(last + 1)
            if kind == "table":
                continues = _is_table_row(following)
            elif kind == "list":
                # Items, and indented lines continuing an item.
                continues = bool(_LIST_ITEM.match(following) or following[:1] in (" ", "\t"))
            else:
                continues = not starts_block(last + 1)
            if not continues:
                break
            last += 1

        blocks.append(Block(kind, start, lines[last][1]))
        index = last + 1

    return blocks


def build_sections(blocks: list[Block]) -> list[Section]:
    """Group blocks under their headings, each section knowing its heading path."""
    sections: list[Section] = []
    stack: list[Block] = []

    for block in blocks:
        if block.kind == "heading":
            while stack and stack[-1].level >= block.level:
                stack.pop()
            stack.append(block)
            sections.append(Section(tuple(h.title for h in stack), block))
        else:
            if not sections:
                sections.append(Section((), None))
            sections[-1].blocks.append(block)

    return sections


def block_units(text: str, block: Block, max_chars: int) -> list[Span]:
    """Split a block too long for one chunk at its natural inner boundaries."""
    if block.end - block.start <= max_chars:
        return [(block.start, block.end)]

    if block.kind in ("code", "table"):
        # Rows and code lines stay whole; only a line longer than a chunk is cut.
        pieces = split_by_pattern(text, block.start, block.end, r"\n")
    elif block.kind == "list":
        pieces = split_by_pattern(text, block.start, block.end, r"\n(?=\s*(?:[-*+•]|\d+[.)])\s)")
    else:
        pieces = split_sentences(text, block.start, block.end)

    units = []
    for start, end in pieces:
        if block.kind == "code" and end - start > max_chars:
            units.extend(hard_split(text, start, end, max_chars))
        else:
            units.extend(fit_span(text, start, end, max_chars))
    return units


def section_units(text: str, section: Section, max_chars: int) -> list[Span]:
    """Units of a section, with its heading attached to the first one."""
    units = [unit for block in section.blocks for unit in block_units(text, block, max_chars)]

    if section.heading is None:
        return units
    if units and units[0][1] - section.heading.start <= max_chars:
        return [(section.heading.start, units[0][1])] + units[1:]
    return [(section.heading.start, section.heading.end)] + units



def structured_spans(
    text: str, start: int, end: int, max_chars: int, detect_plain_headings: bool = True
) -> list[Span]:
    """Chunk spans of at most max_chars within text[start:end], cut between blocks.

    Blocks are packed whole where they fit, so a table, list or code block
    shorter than max_chars always stays in one piece.
    """
    region = text[start:end]
    units = [
        (unit_start + start, unit_end + start)
        for block in parse_blocks(region, detect_plain_headings)
        for unit_start, unit_end in block_units(region, block, max_chars)
    ]
    return pack(units, max_chars)

def group_sections(
    sections: list[Section], min_chars: int, max_chars: int
) -> list[list[Section]]:
    """Combine each section shorter than min_chars with the next, if both fit in max_chars."""
    groups: list[list[Section]] = []

    for section in sections:
        if groups:
            previous = groups[-1]
            previous_length = previous[-1].end - previous[0].start
            combined = section.end - previous[0].start
            if previous_length < min_chars and combined <= max_chars:
                previous.append(section)
                continue
        groups.append([section])

    return groups


class StructureChunker(Chunker):
    """Chunks that follow headings and never split a table row, list item or code line.

    A chunk never spans two sections, except that sections shorter than
    min_section_chars are combined with the next section when both fit in
    max_chars. With include_section_path, each chunk's text starts with
    its heading path ("Handbook > Leave > Sick leave") unless it already
    starts with its only heading, so a chunk from the middle of a section
    still says what it is about. The path is also stored as section_path.
    """

    name = "structure"

    def __init__(
        self,
        max_chars: int = 1000,
        min_section_chars: int = 200,
        include_section_path: bool = True,
        detect_plain_headings: bool = True,
    ) -> None:
        require_positive(max_chars=max_chars)
        self.max_chars = max_chars
        self.min_section_chars = min_section_chars
        self.include_section_path = include_section_path
        self.detect_plain_headings = detect_plain_headings

    def _chunk(self, text: str, document_id: str, metadata: dict, prefix: str) -> list[Chunk]:
        sections = build_sections(parse_blocks(text, self.detect_plain_headings))
        chunks = []

        for group in group_sections(sections, self.min_section_chars, self.max_chars):
            units = [unit for section in group for unit in section_units(text, section, self.max_chars)]
            path = group[0].path

            for start, end in pack(units, self.max_chars):
                chunk_text = text[start:end]
                starts_with_heading = group[0].heading is not None and start == group[0].heading.start
                if self.include_section_path and path and not (starts_with_heading and len(path) == 1):
                    chunk_text = f"{' > '.join(path)}\n{chunk_text}"

                chunk_metadata = metadata.copy()
                if path:
                    chunk_metadata["section_path"] = " > ".join(path)

                chunks.append(
                    Chunk(
                        chunk_id=f"{prefix}_chunk_{len(chunks)}",
                        document_id=document_id,
                        text=chunk_text,
                        chunk_index=len(chunks),
                        metadata=chunk_metadata,
                        start=start,
                        end=end,
                        strategy=self.name,
                    )
                )

        return chunks



def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") or " | " in stripped


def _looks_like_title(line: str) -> bool:
    """A short line in title case or capitals, without sentence punctuation."""
    stripped = line.strip()
    words = stripped.rstrip(":").split()

    if (
        not words
        or len(stripped) > 60
        or len(words) > 8
        or stripped[-1] in ".,;!?"
        or (stripped.endswith(":") and len(words) > 4)
        or not (stripped[0].isupper() or stripped[0].isdigit())
        or _LIST_ITEM.match(line)
        or _is_table_row(line)
    ):
        return False

    content_words = [word for word in words if word.isalpha() and word.lower() not in _SMALL_WORDS]
    if not content_words:
        return False
    capitalised = sum(word[0].isupper() for word in content_words)
    return stripped.isupper() or capitalised / len(content_words) >= 0.6


def _is_body(line: str, title: str) -> bool:
    """Whether line reads as body text under title: longer, or a full sentence."""
    stripped = line.strip()
    return len(stripped) > len(title.strip()) or stripped[-1:] in ".!?:"
