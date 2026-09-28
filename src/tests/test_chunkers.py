"""Every chunking strategy: the shared contract, edge cases, and each one's own rules."""

import re

import pytest

from src.chunking.base import Chunker
from src.chunking.fixed import FixedSizeChunker
from src.chunking.hierarchical import HierarchicalChunker
from src.chunking.metadata_aware import MetadataAwareChunker
from src.chunking.parent_child import ParentChildChunker
from src.chunking.recursive import RecursiveChunker
from src.chunking.registry import available_chunkers, build_chunker, get_chunker, register_chunker
from src.chunking.semantic import SemanticChunker
from src.chunking.sentence import SentenceChunker
from src.chunking.sliding_window import SlidingWindowChunker
from src.chunking.spans import pack, split_sentences
from src.chunking.structure import StructureChunker, build_sections, parse_blocks
from src.chunking.token import TokenChunker
from src.embeddings.service import EmbeddingService
from src.tests.conftest import FakeEmbeddingProvider
from src.tokenization.tokenizer import count_tokens

MARKDOWN = """# Handbook

Intro paragraph about the company. It has two sentences.

## Leave

Employees get 20 days of annual leave. Leave must be approved by a manager, e.g. your lead.

| Type | Days |
|------|------|
| Sick | 10 |

## VPN

```bash
vpn connect --server corp.example.com
vpn status
```

- Install the client
- Log in with SSO
"""

LONG_PARAGRAPH = " ".join(
    f"Sentence number {n} talks about topic {n % 7} in some detail." for n in range(60)
)
UNICODE = "Zürich café — naïve résumé. 東京の事務所は十二人です。 Emoji test 🚀🔥 done. São Paulo opened in 2021."
SHORT = "Tiny."

INPUTS = {
    "markdown": MARKDOWN,
    "long_paragraph": LONG_PARAGRAPH,
    "unicode": UNICODE,
    "short": SHORT,
    "one_huge_word": "x" * 1200,
    "blank_lines": "First line.\n\n\n\nSecond line after gaps.\n",
}


def small_chunkers() -> dict[str, Chunker]:
    """Every registered strategy with sizes small enough to split the inputs."""
    embeddings = EmbeddingService(FakeEmbeddingProvider(), dimension=3)
    params = {
        "fixed": {"chunk_size": 80, "overlap": 10},
        "sliding_window": {"window_size": 12, "step": 8},
        "sentence": {"max_chars": 80, "overlap_sentences": 1},
        "recursive": {"chunk_size": 80, "overlap": 20},
        "token": {"max_tokens": 20, "overlap_tokens": 4},
        "semantic": {"max_chars": 150, "min_chars": 20},
        "structure": {"max_chars": 150, "min_section_chars": 0},
        "metadata_aware": {},
        "parent_child": {"parent_size": 200, "child_size": 80},
        "hierarchical": {
            "section_max_chars": 300,
            "paragraph_max_chars": 150,
            "chunk_size": 80,
            "min_section_chars": 0,
        },
    }
    assert set(params) == set(available_chunkers())
    return {name: get_chunker(name, embedding_service=embeddings, **params[name]) for name in params}


CHUNKERS = small_chunkers()


# --- the contract every strategy shares --------------------------------------


@pytest.mark.parametrize("name", sorted(CHUNKERS))
@pytest.mark.parametrize("text", ["", "   ", "\n\n\t "])
def test_blank_text_gives_no_chunks(name, text):
    assert CHUNKERS[name].chunk(text, "doc") == []


@pytest.mark.parametrize("name", sorted(CHUNKERS))
@pytest.mark.parametrize("input_name", sorted(INPUTS))
def test_every_word_lands_in_a_retrievable_chunk(name, input_name):
    text = INPUTS[input_name]
    chunks = CHUNKERS[name].chunk(text, "doc", {"source_type": "markdown"})
    retrievable = [chunk for chunk in chunks if chunk.retrievable]

    assert retrievable
    for word in re.finditer(r"\S+", text):
        assert any(
            chunk.start <= word.start() and word.end() <= chunk.end for chunk in retrievable
        ) or any(
            # A word longer than a chunk is cut; each piece must be covered.
            chunk.start < word.end() and word.start() < chunk.end for chunk in retrievable
        ), f"{word.group()!r} at {word.start()} is in no chunk"


