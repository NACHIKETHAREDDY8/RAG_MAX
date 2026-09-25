# RAG Document Q&A

Ask questions about your own PDFs and get answers grounded in their actual
content, with the source page cited.

The app reads every PDF in `documents/`, splits it into overlapping pieces,
converts each piece into an embedding vector, and stores them in a FAISS index.
When you ask a question, it finds the 5 most relevant pieces and asks an OpenAI
model to answer using only those — so it cannot invent facts that aren't in your
documents.

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
- c0bb6be9c690bce5-1_chunk_1 | Source: resume.pdf | Page: 1
```

### Adding new documents later

Drop the new PDF into `documents/` and run again. Only the new file is
embedded — existing documents are recognised by a hash of their contents and
skipped. Identical files are detected even if they have different names.

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
documents/*.pdf
    ↓  ingest_pdf        validate, extract with pypdf, clean, one Document per page
    ↓  IndexingService   skip already-indexed pages, 500-character chunks (50 overlap)
    ↓  EmbeddingService  OpenAI → 1,536 numbers per chunk
    ↓  Repository        stores chunks in the VectorStore (FAISS), saves to disk

your question
    ↓  RAGService
    ↓  RetrievalService  embed the question → Repository → 5 closest chunks
    ↓  GenerationService "use only this context, invent nothing" → gpt-4o-mini
    ↓  answer + sources
```

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
    loader.py      file validation, content-hash ids, ingest_pdf
    parser.py      pypdf text extraction
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
    faiss_store.py FAISS implementation, cosine similarity, save/load
    models.py      VectorRecord, SearchResult
  repositories/  vector_store_repository.py — chunks in and out of any VectorStore
  indexing/      service.py — Document → chunks → embeddings → repository
  retrieval/     service.py — question → embedding → repository → top-k chunks
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
| `DOCUMENTS_DIR`, `VECTOR_STORE_PATH` | where PDFs are read from and the index is saved |

## Tests

```powershell
python -m pytest
```

The tests run offline and cost nothing.

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
