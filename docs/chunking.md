# Chunking strategies

Chunking decides what a "piece of a document" is: the unit that gets
embedded, searched, ranked and finally shown to the LLM. The app supports ten
strategies behind one interface. This page explains how each one works, when
it fits, and which parameters matter. For measured results on a real corpus,
see [chunking_experiment.md](chunking_experiment.md).

## How chunking fits in the pipeline

```
Document (from IngestionPipeline)
  ↓  Chunker.chunk(text, document_id, metadata, chunk_id_prefix)
list[Chunk]          retrievable chunks + context-only chunks (parents, sections)
  ↓  IndexingService  embeds the retrievable chunks only
  ↓  Repository       stores text, vector, metadata (+ chunk_strategy, chunk_start,
  ↓                   chunk_end, parent_id, context_id, context_text, section_path)
  ↓  RetrievalService ranks chunks; with expand_context, swaps each matched child
                      for its stored context (parent / section), once per context
```

The strategy is chosen in `config.py` and built by the registry; nothing in
embedding, storage or retrieval knows which one is in use.

```python
# config.py
CHUNKING_STRATEGY = os.getenv("CHUNKING_STRATEGY", "fixed")
CHUNKING_PARAMS = {"recursive": {"chunk_size": 500, "overlap": 0}, ...}
```

```powershell
$env:CHUNKING_STRATEGY = "semantic"; python app.py
```

`CHUNKING_STRATEGY` must be a key of `CHUNKING_PARAMS`. In code,
`get_chunker` also accepts the aliases `markdown` (structure), `fixed_size`
and `parent-child`.

From code:

```python
from src.chunking.registry import available_chunkers, get_chunker

available_chunkers()                     # ['fixed', 'hierarchical', ...]
chunker = get_chunker("recursive", chunk_size=800)
chunks = chunker.chunk(text, document_id="doc-1", metadata={"filename": "a.txt"})
```

Each strategy and parameter set writes its own index file,
`vector_store.<strategy>-<fingerprint>.faiss`, where the fingerprint is a
hash of the parameters (the original fixed 500/50 setting keeps
`vector_store.faiss`). So chunks from two configurations are never mixed in
one search, changing a parameter builds a fresh index on the next run, and
switching back is free. Old index files are not deleted automatically.

Ingestion keeps a document's structure as Markdown markers: headings become
`#` lines, list items `- ` lines, code blocks are fenced with three
backticks, and tables have one `a | b` line per row, for Markdown, HTML and
DOCX files alike. That is what the structure-aware strategies below read.
PDF and plain text have no such markup, so for them the strategies fall back
to recognising short title-case lines as headings.

## The Chunk model

| Field | Meaning |
|---|---|
| `chunk_id` | `<tenant>:<document_id>_chunk_<n>` for retrievable chunks; context-only chunks use `_parent_<n>`, `_section_<n>`, `_paragraph_<n>`, `_document_0` |
| `document_id`, `text`, `chunk_index`, `metadata` | as before Phase 11 |
| `start`, `end` | character offsets into the document text: `text == source[start:end]`, except that structure-aware strategies may prepend a heading path line |
| `strategy` | the strategy that made it (`metadata_aware:<inner>` for routed chunks) |
| `parent_id`, `level` | the chunk one level up and the depth (parent-child: 0/1; hierarchical: 0–3) |
| `retrievable` | `False` for chunks that exist only as context; they are not embedded |
| `context_id`, `context` | the larger chunk the LLM should read when this one matches |

All strategies share the same guarantees, enforced by
`src/tests/test_chunkers.py`: blank text gives no chunks, every word of the
input lands in a retrievable chunk, ids are sequential, metadata is copied per
chunk, and a document shorter than one chunk is exactly one chunk.

## The strategies

Sizes are characters unless noted. Defaults are the values in `config.py`.

### `fixed` — fixed-size characters

Cuts every `chunk_size` characters and starts the next chunk `overlap`
characters earlier.

- **Use when** you need a predictable, cheap baseline, or the text has no
  usable structure at all.
- **Strengths:** trivial, deterministic, uniform chunk sizes, cost is exactly
  known.
- **Weaknesses:** ignores words and sentences. A fact that straddles a cut is
  in two halves, and each half is embedded next to unrelated text. Overlap
  only rescues facts shorter than the overlap.
- **Parameters:** `chunk_size` (500), `overlap` (50).

The default, and the only strategy used before Phase 11. One behaviour
changed: a trailing chunk lying entirely inside the previous chunk's overlap
is no longer produced.

### `sliding_window` — overlapping word windows

Windows of `window_size` words, advancing `step` words at a time. The last
window is moved back to end at the final word, so every window is full.

- **Use when** answers may sit anywhere and you want every position to be
  near the middle of some window; short, dense texts.
- **Strengths:** never cuts a word; heavy overlap means a fact is rarely cut
  in every window that contains it.
- **Weaknesses:** more chunks (more embeddings, more near-duplicate results
  competing for the top k); still blind to sentences and topics.