@pytest.mark.parametrize("name", sorted(CHUNKERS))
@pytest.mark.parametrize("input_name", sorted(INPUTS))
def test_offsets_locate_chunk_text(name, input_name):
    text = INPUTS[input_name]

    for chunk in CHUNKERS[name].chunk(text, "doc"):
        assert 0 <= chunk.start < chunk.end <= len(text)
        source = text[chunk.start : chunk.end]
        # Structure-aware strategies may prepend the section path.
        assert chunk.text == source or chunk.text.endswith("\n" + source)
        assert chunk.text.strip()


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_ids_are_sequential_and_metadata_is_copied(name):
    metadata = {"filename": "handbook.md"}
    chunks = CHUNKERS[name].chunk(MARKDOWN, "doc", metadata, chunk_id_prefix="t:doc")
    retrievable = [chunk for chunk in chunks if chunk.retrievable]

    assert [chunk.chunk_id for chunk in retrievable] == [
        f"t:doc_chunk_{index}" for index in range(len(retrievable))
    ]
    assert [chunk.chunk_index for chunk in retrievable] == list(range(len(retrievable)))
    assert {chunk.document_id for chunk in chunks} == {"doc"}
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)

    chunks[0].metadata["changed"] = True
    assert "changed" not in metadata
    assert all("changed" not in chunk.metadata for chunk in chunks[1:])


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_missing_metadata_is_allowed(name):
    chunks = CHUNKERS[name].chunk("Some text about cats. More text about dogs.", "doc", None)

    assert chunks
    assert all(chunk.strategy and chunk.strategy.split(":")[0] == CHUNKERS[name].name for chunk in chunks)


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_text_shorter_than_one_chunk_is_one_retrievable_chunk(name):
    chunks = [chunk for chunk in CHUNKERS[name].chunk(SHORT, "doc") if chunk.retrievable]

    assert [(chunk.start, chunk.end) for chunk in chunks] == [(0, len(SHORT))]


# --- fixed -------------------------------------------------------------------


def test_fixed_overlap_boundaries():
    chunks = FixedSizeChunker(chunk_size=10, overlap=3).chunk("abcdefghijklmnopqrstuvwxyz", "doc")

    assert [(chunk.start, chunk.end) for chunk in chunks] == [(0, 10), (7, 17), (14, 24), (21, 26)]
    assert chunks[1].text[:3] == chunks[0].text[-3:]


def test_fixed_makes_no_chunk_inside_the_previous_overlap():
    # Before Phase 11 a fourth chunk [24:26] repeated the end of the third.
    chunks = FixedSizeChunker(chunk_size=10, overlap=2).chunk("x" * 26, "doc")

    assert [(chunk.start, chunk.end) for chunk in chunks] == [(0, 10), (8, 18), (16, 26)]


@pytest.mark.parametrize(
    ("size", "overlap"), [(0, 0), (10, 10), (10, -1)]
)
def test_fixed_rejects_invalid_sizes(size, overlap):
    with pytest.raises(ValueError):
        FixedSizeChunker(size, overlap)


# --- sliding window ------------------------------------------------------------


def test_sliding_window_never_cuts_words_and_keeps_last_window_full():
    text = " ".join(f"w{n}" for n in range(10))
    chunks = SlidingWindowChunker(window_size=4, step=3).chunk(text, "doc")

    assert [chunk.text.split() for chunk in chunks] == [
        ["w0", "w1", "w2", "w3"],
        ["w3", "w4", "w5", "w6"],
        ["w6", "w7", "w8", "w9"],
    ]


def test_sliding_window_last_window_moves_back_to_stay_full():
    text = " ".join(f"w{n}" for n in range(9))
    chunks = SlidingWindowChunker(window_size=4, step=4).chunk(text, "doc")

    assert [chunk.text.split()[0] for chunk in chunks] == ["w0", "w4", "w5"]
    assert all(len(chunk.text.split()) == 4 for chunk in chunks)


