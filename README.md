# RAG Document Q&A

Ask questions about your own PDFs and get answers grounded in their actual
content, with the source page cited.

The app reads every PDF in `documents/`, splits it into overlapping pieces,
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

**4. Add your PDFs**

Put any PDF files into the `documents/` folder. They are picked up
automatically; no configuration needed.

Optionally, describe a PDF with a metadata file next to it, named after the
PDF with `.meta.json` in place of `.pdf`:

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
  "author": "HR Team"
}
```

Every field is optional and must be a string. Any other field name is
rejected, so a typo like `departmnet` fails loudly instead of silently never
matching a filter.

## Running it

```powershell
python app.py
```

**First run** reads every PDF, embeds the chunks, and saves the index to disk:

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

### Adding new documents later

Drop the new PDF into `documents/` and run again. Only the new file is
embedded — existing documents are recognised by a hash of their contents and
skipped. Identical files are detected even if they have different names, as
long as they belong to the same tenant: the same file uploaded by two tenants
is indexed once for each.

Adding or editing a `.meta.json` file for an already-indexed PDF takes effect
on the next run: the stored metadata is updated in place (`Updated metadata of
page 1`) without re-embedding anything. The exception is `tenant_id` — see
[Known limitations](#known-limitations).

To rebuild everything from scratch, delete the index files:

```powershell
del vector_store.faiss vector_store.faiss.json
```

## Cost

Two OpenAI calls per question — one to embed the question, one to generate the
answer. Indexing costs one embedding call per page, and only ever runs once per
document.

## How it works

```
documents/*.pdf (+ optional *.meta.json)
    ↓  ingest_pdf        validate, extract with pypdf, clean, one Document per page,
    ↓                    attach file, PDF-embedded and .meta.json metadata
    ↓  IndexingService   skip pages this tenant already indexed, 500-character
    ↓                    chunks (50 overlap), each carrying the page's metadata
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

## Metadata and filtering

### What is stored

Each record in the vector store is `chunk_id`, `text`, `embedding` and
`metadata`. The metadata comes from three places; later rows win:

| Field | Where it comes from |
|---|---|
| `file_size`, `source_type` | the file itself (`source_type` is `"pdf"`) |
| `author`, `date` | embedded in the PDF, if present (`date` as `YYYY-MM-DD`) |
| `department`, `category`, `date`, `author`, `tenant_id` | the `.meta.json` file |
| `tenant_id` | `"default"` (`DEFAULT_TENANT_ID`) when nothing names one |
| `document_id`, `filename`, `page` | set during indexing |

The `.meta.json` file overrides the PDF's own `author` because that is often
just the computer account that exported it (both sample PDFs say `dell`).

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
place, adding `tenant_id`, `filename`, `source_type`, `author`, `date` and any
`.meta.json` fields, without re-embedding. Their vectors and chunk ids stay
as they were.

Older chunks have no tenant yet. The first tenant to index their PDF adopts
them: the `.meta.json` tenant if there is one, otherwise `default`.

## Project structure

```
app.py                      entry point: builds services, indexes, runs the question loop
config.py                   all settings (reads .env)
logger.py                   logging setup
documents/                  put your PDFs here
vector_store.faiss          saved index (git-ignored)
vector_store.faiss.json     saved chunk text + metadata (git-ignored)

src/
  container.py   constructs and connects every service (the only place
                 that names FAISS or OpenAI classes)
  ingestion/     PDF → clean text
    loader.py      file validation, content-hash ids, .meta.json, ingest_pdf
    parser.py      pypdf text and metadata extraction
    cleaner.py     whitespace normalisation
    models.py      Document
  chunking/      text → overlapping pieces
    fixed.py       sliding-window splitter
    models.py      Chunk
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
  indexing/      service.py — Document → chunks → embeddings → repository
  retrieval/     service.py — question (+ filters) → embedding → repository → top-k chunks
  generation/    retrieved chunks → answer
    llm.py         LLM interface and OpenAI chat model
    prompt.py      prompt construction, source formatting
    service.py     GenerationService — prompt → LLM
  services/      rag_service.py — RAGService: retrieval → generation
  tests/         pytest suite (no API calls; uses fake embeddings and LLM)
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
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | chunk length and overlap, in characters |
| `TOP_K` | how many chunks are retrieved per question |
| `DEFAULT_TENANT_ID` | tenant given to documents whose metadata names none |
| `DOCUMENTS_DIR`, `VECTOR_STORE_PATH` | where PDFs are read from and the index is saved |

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

## Troubleshooting

**`ModuleNotFoundError: No module named 'faiss'`**
The virtual environment isn't active, or dependencies aren't installed. Run
`.\.venv\Scripts\Activate.ps1` then `pip install -r requirements.txt`.

**`openai.AuthenticationError`**
`OPENAI_API_KEY` in `.env` is missing, wrong, or still the placeholder value.

**`ValueError: Cannot search an empty vector index.`**
No PDFs were indexed. Check that `documents/` contains at least one `.pdf`.

**`UnicodeEncodeError` when printing**
Should not happen — `app.py` reconfigures stdout to UTF-8 on startup. If you
see it from a different script, set `$env:PYTHONIOENCODING="utf-8"` first.

**`FAISS index and stored records are out of sync.`**
The two index files don't match each other. Delete both and let them rebuild.

## Known limitations

- No retry around the OpenAI calls. A failed question is logged and the loop
  continues; a failure while indexing is logged, the chunks embedded so far
  are saved, and the app exits.
- Chunks are split at a fixed character count, so sentences can be cut in half.
  The 50-character overlap limits the damage but doesn't eliminate it.
- Chunks from a PDF that is later edited or deleted stay in the index. Delete
  the index files to rebuild.
- Changing the `tenant_id` of a PDF that is already indexed embeds a new copy
  for the new tenant and leaves the old copy with the old tenant. Rebuild the
  index to move a document between tenants.
- An identical copy of a PDF under a different name (same content hash) is
  skipped, so it never gets its own metadata or sources.