- **Parameters:** `window_size` (100 words), `step` (75 words; must not exceed
  `window_size`).

### `sentence` — whole sentences up to a size

Splits text into sentences (abbreviation-aware; blank lines, headings and
list items also end a sentence), then packs consecutive sentences up to
`max_chars`. With `overlap_sentences`, each chunk repeats the previous one's
last sentences, as long as there is room.

- **Use when** prose where facts are expressed within one or two sentences.
- **Strengths:** no chunk ends mid-sentence; cheap.
- **Weaknesses:** packing is greedy and topic-blind: a chunk can end one
  sentence into a new topic.
- **Parameters:** `max_chars` (500), `overlap_sentences` (1).

### `recursive` — the coarsest boundary that fits

If the text is longer than `chunk_size`, it is split at section headings;
pieces still too long are split at paragraphs, then lines, sentences, words
and finally characters. The pieces are then packed back together up to
`chunk_size`.

- **Use when** general-purpose default for mixed prose with paragraphs.
- **Strengths:** respects paragraphs where they exist and degrades gracefully
  where they don't; chunks are contiguous slices of the source.
- **Weaknesses:** it only knows `#` headings as section breaks, so in PDF or
  plain text greedy packing can glue a title-case heading to the end of the
  previous chunk; a transcript with no paragraphs falls back to
  sentence-level cuts.
- **Parameters:** `chunk_size` (500), `overlap` (0), `separators` (names from
  `spans.SEPARATORS` or regular expressions; `["line", "word"]` keeps table
  rows whole).

### `token` — tokens, measured like the model measures

Cuts every `max_tokens` tiktoken tokens (`cl100k_base`, the project's
tokenizer) with `overlap_tokens` of overlap, then widens each cut to whole
characters so multi-byte characters are never broken.

- **Use when** a hard budget in model tokens matters more than boundaries:
  embedding models with small input limits, or strict prompt budgets.
- **Strengths:** chunk cost in tokens is exact and uniform across languages.
- **Weaknesses:** the same boundary blindness as `fixed`, in token units;
  cuts land mid-word.
- **Parameters:** `max_tokens` (128), `overlap_tokens` (16).

### `semantic` — cut where the meaning changes

Splits sentences, embeds each sentence together with `buffer_size`
neighbours on each side, and measures the cosine distance between
consecutive sentence embeddings. A chunk ends where the distance is unusually
large: above the `breakpoint_threshold` percentile of the document's own
distances (`threshold_type="percentile"`), more than that many standard
deviations above the mean (`"std"`), or above a fixed distance
(`"absolute"`). Groups over `max_chars` are split again at their largest
internal distance; groups under `min_chars` merge into their most similar
neighbour. `SemanticChunker.analyze(text)` returns the sentences, distances,
threshold and cut points for inspection.

- **Use when** long text without reliable structure whose topic shifts
  mid-flow: transcripts, chat logs, extracted text with no paragraphs.
- **Strengths:** boundaries follow topics, so one chunk tends to hold one
  complete idea and its embedding is not diluted by a neighbouring topic.
Distances alone miss two things a reader relies on, so two rules adjust
them. With `respect_headings`, a chunk always ends before a heading, never
right after one, and small groups are never merged across one. With
`keep_references`, no cut is made before a sentence that opens by pointing
back ("This retry storm is why…", "It was routed…"), which would otherwise
separate a consequence from its cause when its wording changes sharply.
`analyze()` reports these as `forced` and `blocked` cuts.

- **Weaknesses:** one embedding per sentence at indexing time (about 5.7× the
  embedding calls of `fixed` in the experiment); boundaries depend on the
  embedding model and threshold; with headings respected, a long section
  whose sentences stay on topic becomes one large chunk, like `structure`;
  the back-reference rule is a word list, not an understanding of the text.
- **Parameters:** `breakpoint_threshold` and `threshold_type` (85th
  percentile), `buffer_size` (1), `max_chars` (1000), `min_chars` (150),
  `respect_headings` (True), `keep_references` (True).
  Needs an `EmbeddingService`; the container passes the app's own.

### `structure` — follow headings and blocks

Parses the text into blocks: Markdown headings (`#` and underlined), fenced
code, `|` tables, lists, paragraphs, and optionally plain-text headings
(short title-case lines followed by body text, which is how PDF and plain
text show headings). Blocks are grouped into
sections under their heading path, and each section's blocks are packed up to
`max_chars`. A chunk never spans two sections, except that sections shorter
than `min_section_chars` merge with the next. Tables are only split between
rows, lists between items, code between lines. With
`include_section_path`, chunk text starts with its heading path
(`Handbook > Leave > Sick leave`), also stored as `section_path` metadata.

- **Use when** handbooks, documentation, policies, READMEs: anything whose
  headings are meaningful.
- **Strengths:** a table, list or code block stays whole; every chunk says
  which section it belongs to, even from the middle of a long section.