def test_sliding_window_rejects_step_larger_than_window():
    with pytest.raises(ValueError):
        SlidingWindowChunker(window_size=4, step=5)


# --- sentences ---------------------------------------------------------------


def test_sentence_split_handles_abbreviations_and_lines():
    text = (
        "Dr. Smith approved it, e.g. for travel. Costs rose 3.5 percent! Why?\n"
        "Leave Policy\n"
        "Employees get leave. The list:\n"
        "- first item\n"
        "- second item wraps\n"
        "  onto the next line"
    )
    sentences = [text[start:end] for start, end in split_sentences(text)]

    assert sentences == [
        "Dr. Smith approved it, e.g. for travel.",
        "Costs rose 3.5 percent!",
        "Why?",
        "Leave Policy",
        "Employees get leave.",
        "The list:",
        "- first item",
        "- second item wraps\n  onto the next line",
    ]


def test_sentence_chunker_never_ends_mid_sentence():
    chunks = SentenceChunker(max_chars=120).chunk(LONG_PARAGRAPH, "doc")

    assert len(chunks) > 1
    assert all(chunk.text.endswith(".") and len(chunk.text) <= 120 for chunk in chunks)


def test_sentence_chunker_splits_a_sentence_longer_than_max_between_words():
    text = "word " * 50 + "end."
    chunks = SentenceChunker(max_chars=40).chunk(text, "doc")

    assert all(len(chunk.text) <= 40 for chunk in chunks)
    assert all(not chunk.text.startswith("ord") for chunk in chunks)


def test_sentence_overlap_repeats_last_sentence():
    text = "One is here. Two is here. Three is here. Four is here."
    chunks = SentenceChunker(max_chars=30, overlap_sentences=1).chunk(text, "doc")

    assert [chunk.text for chunk in chunks] == [
        "One is here. Two is here.",
        "Two is here. Three is here.",
        "Three is here. Four is here.",
    ]


# --- recursive ---------------------------------------------------------------


def test_recursive_prefers_paragraph_boundaries():
    text = "First paragraph is here.\n\nSecond paragraph is here.\n\nThird one."
    chunks = RecursiveChunker(chunk_size=55).chunk(text, "doc")

    assert [chunk.text for chunk in chunks] == [
        "First paragraph is here.\n\nSecond paragraph is here.",
        "Third one.",
    ]


def test_recursive_hard_splits_a_word_longer_than_the_chunk():
    chunks = RecursiveChunker(chunk_size=100).chunk("y" * 250, "doc")

    assert [len(chunk.text) for chunk in chunks] == [100, 100, 50]


def test_recursive_accepts_custom_separators():
    text = "row one\nrow two\nrow three"
    chunks = RecursiveChunker(chunk_size=16, separators=["line"]).chunk(text, "doc")

    assert [chunk.text for chunk in chunks] == ["row one\nrow two", "row three"]


def test_pack_overlap_always_makes_progress():
    spans = [(0, 5), (6, 11), (12, 17), (18, 23)]

    assert pack(spans, max_length=11, overlap=100) == [(0, 11), (6, 17), (12, 23)]


# --- tokens ------------------------------------------------------------------


def test_token_chunks_respect_the_token_limit_and_overlap():
    chunks = TokenChunker(max_tokens=30, overlap_tokens=5).chunk(LONG_PARAGRAPH, "doc")

    assert len(chunks) > 1
    assert all(count_tokens(chunk.text) <= 31 for chunk in chunks)
    assert all(later.start < earlier.end for earlier, later in zip(chunks, chunks[1:]))


def test_token_chunks_never_break_multibyte_characters():
    text = "🚀" * 40 + " 東京の事務所 " * 10
    chunks = TokenChunker(max_tokens=7, overlap_tokens=0).chunk(text, "doc")

    assert "�" not in "".join(chunk.text for chunk in chunks)
    assert all(chunk.text == text[chunk.start : chunk.end] for chunk in chunks)


# --- semantic ----------------------------------------------------------------


def semantic(**params) -> SemanticChunker:
    return SemanticChunker(EmbeddingService(FakeEmbeddingProvider(), dimension=3), **params)


