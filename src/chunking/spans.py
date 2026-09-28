"""Character spans: the shared vocabulary of every chunking strategy.

Strategies decide where text is cut by working with (start, end) offsets into
the original string rather than with copies of it. Joining consecutive spans
is then a single slice from the first start to the last end, so separators
between pieces are kept exactly as they were and every chunk can be traced
back to its place in the document.
"""

import re
from collections.abc import Callable

Span = tuple[int, int]

# Named separator patterns for recursive splitting, coarsest first.
SEPARATORS = {
    # A Markdown heading starts a new section.
    "section": r"\n(?=#{1,6}\s)",
    "paragraph": r"\n[ \t]*\n",
    "line": r"\n",
    # Sentence ends. Abbreviations are handled by split_sentences; for
    # recursive splitting an occasional cut after "e.g." is harmless.
    "sentence": r"(?<=[.!?])[\"'”’)\]]*\s+",
    "word": r"\s+",
}
DEFAULT_SEPARATORS = ["section", "paragraph", "line", "sentence", "word"]

ABBREVIATIONS = {
    "e.g.", "i.e.", "etc.", "vs.", "mr.", "mrs.", "ms.", "dr.", "prof.",
    "inc.", "ltd.", "co.", "corp.", "jr.", "sr.", "st.", "no.", "fig.",
    "approx.", "dept.", "u.s.", "a.m.", "p.m.",
}
_SENTENCE_END = re.compile(r"[.!?][\"'”’)\]]*\s+")
_STRUCTURAL_LINE = re.compile(r"\s*(?:[-*+•]\s|\d+[.)]\s|#{1,6}\s|\|)")


def trim(text: str, start: int, end: int) -> Span | None:
    """Shrink a span to exclude surrounding whitespace; None if nothing is left."""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


def split_by_pattern(text: str, start: int, end: int, pattern: str) -> list[Span]:
    """Return the non-blank pieces of text[start:end] between pattern matches."""
    pieces = []
    position = start

    for match in re.compile(pattern).finditer(text, start, end):
        if match.end() == match.start():
            continue
        if (piece := trim(text, position, match.start())) is not None:
            pieces.append(piece)
        position = match.end()

    if (piece := trim(text, position, end)) is not None:
        pieces.append(piece)

    return pieces


def hard_split(text: str, start: int, end: int, size: int) -> list[Span]:
    """Cut a span into consecutive pieces of at most size characters."""
    pieces = []
    for piece_start in range(start, end, size):
        if (piece := trim(text, piece_start, min(piece_start + size, end))) is not None:
            pieces.append(piece)
    return pieces


def split_sentences(text: str, start: int = 0, end: int | None = None) -> list[Span]:
    """Return sentence spans in text[start:end].

    A sentence ends at ., ! or ? followed by whitespace, unless the word is a
    known abbreviation or a single initial, or the next word starts in lower
    case. A blank line always ends a sentence, and so does a line break
    before a list item, heading or table row, or before a capitalised line
    (extracted PDFs and HTML put headings and bullets on their own lines
    without punctuation). A line that continues in lower case is treated as
    a wrapped sentence.
    """
    end = len(text) if end is None else end
    sentences = []

    for block_start, block_end in split_by_pattern(text, start, end, SEPARATORS["paragraph"]):
        for line_start, line_end in _logical_lines(text, block_start, block_end):
            sentences.extend(_split_line(text, line_start, line_end))

    return sentences


def _logical_lines(text: str, start: int, end: int) -> list[Span]:
    """Join wrapped lines; keep lines that start a new unit separate."""
    lines = split_by_pattern(text, start, end, r"\n")
    logical: list[Span] = []

    for line_start, line_end in lines:
        first = text[line_start]
        continues = (
            logical
            and not _STRUCTURAL_LINE.match(text, line_start)
            and (first.islower() or first in ",;:)")
        )
        if continues:
            logical[-1] = (logical[-1][0], line_end)
        else:
            logical.append((line_start, line_end))

    return logical


def _split_line(text: str, start: int, end: int) -> list[Span]:
    sentences = []
    sentence_start = start

    for match in _SENTENCE_END.finditer(text, start, end):
        following = match.end()
        if following >= end:
            break

        word_start = text.rfind(" ", sentence_start, match.start()) + 1
        word = text[max(word_start, sentence_start) : match.start() + 1].lower()
        next_char = text[following]

        if word in ABBREVIATIONS or re.fullmatch(r"[a-z]\.", word) or next_char.islower():
            continue

        if (sentence := trim(text, sentence_start, match.start() + 1)) is not None:
            sentences.append(sentence)
        sentence_start = following

    if (sentence := trim(text, sentence_start, end)) is not None:
        sentences.append(sentence)

    return sentences


def pack(
    spans: list[Span],
    max_length: int,
    overlap: int = 0,
    length: Callable[[Span], int] | None = None,
) -> list[Span]:
    """Greedily join consecutive spans into spans of at most max_length.

    A span longer than max_length on its own is kept whole; callers split
    such pieces first when that matters. With overlap, each packed span
    starts with the trailing pieces of the previous one, as many as fit in
    overlap characters, while always adding at least one new piece.
    """
    measure = length or (lambda span: span[1] - span[0])
    packed = []
    first = 0

    while first < len(spans):
        last = first
        while (
            last + 1 < len(spans)
            and measure((spans[first][0], spans[last + 1][1])) <= max_length
        ):
            last += 1

        packed.append((spans[first][0], spans[last][1]))

        if last + 1 >= len(spans):
            break

        next_first = last + 1
        while (
            overlap
            and next_first - 1 > first
            and measure((spans[next_first - 1][0], spans[last][1])) <= overlap
        ):
            next_first -= 1
        first = next_first

    return packed