- **Weaknesses:** a long section becomes one large chunk whose embedding
  averages many facts; on text without structure it is just sentence packing
  at `max_chars`; for PDF and plain text, heading detection is a
  heuristic that misses sentence-case headings.
- **Parameters:** `max_chars` (1000), `min_section_chars` (200),
  `include_section_path` (True), `detect_plain_headings` (True).

### `metadata_aware` — pick the strategy per document

Routes each document to a strategy using its metadata. The default rules:
CSV and JSON → `recursive` on lines (one row per line stays whole);
Markdown, HTML and DOCX → `structure`; everything else → `recursive`. Rules
can match any metadata field (`source_type`, `category`, `department`,
`tenant_id`, …), and a list matches any of its values.

```python
"metadata_aware": {
    "rules": [
        {"when": {"category": "policy"}, "strategy": "structure", "params": {"max_chars": 800}},
        {"when": {"source_type": ["txt"]}, "strategy": "semantic"},
    ],
    "fallback": {"strategy": "recursive", "params": {"chunk_size": 500}},
}
```

- **Use when** the corpus mixes document types, which most real corpora do.
- **Strengths:** each type gets a strategy that suits it, in one index.
- **Weaknesses:** only as good as the metadata and the rules; more
  configuration to maintain.

### `parent_child` — search small, answer from large

Splits recursively into parents of `parent_size`, and each parent into
children of `child_size`. Only children are embedded, so a match is precise;
each child stores its parent's text, and retrieval (with
`RETRIEVAL_EXPAND_CONTEXT`) hands the LLM the parent instead. Several
children of one parent collapse into one result.

- **Use when** answers need surrounding context (causes and effects, steps,
  multi-sentence explanations) but precise matching matters.
- **Strengths:** small chunks rank sharply; the LLM still sees the full
  surrounding passage, which fixes answers that span a chunk boundary.
- **Weaknesses:** the LLM reads far more text per question (about 2× `fixed`
  in the experiment), which costs tokens and adds noise; parent text is stored
  once per child (storage grows); collapsing children can return fewer than
  `top_k` contexts.
- **Parameters:** `parent_size` (2000), `child_size` (400), `child_overlap` (0).

### `hierarchical` — document → section → paragraph → chunk

Builds a tree: the whole document (level 0), sections by heading (level 1,
split at `section_max_chars`), paragraphs made of consecutive blocks (level 2,
up to `paragraph_max_chars`), and leaf chunks of blocks or sentences (level 3,
up to `chunk_size`). Every chunk points to its parent. Leaves are embedded;
each carries the text of its section (or paragraph, with
`context_level="paragraph"`) as context.

- **Use when** long structured documents where the right context size depends
  on the question; when you want the tree itself (navigation, summaries per
  section).
- **Strengths:** precise leaves plus a structurally meaningful context;
  leaves never mix two sections.
- **Weaknesses:** most chunks and most configuration; on unstructured text the
  "section" is the whole document part, so the context is large and
  unfocused.
- **Parameters:** `section_max_chars` (3000), `paragraph_max_chars` (1000),
  `chunk_size` (400), `min_section_chars` (200), `context_level` ("section"),
  `include_section_path`, `detect_plain_headings`.

## Choosing a strategy

There is no single best strategy; the experiment shows the winner changing by
document. As a starting point:

| Your documents | Try first | Why |
|---|---|---|
| Headed docs: handbooks, policies, wikis | `structure`, `hierarchical` | headings and tables are the real units |
| Transcripts, chat logs, text without paragraphs | `semantic`, `sentence` | only meaning or sentences mark boundaries |
| Tables exported to CSV/JSON lines | `recursive` with `separators=["line", "word"]` | a row must stay whole |
| Multi-sentence answers (causes, procedures) | `parent_child` | match small, read large |
| A mix of all of the above | `metadata_aware` | route each type to its strategy |
| Unknown, need a baseline | `recursive`, then `fixed` as a control | cheap, reasonable, comparable |

Then measure on your own documents and questions with the experiment runner;
see [chunking_experiment.md](chunking_experiment.md#reproducing-and-extending).

## Adding a strategy

Subclass `Chunker`, give it a `name`, implement `_chunk(text, document_id,
metadata, prefix)` (usually by computing `(start, end)` spans and calling
`self._chunks_from_spans(...)`), and register it:

```python
from src.chunking.base import Chunker
from src.chunking.registry import register_chunker
from src.chunking.spans import SEPARATORS, split_by_pattern

@register_chunker
class ParagraphChunker(Chunker):
    name = "paragraph"

    def _chunk(self, text, document_id, metadata, prefix):
        spans = split_by_pattern(text, 0, len(text), SEPARATORS["paragraph"])
        return self._chunks_from_spans(text, spans, document_id, metadata, prefix)
```

Add its parameters to `CHUNKING_PARAMS` and it is selectable with
`CHUNKING_STRATEGY=paragraph`. Add it to `small_chunkers()` in
`src/tests/test_chunkers.py` and the shared contract tests run against it.