TOPICS = (
    "The cat sleeps. The cat eats. The cat purrs. "
    "The dog barks. The dog runs. The dog digs. "
    "The fish swims. The fish floats."
)


def test_semantic_cuts_where_the_topic_changes():
    chunker = semantic(buffer_size=0, threshold_type="absolute", breakpoint_threshold=0.5, min_chars=0)

    chunks = chunker.chunk(TOPICS, "doc")

    assert [chunk.text for chunk in chunks] == [
        "The cat sleeps. The cat eats. The cat purrs.",
        "The dog barks. The dog runs. The dog digs.",
        "The fish swims. The fish floats.",
    ]


def test_semantic_analysis_explains_breakpoints():
    analysis = semantic(buffer_size=0, threshold_type="absolute", breakpoint_threshold=0.5).analyze(TOPICS)

    assert len(analysis.sentences) == 8
    assert analysis.breakpoints == [2, 5]
    assert all(analysis.distances[index] > 0.5 for index in analysis.breakpoints)


def test_semantic_splits_oversized_groups_and_merges_tiny_ones():
    oversized = semantic(buffer_size=0, threshold_type="absolute", breakpoint_threshold=2.0, max_chars=50, min_chars=0)
    assert all(len(chunk.text) <= 50 for chunk in oversized.chunk(TOPICS, "doc"))

    merged = semantic(buffer_size=0, threshold_type="absolute", breakpoint_threshold=0.5, min_chars=40)
    assert [chunk.text for chunk in merged.chunk(TOPICS, "doc")][-1].startswith("The dog")


def test_semantic_percentile_and_std_thresholds():
    for threshold_type, value in (("percentile", 80.0), ("std", 1.0)):
        chunks = semantic(buffer_size=0, threshold_type=threshold_type, breakpoint_threshold=value, min_chars=0).chunk(TOPICS, "doc")
        assert 1 < len(chunks) <= 8


def test_semantic_cuts_before_headings_and_never_after_them():
    text = "The cat sleeps. The cat eats.\n## Care Notes\nThe cat purrs. The cat naps."
    chunker = semantic(buffer_size=0, threshold_type="absolute", breakpoint_threshold=2.0, min_chars=500)

    chunks = chunker.chunk(text, "doc")

    # No distance crosses the threshold and every group is under min_chars,
    # yet the heading still starts a chunk and stays with its section.
    assert [chunk.text for chunk in chunks] == [
        "The cat sleeps. The cat eats.",
        "## Care Notes\nThe cat purrs. The cat naps.",
    ]
    unaware = semantic(
        buffer_size=0, threshold_type="absolute", breakpoint_threshold=2.0, min_chars=0, respect_headings=False
    )
    assert len(unaware.chunk(text, "doc")) == 1


def test_semantic_keeps_back_references_with_what_they_refer_to():
    text = "The dog barks. The dog runs. This makes the cat hide. The cat sleeps."
    guarded = semantic(buffer_size=0, threshold_type="absolute", breakpoint_threshold=0.5, min_chars=0)
    unguarded = semantic(
        buffer_size=0, threshold_type="absolute", breakpoint_threshold=0.5, min_chars=0, keep_references=False
    )

    assert [chunk.text for chunk in unguarded.chunk(text, "doc")] == [
        "The dog barks. The dog runs.",
        "This makes the cat hide. The cat sleeps.",
    ]
    assert len(guarded.chunk(text, "doc")) == 1
    assert 1 in guarded.analyze(text).blocked


def test_semantic_single_sentence_is_one_chunk_without_embedding():
    provider = FakeEmbeddingProvider()
    chunker = SemanticChunker(EmbeddingService(provider, dimension=3))

    assert [chunk.text for chunk in chunker.chunk("Only one sentence here.", "doc")] == [
        "Only one sentence here."
    ]
    assert provider.calls == []


def test_semantic_rejects_invalid_settings():
    with pytest.raises(ValueError):
        semantic(threshold_type="median")
    with pytest.raises(ValueError):
        semantic(min_chars=500, max_chars=100)


# --- structure ---------------------------------------------------------------


