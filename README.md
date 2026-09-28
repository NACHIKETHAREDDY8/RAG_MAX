# RAG Document Q&A

Ask questions about your own documents and get answers grounded in their
actual content, with the source file (and page, for PDFs) cited.

The app reads every PDF, Word (.docx), text, Markdown, HTML, CSV and JSON
file in `documents/`, splits it into pieces (chunks) with a configurable
[chunking strategy](#chunking-strategies),
converts each piece into an embedding vector, and stores them in a FAISS index.
When you ask a question, it finds the 5 most relevant pieces and asks an OpenAI
model to answer using only those — so it cannot invent facts that aren't in your
documents.

Every chunk carries metadata (file, page, department, category, date, author,
tenant), so a search can be limited to, say, one company's HR policies — see
[Metadata and filtering](#metadata-and-filtering).

## Requirements

- Python 3.11
- An OpenAI API key

## Setup

Run these once, from the project folder.

**1. Create and activate a virtual environment**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On Git Bash or macOS/Linux use `source .venv/bin/activate` (or
`source .venv/Scripts/activate` on Windows Git Bash).

**2. Install the dependencies**

```powershell
pip install -r requirements.txt
```

**3. Create your `.env` file**

Copy the template and fill in your real key:

```powershell
copy .env.example .env
```

Then edit `.env`:

```
APP_NAME=RAG Application
ENVIRONMENT=development
LOG_LEVEL=INFO
OPENAI_API_KEY=sk-your-real-key-here
```

`.env` is git-ignored — your key never gets committed.

**4. Add your documents**

Put your files into the `documents/` folder. Every
[supported format](#supported-formats) is picked up automatically; no
configuration needed.

Optionally, describe a document with a metadata file next to it, named after
the document with `.meta.json` in place of its extension:

```
documents/leave_policy.pdf
documents/leave_policy.meta.json
```

```json
{
  "tenant_id": "company_A",
  "department": "HR",
  "category": "policy",
  "date": "2026-01-15",
  "author": "HR Team",
  "title": "Leave Policy 2026"
}
```

Every field is optional and must be a string. Any other field name is
rejected, so a typo like `departmnet` fails loudly instead of silently never
matching a filter.

## Running it

```powershell
python app.py
```

**First run** reads every document, embeds the chunks, and saves the index to disk:

```
Processing: my-document.pdf
Extracted 2 pages
Total chunks: 9
...
Saved 12 chunks to vector_store.faiss
Ask a question, or type 'exit' to quit.
Question:
```

**Every run after that** loads the saved index instead of re-embedding, so it
starts instantly and costs nothing:

```
Loaded 12 stored chunks from vector_store.faiss
Processing: my-document.pdf
Already indexed, skipping page 1
Already indexed, skipping page 2
Ask a question, or type 'exit' to quit.
Question:
```

Type a question and press Enter. Type `exit` or `quit` to stop.

### Example

```
Question: What GPU work has she done?

Answer: She optimized multi-GPU training and inference workflows using
CUDA-enabled environments, improving accelerator utilization by 41%.

Sources:
- default:c0bb6be9c690bce5-1_chunk_1 | Source: resume.pdf | Page: 1 | Document: c0bb6be9c690bce5-1
```

Files that cannot be read are reported and skipped; the rest are still
indexed:

```
Processing: slides.pptx
Skipped slides.pptx: Unsupported file type '.pptx' for slides.pptx. Supported extensions: .csv, .docx, ...
Processing: scan.pdf
No text found in scan.pdf, skipping
```

### Adding new documents later

Drop the new file into `documents/` and run again. Only the new file is
embedded. Existing documents are recognised by the SHA-256 hash of their
contents and skipped. Identical files are detected even if they have different
names (`Duplicate of a.pdf, skipping page 1`), as long as they belong to the
same tenant: the same file uploaded by two tenants is indexed once for each.

### Editing a document (versions)

Edit a file in `documents/` and run again: the new content is embedded and
**replaces** the old one, so answers never mix old and new text. Each chunk
records which version it is:

| Field | Meaning |
|---|---|
| `version` | 1 for the first content seen under this filename (per tenant), then 2, 3, ... |
| `previous_version` | the hash prefix (`document_id` before the `-`) of the version it replaced |

A version is a distinct content hash under the same filename and tenant.
Re-running without changes keeps the same version. Search with
`filters={"version": 2}` to see which chunks came from an edit.

Adding or editing a `.meta.json` file for an already-indexed document takes effect
on the next run: the stored metadata is updated in place (`Updated metadata of
page 1`) without re-embedding anything. The exception is `tenant_id` — see
[Known limitations](#known-limitations).

To rebuild everything from scratch, delete the index files:

```powershell
del vector_store.faiss vector_store.faiss.json
```

## Cost

Two OpenAI calls per question — one to embed the question, one to generate the
answer. Indexing costs one embedding call per PDF page or non-PDF file, and
only runs again for a document when its content changes.

## How it works

```
documents/* (+ optional *.meta.json)
    ↓  IngestionPipeline validate → detect type → pick parser → parse → clean
    ↓                    → metadata → SHA-256 → one Document per PDF page,
    ↓                    one per other file (see "Ingestion architecture")
    ↓  IndexingService   skip documents this tenant already indexed (hash),
    ↓                    resolve the version, chunk with CHUNKING_STRATEGY
    ↓                    (default: 500 characters, 50 overlap) carrying the
    ↓                    metadata, retire older versions
    ↓  EmbeddingService  OpenAI → 1,536 numbers per chunk
    ↓  Repository        stores chunk_id + text + embedding + metadata in the
    ↓                    VectorStore (FAISS), saves to disk

your question (+ optional filters)
    ↓  RAGService
    ↓  RetrievalService  embed the question
    ↓  VectorStore       keep only chunks matching every filter,
    ↓                    then rank those by similarity → top_k chunks
    ↓  GenerationService "use only this context, cite Source and Page" → gpt-4o-mini
    ↓  answer + sources (filename, page, document id)
```

## Supported formats

| Format | Extensions | How text is extracted | Format metadata |
|---|---|---|---|
| PDF | `.pdf` | pypdf, one Document per page | `author`, `date`, `page_count` |
| Word | `.docx` | python-docx; paragraphs and tables in document order, one line per table row; heading and list styles become `#` and `- ` lines | `author`, `title`, `date` |
| Text | `.txt`, `.text` | as-is | `encoding` |
| Markdown | `.md`, `.markdown` | rendered with markdown-it-py, then read as HTML; inline formatting and link URLs dropped, headings, list items, code fences and table rows kept | `title` (front matter or first `#` heading), `author`, `date` (front matter), `encoding` |
| HTML | `.html`, `.htm` | BeautifulSoup; visible text only, one block element per line; `<h1>`–`<h6>` become `#` lines, `<li>` `- ` lines, `<pre>` fenced code | `title`, `author`, `date` (from `<meta>`), `encoding` |
| CSV | `.csv` | one `column: value` line per row; delimiter detected | `row_count`, `column_count`, `encoding` |
| JSON | `.json` | one `path.to.key: value` line per value | `encoding` |

Only PDFs have pages. Other formats are a single Document with no `page`, so
their sources cite the file alone rather than a made-up "Page 1".

CSV rows and JSON values repeat their column name or key path on every line
because chunks are cut at a fixed length: a chunk from the middle of a large
table still says what its numbers mean.

Text files are decoded as UTF-8 (with or without BOM), UTF-16 with a BOM, or
else Windows-1252, the encoding Windows tools often save in.

## Ingestion architecture

```
file path
  → validation.py          exists, is a file, not empty, ≤ MAX_FILE_SIZE_MB
  → detection.py           FileType from the extension (else the MIME type),
                           then check the content matches: %PDF header, DOCX
                           zip with word/document.xml, no binary in text formats
  → parsers/factory.py     ParserFactory picks the parser for that FileType
  → parsers/*_parser.py    format-specific parser (all extend BaseParser)
  → ParsedDocument         the normalized result: sections + format metadata
  → cleaner.py             line endings, whitespace, invisible characters
  → metadata.py            file facts + format metadata + .meta.json sidecar
  → hashing.py             SHA-256 of the file → document_id "<hash16>-<section>"
  → Document(s)            what IndexingService receives

IndexingService (src/indexing/)
  → duplicate detection    this tenant already has this document_id? skip
  → versioning.py          version number from what is stored for this filename
  → chunker                the Chunker built from CHUNKING_STRATEGY
  → embed, store, and remove chunks of older versions
```

Ingestion ends at Documents; indexing starts there. Duplicate detection and
versioning live in indexing because both depend on what is already stored,
and ingestion never touches the vector store.

Every ingestion failure raises a subclass of `IngestionError`
(`FileValidationError`, `UnsupportedFileTypeError`, `ParserError`,
`MetadataError`). A parser library's own exception, such as a corrupt PDF,
is wrapped in `ParserError` by `BaseParser.parse`, so callers catch one type.
`app.py` reports these and moves on to the next file. Any other error, such as
an OpenAI failure, still stops the run after saving what was already embedded.

To support another format, write a `BaseParser` subclass that implements
`_parse(path) -> ParsedDocument`, add its extension to `EXTENSION_TYPES` in
`detection.py`, and register it in `default_parser_factory()`.

Use the pipeline directly from code:

```python
from src.ingestion.pipeline import IngestionPipeline

result = IngestionPipeline().ingest("documents/leave_policy.docx")
result.file_type     # FileType.DOCX
result.file_hash     # full SHA-256
result.documents     # list[Document], ready for IndexingService.index_document
```

`ingest(path, mime_type="text/csv")` accepts a MIME type for files whose
extension says nothing, such as uploads saved under a temporary name.

## Chunking strategies

How documents are cut into chunks is configurable. Ten strategies share one
interface: `fixed` (the default, unchanged behaviour), `sliding_window`,
`sentence`, `recursive`, `token`, `semantic`, `structure` (Markdown and
document structure), `metadata_aware` (a strategy per document type),
`parent_child` and `hierarchical`. Pick one with an environment variable:

```powershell
$env:CHUNKING_STRATEGY = "recursive"; python app.py
```

or in `.env` (`CHUNKING_STRATEGY=recursive`). Parameters live in
`CHUNKING_PARAMS` in `config.py`. Each strategy and parameter set keeps its
own index file, so switching strategy or changing a parameter re-indexes
once and never mixes chunks. With
`parent_child` and `hierarchical`, the LLM receives the larger parent or
section around each matched chunk.

- [docs/chunking.md](docs/chunking.md): how each strategy works, when to use
  it, strengths, weaknesses and parameters.
- [docs/chunking_experiment.md](docs/chunking_experiment.md): the strategies
  compared on one corpus with the same questions, embedding model and k, and
  why they retrieve differently. Re-run it with
  `python -m src.experiments.chunking` (add `--offline` for a free run).

## Metadata and filtering

### What is stored

Each record in the vector store is `chunk_id`, `text`, `embedding` and
`metadata`. The metadata comes from three places; later rows win:

| Field | Where it comes from |
|---|---|
| `file_size`, `source_type`, `mime_type`, `file_hash` | the file itself; `source_type` is `pdf`, `docx`, `txt`, `markdown`, `html`, `csv` or `json` |
| `author`, `date`, `title`, `page_count`, `row_count`, ... | recorded by the format, when present (see [Supported formats](#supported-formats); `date` as `YYYY-MM-DD`) |
| `department`, `category`, `date`, `author`, `title`, `tenant_id` | the `.meta.json` file |
| `tenant_id` | `"default"` (`DEFAULT_TENANT_ID`) when nothing names one |
| `version`, `previous_version` | set during indexing (see [Editing a document](#editing-a-document-versions)) |
| `document_id`, `filename`, `page` | set during indexing; `page` only for PDFs |

The `.meta.json` file overrides the document's own `author` because that is
often just the computer account that exported it (both sample PDFs say
`dell`).

Every field can be filtered on, for example
`filters={"source_type": "csv", "department": "Finance"}`.

### Filtering

`RetrievalService.retrieve` and `RAGService.answer` / `answer_with_context`
take an optional `filters` dictionary:

```python
from src.container import build_container

rag = build_container().rag_service

context = rag.retrieval_service.retrieve(
    "What is the leave policy?",
    top_k=10,
    filters={"department": "HR", "category": "policy"},
)
answer, context = rag.answer_with_context(
    "What is the leave policy?",
    filters={"tenant_id": "company_A", "department": "HR"},
)
```

- A chunk matches when its metadata **equals every** filter value (AND).
  Matching is exact and case-sensitive: `"HR"` does not match `"hr"`.
- A chunk missing a filtered field never matches.
- No matching chunks returns an empty list. `RAGService` then answers
  "No matching documents were found for this question." without calling the
  LLM.
- `filters=None` (the default) or `{}` searches everything, exactly as before.

### Filtering before vs after vector search

Filtering happens **before** ranking. The FAISS store finds the matching
records, then asks FAISS to score only those (`IDSelectorBatch`), so a
filtered search still returns up to `top_k` results.

The alternative, searching for the `top_k` closest chunks and then dropping
the ones that don't match, is simpler but wrong: if the closest chunks belong
to another department, you get back fewer results than asked for, often none.
`test_filtered_search_fills_top_k_from_matches` fails if the store is
switched to that approach.

The cost is a Python pass over every record's metadata per filtered query,
which is fine at this scale. A dedicated vector database (Chroma, Qdrant,
pgvector) does the same filtering with an index.

### Tenant isolation

Every indexed chunk gets a `tenant_id`. Passing
`filters={"tenant_id": "company_A"}` guarantees no other tenant's chunk is
even scored, because records without that exact value never match.

Chunk ids start with the tenant (`company_A:<document_id>_chunk_0`), so the
same file indexed for two tenants still has unique chunk ids. Records indexed
before this change keep their old ids.

Isolation depends on the caller always passing `tenant_id`: a search without
it sees every tenant. The terminal app in `app.py` is single-user and does not
filter.

### Source attribution

Each result exposes `filename`, `page` and `document_id`. They are printed
under every answer and included in the prompt, which asks the model to cite
the Source and Page each part of its answer comes from.

### Indexes built before metadata filtering

No rebuild is needed. The next `python app.py` run upgrades older chunks in
place, adding `tenant_id`, `filename`, `source_type`, `author`, `date`, any
`.meta.json` fields and, since multi-format ingestion, `mime_type`,
`file_hash`, `page_count` and `version`, without re-embedding. PDF document ids
are computed exactly as before, so existing PDFs are recognised. Their vectors
and chunk ids stay as they were.

Older chunks have no tenant yet. The first tenant to index their PDF adopts
them: the `.meta.json` tenant if there is one, otherwise `default`.

## Project structure

```
app.py                      entry point: builds services, indexes, runs the question loop
config.py                   all settings (reads .env)
logger.py                   logging setup
documents/                  put your documents here
vector_store.faiss          saved index (git-ignored)
vector_store.faiss.json     saved chunk text + metadata (git-ignored)

src/
  container.py   constructs and connects every service (the only place
                 that names FAISS or OpenAI classes)
  ingestion/     any supported file → clean Documents
    pipeline.py    IngestionPipeline (runs the stages below), find_documents
    validation.py  exists / is a file / not empty / size limit
    detection.py   FileType from extension or MIME type, content signature check
    parsers/
      base.py        BaseParser (wraps failures in ParserError), text decoding
      factory.py     ParserFactory: FileType → parser
      pdf_parser.py, docx_parser.py, text_parser.py, markdown_parser.py,
      html_parser.py, csv_parser.py, json_parser.py
    cleaner.py     whitespace and invisible-character normalisation
    metadata.py    file + format + .meta.json metadata
    hashing.py     SHA-256 and document ids
    errors.py      IngestionError and its subclasses
    models.py      ParsedSection, ParsedDocument (parser output), Document
  chunking/      text → chunks; ten strategies behind one interface (docs/chunking.md)
    base.py        Chunker interface
    models.py      Chunk (offsets, strategy, parent, context)
    registry.py    get_chunker / build_chunker / register_chunker
    spans.py       character spans, sentence splitting, packing
    fixed.py, sliding_window.py, sentence.py, recursive.py, token.py,
    semantic.py, structure.py, metadata_aware.py, parent_child.py,
    hierarchical.py
  experiments/chunking/  compare strategies on one corpus (docs/chunking_experiment.md)
    runner.py      same corpus, questions, embeddings and k for every strategy
    metrics.py     precision, MRR, recall, completeness from evidence offsets
    dataset.py     questions with gold evidence passages
    report.py      Markdown comparison report
  tokenization/  measuring text in model units
    tokenizer.py   tiktoken encode / count / validate
  embeddings/    text → vectors
    base.py        EmbeddingProvider interface
    provider.py    OpenAI implementation
    service.py     batching and validation
  vector_store/  storing and searching vectors
    base.py        VectorStore interface
    faiss_store.py FAISS implementation, cosine similarity, filters, save/load
    filters.py     metadata filter matching shared by any VectorStore
    models.py      VectorRecord, SearchResult (with source fields)
  repositories/  vector_store_repository.py — chunks in and out of any VectorStore
  indexing/      Document → chunks → embeddings → repository
    service.py     IndexingService: duplicates, chunking, metadata refresh
    versioning.py  version numbers per filename, retiring old versions
  retrieval/     service.py — question (+ filters) → embedding → repository → top-k chunks
  generation/    retrieved chunks → answer
    llm.py         LLM interface and OpenAI chat model
    prompt.py      prompt construction, source formatting
    service.py     GenerationService — prompt → LLM
  services/      rag_service.py — RAGService: retrieval → generation
  tests/         pytest suite (no API calls; uses fake embeddings and LLM)

experiments/chunking/       experiment corpus, questions, config and results
docs/                       chunking guide and experiment report
```

To use a different vector database (for example Chroma), implement
`VectorStore` from `src/vector_store/base.py` and construct it in
`src/container.py`. Nothing else changes.

## Configuration

Everything lives in `config.py`:

| Setting | Meaning |
|---|---|
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION` | embedding model and its vector size |
| `CHAT_MODEL` | model that writes the answer |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | chunk length and overlap, in characters, for the `fixed` strategy |
| `CHUNKING_STRATEGY` | which chunker to use (env var; default `fixed`) — see [Chunking strategies](#chunking-strategies) |
| `CHUNKING_PARAMS` | parameters of every strategy |
| `RETRIEVAL_EXPAND_CONTEXT` | answer from the parent/section of a matched chunk, for strategies that store one |
| `TOP_K` | how many chunks are retrieved per question |
| `DEFAULT_TENANT_ID` | tenant given to documents whose metadata names none |
| `MAX_FILE_SIZE_MB` | larger documents are skipped before being read |
| `DOCUMENTS_DIR`, `VECTOR_STORE_PATH` | where documents are read from and the index is saved (`vector_store.<strategy>-<parameter hash>.faiss` for anything but the original fixed 500/50) |

## Tests

```powershell
python -m pytest
```

The tests run offline and cost nothing.

`src/tests/test_metadata_filtering.py` covers metadata filtering: no filter,
one filter, multiple filters, no matching metadata, tenant filtering, `top_k`
with filters, persistence of metadata, `.meta.json` handling, per-tenant
duplicate detection, source attribution, and a full question → filtered
retrieval → prompt → answer + sources flow.

Ingestion has three files:

- `test_parsers.py`: each of the seven parsers, including encodings, tables,
  front matter, hidden HTML, CSV dialects, nested JSON and corrupt files.
- `test_ingestion.py`: validation, type detection, parser selection, document
  ids and metadata, and `app.index_documents` skipping bad files. It also
  indexes one file of every format and searches it with filters.
- `test_versioning.py`: version numbers, replacing old versions, and deleting
  from the FAISS store.

Chunking has three files:

- `test_chunkers.py`: the contract every strategy shares (blank text, every
  word in some chunk, valid offsets, sequential ids, copied metadata, short
  documents), plus each strategy's own rules and edge cases: overlap
  boundaries, abbreviations, over-long sentences and words, Unicode and
  multi-byte characters, headings, tables, code blocks, lists and routing by
  metadata.
- `test_chunking_pipeline.py`: a chosen chunker through indexing, storage,
  metadata refresh, context expansion at retrieval, and the container.
- `test_chunking_experiment.py`: evidence location, metrics, the embedding
  cache, and a complete offline experiment run.

Sample files are generated by `src/tests/sample_files.py`; nothing is read
from `documents/`.

## Troubleshooting

**`ModuleNotFoundError: No module named 'faiss'`**
The virtual environment isn't active, or dependencies aren't installed. Run
`.\.venv\Scripts\Activate.ps1` then `pip install -r requirements.txt`.

**`openai.AuthenticationError`**
`OPENAI_API_KEY` in `.env` is missing, wrong, or still the placeholder value.

**`ValueError: Cannot search an empty vector index.`**
Nothing was indexed. Check that `documents/` contains at least one supported
file with text, and look for `Skipped ...` lines in the output.

**`Skipped x.pdf: x.pdf is not a valid PDF file.`**
The file's content does not match its extension, for example a web page
saved as `.pdf`. Rename it to its real type or export it again.

**`No text found in scan.pdf, skipping`**
The PDF is scanned images with no text layer. Run it through OCR first.

**`UnicodeEncodeError` when printing**
Should not happen — `app.py` reconfigures stdout to UTF-8 on startup. If you
see it from a different script, set `$env:PYTHONIOENCODING="utf-8"` first.

**`FAISS index and stored records are out of sync.`**
The two index files don't match each other. Delete both and let them rebuild.

## Known limitations

- No retry around the OpenAI calls. A failed question is logged and the loop
  continues; a failure while indexing is logged, the chunks embedded so far
  are saved, and the app exits.
- The default `fixed` strategy splits at a fixed character count, so sentences
  can be cut in half; the other strategies avoid this at other costs (see
  [docs/chunking.md](docs/chunking.md)). Each chunking configuration gets its
  own index file and old ones are not deleted; remove unused
  `vector_store.*.faiss` files by hand.
- Chunks from a document that is deleted from `documents/` stay in the index,
  and so do old versions of a file that was renamed. Delete the index files to
  rebuild.
- Only the latest version of a file is kept; older versions cannot be searched
  or restored.
- If an edit makes a file identical to another file the tenant already
  indexed, it is skipped as a duplicate and its old version stays.
- Changing the `tenant_id` of a document that is already indexed embeds a new
  copy for the new tenant and leaves the old copy with the old tenant. Rebuild
  the index to move a document between tenants.
- An identical copy of a document under a different name (same content hash)
  is skipped, so it never gets its own metadata or sources.
- Two documents with the same name and different extensions (`report.pdf`,
  `report.docx`) share `report.meta.json`.
- Scanned PDFs without a text layer are not read (no OCR). DOCX headers,
  footers and comments are not extracted.