def test_structure_parses_markdown_blocks_and_sections():
    blocks = parse_blocks(MARKDOWN)
    sections = build_sections(blocks)

    assert [block.kind for block in blocks] == [
        "heading", "paragraph", "heading", "paragraph", "table", "heading", "code", "list",
    ]
    assert [section.path for section in sections] == [
        ("Handbook",),
        ("Handbook", "Leave"),
        ("Handbook", "VPN"),
    ]


def test_structure_keeps_tables_and_code_whole_and_adds_section_path():
    chunks = StructureChunker(max_chars=150, min_section_chars=0).chunk(MARKDOWN, "doc")
    texts = [chunk.text for chunk in chunks]

    assert any("| Type | Days |\n|------|------|\n| Sick | 10 |" in text for text in texts)
    assert any("```bash\nvpn connect --server corp.example.com\nvpn status\n```" in text for text in texts)
    assert texts[0].startswith("# Handbook")
    assert texts[1].startswith("Handbook > Leave\n## Leave")
    assert [chunk.metadata["section_path"] for chunk in chunks] == [
        "Handbook", "Handbook > Leave", "Handbook > VPN",
    ]


def test_structure_splits_a_long_table_between_rows():
    table = "| Name | Value |\n" + "".join(f"| row {n} | {n * 10} |\n" for n in range(30))
    chunks = StructureChunker(max_chars=100, include_section_path=False).chunk(table, "doc")

    assert len(chunks) > 1
    for chunk in chunks:
        assert all(line.startswith("|") and line.endswith("|") for line in chunk.text.splitlines())


def test_structure_detects_plain_text_headings():
    text = (
        "Leave Policy\n"
        "Annual Leave\n"
        "Full-time employees receive 25 days of paid annual leave per year.\n"
        "Sick Leave\n"
        "Notify your manager before 09:30 on the first day of absence."
    )
    sections = build_sections(parse_blocks(text))

    assert [section.path[-1] for section in sections] == ["Leave Policy", "Annual Leave", "Sick Leave"]
    assert build_sections(parse_blocks(text, detect_plain_headings=False))[0].heading is None


def test_structure_reads_setext_headings_and_unclosed_fences():
    text = "Title\n=====\n\nBody text here.\n\n```\ncode without end"
    blocks = parse_blocks(text)

    assert [(block.kind, block.level) for block in blocks] == [("heading", 1), ("paragraph", 0), ("code", 0)]
    assert blocks[-1].end == len(text)


# --- metadata-aware ------------------------------------------------------------


def test_metadata_aware_routes_by_source_type():
    chunker = MetadataAwareChunker()
    csv_text = "\n".join(f"office: O{n} | city: C{n} | employees: {n}" for n in range(40))

    csv_chunks = chunker.chunk(csv_text, "doc", {"source_type": "csv"})
    markdown_chunks = chunker.chunk(MARKDOWN, "doc", {"source_type": "markdown"})
    other_chunks = chunker.chunk(LONG_PARAGRAPH, "doc", {"source_type": "pdf"})

    assert {chunk.strategy for chunk in csv_chunks} == {"metadata_aware:recursive"}
    assert all(chunk.text.startswith("office:") and chunk.text.split("\n")[-1].count("|") == 2 for chunk in csv_chunks)
    assert {chunk.strategy for chunk in markdown_chunks} == {"metadata_aware:structure"}
    assert {chunk.strategy for chunk in other_chunks} == {"metadata_aware:recursive"}


def test_metadata_aware_custom_rules_and_fallback():
    chunker = MetadataAwareChunker(
        rules=[{"when": {"category": "policy", "department": ["HR", "Legal"]}, "strategy": "sentence", "params": {"max_chars": 50}}],
        fallback={"strategy": "fixed", "params": {"chunk_size": 30, "overlap": 0}},
    )

    assert chunker.chunker_for({"category": "policy", "department": "HR"}).name == "sentence"
    assert chunker.chunker_for({"category": "policy", "department": "IT"}).name == "fixed"
    assert chunker.chunker_for({}).name == "fixed"
    assert not chunker.provides_context


def test_metadata_aware_provides_context_when_a_rule_does():
    chunker = MetadataAwareChunker(rules=[{"when": {"source_type": "pdf"}, "strategy": "parent_child"}])

    assert chunker.provides_context
    with pytest.raises(ValueError):
        MetadataAwareChunker(rules=[{"when": {}, "strategy": "metadata_aware"}])


# --- parent-child ------------------------------------------------------------


def test_parent_child_children_sit_inside_their_parent():
    chunks = ParentChildChunker(parent_size=300, child_size=100).chunk(LONG_PARAGRAPH, "doc", chunk_id_prefix="t:doc")
    parents = {chunk.chunk_id: chunk for chunk in chunks if not chunk.retrievable}
    children = [chunk for chunk in chunks if chunk.retrievable]

    assert len(parents) > 1 and len(children) > len(parents)
    assert all(chunk_id.startswith("t:doc_parent_") for chunk_id in parents)
    for child in children:
        parent = parents[child.parent_id]
        assert parent.start <= child.start and child.end <= parent.end
        assert child.context == parent.text and child.context_id == parent.chunk_id
        assert (parent.level, child.level) == (0, 1)
        assert len(child.text) <= 100


def test_parent_child_rejects_child_larger_than_parent():
    with pytest.raises(ValueError):
        ParentChildChunker(parent_size=100, child_size=200)


# --- hierarchical ------------------------------------------------------------


def test_hierarchical_builds_a_four_level_tree():
    chunker = HierarchicalChunker(section_max_chars=300, paragraph_max_chars=150, chunk_size=80, min_section_chars=0)
    chunks = chunker.chunk(MARKDOWN, "doc")
    by_id = {chunk.chunk_id: chunk for chunk in chunks}

    assert sorted({chunk.level for chunk in chunks}) == [0, 1, 2, 3]
    assert [chunk.level for chunk in chunks if chunk.retrievable] == [3] * sum(chunk.retrievable for chunk in chunks)
    for chunk in chunks:
        if chunk.parent_id:
            parent = by_id[chunk.parent_id]
            assert parent.level == chunk.level - 1
            assert parent.start <= chunk.start and chunk.end <= parent.end
    for leaf in (chunk for chunk in chunks if chunk.retrievable):
        assert by_id[leaf.context_id].level == 1
        assert leaf.context == by_id[leaf.context_id].text


def test_hierarchical_context_level_paragraph():
    chunks = HierarchicalChunker(
        section_max_chars=300, paragraph_max_chars=150, chunk_size=80, context_level="paragraph"
    ).chunk(MARKDOWN, "doc")
    by_id = {chunk.chunk_id: chunk for chunk in chunks}

    assert {by_id[chunk.context_id].level for chunk in chunks if chunk.retrievable} == {2}


def test_hierarchical_rejects_inconsistent_sizes():
    with pytest.raises(ValueError):
        HierarchicalChunker(section_max_chars=500, paragraph_max_chars=1000, chunk_size=400)


# --- registry ----------------------------------------------------------------


def test_registry_builds_strategies_by_name_and_alias():
    assert isinstance(get_chunker("fixed", chunk_size=100, overlap=0), FixedSizeChunker)
    assert isinstance(get_chunker("markdown"), StructureChunker)
    assert isinstance(get_chunker("parent-child"), ParentChildChunker)


def test_registry_reports_unknown_strategies_and_missing_dependencies():
    with pytest.raises(ValueError, match="Available"):
        get_chunker("magic")
    with pytest.raises(ValueError, match="embedding_service"):
        get_chunker("semantic")


def test_build_chunker_uses_the_strategy_params():
    chunker = build_chunker(
        "recursive",
        {"recursive": {"chunk_size": 123, "overlap": 7}, "fixed": {"chunk_size": 1}},
    )

    assert (chunker.chunk_size, chunker.overlap) == (123, 7)
    assert chunker.config()["chunk_size"] == 123


def test_register_chunker_adds_a_strategy():
    @register_chunker
    class WholeTextChunker(Chunker):
        name = "whole_text_test"

        def _chunk(self, text, document_id, metadata, prefix):
            return self._chunks_from_spans(text, [(0, len(text))], document_id, metadata, prefix)

    assert [chunk.text for chunk in get_chunker("whole_text_test").chunk("abc", "doc")] == ["abc"]
