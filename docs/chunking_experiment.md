# Chunking experiment: what changed retrieval, and why

This report compares the Phase 11 chunking strategies on one corpus and one
question set. It interprets the generated numbers in
[`experiments/chunking/results/phase11/report.md`](../experiments/chunking/results/phase11/report.md),
which also holds the full per-question tables and chunk-boundary case
studies. How each strategy works is described in [chunking.md](chunking.md).

**The short version:** no strategy was best everywhere. Which one won depended
on the shape of the document and the shape of the answer: whether the text
has headings, whether topics shift without paragraph breaks, and whether an
answer fits in one sentence or spans paragraphs. Most questions (22 of 35)
were answered completely by every configuration; the differences come from
the other 13, and nearly all of them trace back to where a chunk boundary
fell.

## Setup

Seven synthetic documents (about 19,000 characters), written to have
different shapes and to include *hard negatives*: text on the same topic with
different facts, as real corpora have.

| Document | Shape | Role |
|---|---|---|
| `employee_handbook.md` | Markdown: headings, a table, a code block, a list | structured |
| `engineering_onboarding.md` | Markdown, overlaps the handbook (VPN, laptops, security) | structured, hard negative |
| `quarterly_review_transcript.txt` | Q3 meeting transcript: one paragraph, six topics | unstructured, topic shifts |
| `q2_business_review_transcript.txt` | Q2 transcript: same agenda, different numbers | hard negative |
| `incident_postmortem.txt` | checkout outage: headed paragraphs, causal chains | structured prose |
| `search_outage_postmortem.txt` | second outage, same vocabulary | hard negative |
| `office_directory.csv` | 10 rows × 8 columns | tabular |

**35 questions**, each with gold *evidence*: the exact passages a complete
answer needs, located by character offset in the ingested text. 17 questions
need two or three passages, some in different paragraphs.

**Held constant for every strategy:** the ingested documents, the questions,
the embedding model (`text-embedding-3-small`), the vector store (FAISS,
cosine), the production `IndexingService` and `RetrievalService`, k ∈ {1, 3,
5}, and the evaluation code. Only the chunker changes. Parent-child and
hierarchical run with context expansion on, as the app would.

**Two controls:** `fixed_1000` is the fixed strategy at double size. It
separates "better boundaries" from "simply bigger chunks", a confound that
otherwise makes large-chunk strategies look smarter than they are.
`semantic_plain` is the semantic chunker with its heading and back-reference
rules switched off, as it was in the first run (see
[Fixes after the first run](#fixes-after-the-first-run)).

Metrics (defined precisely at the end of the generated report): *precision*,
*hit* and *MRR* describe how well the retrieved chunks rank; *completeness*
(share of evidence characters delivered to the LLM) and *complete answers*
(questions with every passage delivered) describe whether the answer reaches
the LLM; *context chars* is what the LLM has to read.

## Results

At k = 3 (headline), plus completeness at k = 1:

| Strategy | Chunks | Avg chars | Texts embedded | Precision@3 | MRR@3 | Completeness@1 | Completeness@3 | Complete answers@3 | Context chars@3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed | 45 | 465 | 45 | 0.39 | 0.87 | 0.67 | 0.91 | 0.83 | 1,444 |
| fixed_1000 | 23 | 896 | 23 | 0.37 | 0.88 | 0.76 | 0.96 | 0.94 | 2,805 |
| sliding_window | 54 | 485 | 54 | 0.46 | 0.89 | 0.75 | 0.97 | 0.94 | 1,464 |
| sentence | 51 | 440 | 51 | 0.43 | 0.90 | 0.79 | 0.94 | 0.91 | 1,328 |
| recursive | 51 | 372 | 51 | 0.36 | 0.91 | 0.80 | 0.94 | 0.91 | 1,161 |
| token | 43 | 488 | 43 | 0.40 | 0.84 | 0.63 | 0.94 | 0.89 | 1,522 |
| semantic | 43 | 441 | 258 | 0.32 | 0.90 | 0.84 | 0.93 | 0.91 | 1,542 |
| semantic_plain | 39 | 487 | 254 | 0.34 | 0.86 | 0.75 | 0.95 | 0.91 | 1,795 |
| structure | 35 | 563 | 35 | 0.32 | 0.85 | 0.75 | 0.93 | 0.91 | 1,787 |
| metadata_aware | 48 | 410 | 48 | 0.36 | 0.91 | 0.80 | 0.94 | 0.91 | 1,228 |
| parent_child | 64 | 296 | 64 | 0.32 | 0.83 | 0.83 | 0.97 | 0.97 | 3,114 |
| hierarchical | 69 | 291 | 69 | 0.35 | 0.87 | 0.81 | 0.91 | 0.89 | 2,336 |

### How much of this is noise

With 35 questions, one question moves an average by about 0.03. Averages
within ~0.05 of each other are not meaningfully different on this corpus.
Several single questions are decided by ranking races with a margin of 0.01
to 0.02 in cosine score (p2 below is one), and turning on one sentence of
overlap in the `sentence` strategy flipped question t7 from complete to
missed. Read the table as "which *kinds* of questions does a strategy win or
lose", not as a leaderboard. The per-document and per-question tables in the
generated report are where the explanations are.

## What the numbers show

**1. Boundaries only matter near an answer.** 22 of 35 questions were complete
for all twelve configurations. When a fact sits comfortably inside any
chunk, every strategy retrieves it. Chunking decides the other 13.

**2. Fixed-size chunks lose answers by cutting them.** `fixed` has the lowest
share of complete answers (0.83). Its failures are cuts through an evidence
sentence: t6 (security audit, cut at character 2750), r1 (TalentBridge, cut
at 950), p2 (alert routing, cut at 950). Every strategy that respects
sentences answers t6 and r1 completely, except structure and hierarchical on
t6 (next point). The 50-character overlap doesn't help: those sentences are
140 and 167 characters long.

**3. Bigger chunks buy completeness with context, not ranking.**
`fixed_1000` raises completeness from 0.91 to 0.96 and complete answers from
0.83 to 0.94, but doubles the context to read (2,805 characters) and barely
changes MRR (0.88 vs 0.87). Part of any large-chunk strategy's advantage is
this size effect, not smarter boundaries.

**4. Parent-child is the most complete and the most expensive to read.** It
is the only strategy of the ~400-character class that answers p1 ("what
caused the outage"), whose evidence sits under two headings, Summary and
Timeline. It matches a small child and delivers the 2,000-character parent
that contains both. It has the best complete-answer rate (0.97). The cost:
its children compete with each other and with distractors, so MRR is the
lowest (0.83), and the LLM reads 3,114 characters per question, over twice
what fixed delivers.

**5. The winner changes by document.** Completeness at k = 3:

| Document | Best | Worst | Why |
|---|---|---|---|
| Q3 transcript (no structure) | recursive, metadata_aware 1.00; token 0.98; sliding 0.96 | hierarchical 0.75, fixed 0.80 | nothing to follow but sentences; see t6 and t7 below |
| Checkout postmortem (headed prose) | fixed_1000, parent_child 1.00 | semantic, structure 0.79 | answers span paragraphs and headings |
| Search postmortem | fixed_1000, sliding, semantic, semantic_plain, structure, parent_child 1.00 | recursive, metadata_aware 0.50 | s1's evidence spans a paragraph and a section |
| Handbook (Markdown) | all ≥ 0.98; best ranking (MRR 1.00) for recursive, semantic, structure, metadata_aware, parent_child, hierarchical | fixed (MRR 0.83) | headings now reach the chunkers |
| CSV | all 1.00 except token 0.75 | token | token cuts a row in half (c3: "…uto Sato \| time_zone: JST") |

`structure` is among the *worst* on the checkout postmortem, the most
cleanly structured prose in the corpus. It keeps the whole Timeline section
(947 characters: the deploy, the alert and the rollback) as one chunk, and
that chunk's embedding is an average of all three events. For p2 ("why did
the on-call engineer find out so late") it ranks fourth, behind the Summary,
What Went Well and Root Cause sections. Following structure is not the same
as producing focused chunks. Semantic chunking with the heading rule now
makes the identical Timeline chunk and misses p2 the same way.

**6. Routing by metadata combines the strengths.** `metadata_aware` (CSV →
lines, Markdown → structure, text → recursive) shares the best MRR (0.91,
with recursive) and the best completeness on four of seven documents. It
is not magic, though: its transcripts and postmortems are chunked by `recursive`,
so it inherits recursive's s1 and r2 misses.

**7. Semantic chunking is not free.** It embedded 258 texts to produce 43
chunks: one embedding per sentence window, about 5.7× the indexing calls of
`fixed`. Its chunks vary from 150 to 1,000 characters.

## Why semantic chunking beat fixed-size on the Q3 transcript

The transcript is a single 3,372-character paragraph that moves through
revenue → hiring → data-centre migration → APAC churn → security audit →
announcements, with no paragraph breaks or headings to follow. This is where
semantic chunking should help, and question t6 shows the mechanism.

**Question t6:** *What was the most serious security audit finding and what
was decided about it?* The evidence is two consecutive sentences at
characters 2636–2773 and 2774–2915:

> The most serious one is that API keys used by the analytics pipeline have
> never been rotated, some of them are more than three years old. The
> decision is that all of those keys will be rotated by the 15th of October,
> and from then on keys will rotate automatically every 90 days.

**Fixed (500/50)** cuts at 2750, in the middle of the first sentence:

| Chunk | Span | Starts | Ends | Rank |
|---|---|---|---|---|
| chunk_5 | 2250–2750 | "n. The plan is to hire two Japanese-speaking support ag…" | "…never been rotated, some of them are mor" | 1 |
| chunk_6 | 2700–3200 | "line have never been rotated, some of them are more tha…" | "…ns in January with 20 desks, mostly for " | not in top 5 |

chunk_5 is half APAC churn plan, half security audit. It ranks first because
it contains "Now the security audit. The external audit by Castell
Security…", but it stops before the decision. chunk_6 holds the decision,
but it starts mid-sentence and then runs into the other two findings and the
Lisbon office announcement. It never mentions "audit", and its embedding is
a blend of three topics, so it is not retrieved at all. The LLM would get the
finding without the fix: **completeness 0.41**. Doubling the size
(`fixed_1000`, 0.59) moves the cut but does not remove it. Its chunk_2 ends
at 2800, inside the second evidence sentence.

**Semantic** computes the cosine distance between each sentence and the next
(each embedded with one neighbour on either side). For this document the
85th-percentile threshold is 0.326:

| # | Sentence | Distance to next | Cut |
|---:|---|---:|:-:|
| 24 | Customer success will also call every APAC account above 50 thousand euros… | 0.312 | |
| 25 | Now the security audit. | 0.323 | ✂ (size limit) |
| 26 | The external audit by Castell Security finished last week… | 0.058 | |
| 27 | **The most serious one is that API keys … have never been rotated…** | 0.181 | |
| 28 | **The decision is that all of those keys will be rotated by the 15th of October…** | 0.189 | |
| 29 | The other two findings are about overly broad admin permissions… | 0.346 | ✂ |
| 30 | Last topic, a couple of announcements. | 0.287 | |

Inside the security topic the distances are low (0.06–0.19): the sentences
talk about the same thing, so their embeddings are close. The distance jumps
to 0.346 when the speaker moves on to announcements, which exceeds the
threshold, and the chunk ends. The resulting chunk_5 (2529–3095) is the
whole audit discussion and nothing else. It ranks first, contains both
evidence sentences, and scores **completeness 1.00**.

One detail should not be overclaimed. The cut *before* the topic, after "Now
the security audit." (0.323), was not a threshold breakpoint. The churn and
security sentences together were 1,187 characters, over `max_chars` (1,000),
so the chunker split them at their largest internal distance, which happened
to be there. The announcing sentence ended up at the end of the churn chunk.
The threshold and the size guard work together.

Across the whole transcript, semantic's cuts land on four of the five agenda
changes exactly ("Next item is hiring", "Moving on to the data center
migration", "Next, customer churn", "Last topic"), one sentence late on the
fifth, and add one split inside the migration topic (overview vs. billing
blocker). None of `fixed`'s seven boundaries is even on a sentence boundary.
The same mechanism answers r1 in the Q2 transcript: `fixed` cuts the
TalentBridge sentence at 950 (completeness 0.61), while semantic keeps the
hiring discussion together (distances 0.10–0.29, then 0.345 at
"Next, infrastructure.").

In one sentence: **on text whose topics change without any formatting,
semantic chunking puts boundaries where the meaning changes, so a complete
answer lives in one focused chunk. Fixed-size chunking puts boundaries at
arbitrary offsets, splitting answers across chunks whose embeddings are
diluted by neighbouring topics.**

## Where semantic chunking loses

- **Mixed small topics still dilute (t7).** The final announcements (a new
  Lisbon office and the offsite moving from Lisbon to Porto) form one chunk.
  The Q2 transcript's "offsite planned for March in Lisbon" outranks it.
  Sliding window, recursive, token, structure and metadata-aware ranked
  their offsite chunk above that distractor; both semantic variants, fixed,
  fixed_1000, sentence, parent-child and hierarchical did not.
- **Answers that span headings (p1).** The cause is stated in the Summary and
  detailed in the Timeline. Any strategy whose chunks stop at a heading
  delivers one half at k = 3; only large or parent context gets both.
- **Whole sections are coarse (p2).** See point 5 above.
- **Cost.** About 5.7× the embedding calls of `fixed` at indexing time, and
  results that depend on the embedding model and the threshold.

## Fixes after the first run

The first run exposed four problems. Each was fixed, and this report shows
the results after the fixes.

| Problem found | Fix | Effect in this run |
|---|---|---|
| Ingestion flattened Markdown and HTML: headings, list bullets and code fences were dropped, and tables came out one cell per line | `html_to_text` keeps `#` headings, `- ` list items, fenced code, and one line per table row; DOCX heading and list styles get the same markers | recursive answers h7 (the VPN commands were previously glued to the Expenses section); handbook MRR 1.00 for six strategies (was five) |
| Semantic chunking cut a consequence from its cause: "This retry storm is why…" had distance 0.334 from the previous sentence (p3) | `keep_references`: no cut before a sentence opening with *this, these, those, it, such, …* | p3: 1.00, vs 0.75 for `semantic_plain` |
| Semantic chunking attached headings to the end of the previous chunk ("…reached nobody. Timeline") | `respect_headings`: always cut before a heading, never after one, never merge across one | chunks now follow sections where a document has them; completeness@1 0.84 vs 0.75, MRR@3 0.90 vs 0.86, 14% less context |
| Parent-child and hierarchical prompts repeated the parent text in the metadata JSON sent to the LLM | the prompt leaves out chunking bookkeeping (`context_text`, `matched_text`, offsets, ids) | not measured here (retrieval-only), covered by `test_prompt_leaves_out_chunking_bookkeeping` |

A fifth fix is operational. Changing a strategy's parameters used to leave
the old chunks in place, because documents are skipped by content hash. The
index file name now includes a fingerprint of the parameters, so a changed
setting builds a fresh index.

Two honest caveats about these fixes. First, they were designed after
seeing failures on this question set, so their improvement on p3 and h7 is
not independent evidence. They should be judged on a new corpus. Second,
the heading rule cost one question: on p2, `semantic` now makes the same
947-character Timeline chunk as `structure` and ranks it fourth (0.506 vs
0.517 for third). `semantic_plain` had nearly the same chunk and ranked it
third. That is a ranking race lost by 0.02, not a new failure mode, and
tuning `max_chars` to win it would be fitting the test set.

## Conclusions, conditioned on the documents

- **Unstructured text with topic shifts** (transcripts, logs): any
  sentence-respecting strategy beats fixed-size. Semantic gives the most
  topic-coherent chunks but costs an embedding per sentence. Here recursive
  and sentence were as good at a fraction of the cost, because the answers
  were within a few adjacent sentences.
- **Headed documents** (handbooks, guides): once headings survive ingestion,
  almost every strategy finds the answer and structure-aware strategies rank
  it first. Whole sections can still be too coarse to rank well
  (the postmortem Timeline).
- **Multi-paragraph answers** (postmortems, procedures): only large delivered
  context answers them completely. Parent-child gets it with precise
  matching, at twice the reading cost; `fixed_1000` gets most of it by brute
  force.
- **Tables:** keep rows whole. Line-based recursive does; token-based
  chunking does not.
- **Mixed corpora:** routing by document type (`metadata_aware`) ranked
  answers best overall here, but it is only as good as the strategy each
  rule routes to (0.50 on the search postmortem, via recursive). The
  broader lesson is to pick chunking per document shape, not once for the
  whole corpus.

## Limitations

- **Small, synthetic corpus.** Seven documents and 35 questions, written by
  the same author as the chunkers, with questions deliberately including
  multi-sentence answers. Real documents are messier, and results on them may
  differ in either direction.
- **Fixes tuned on the evaluation set** (see above).
- **Retrieval metrics only.** Completeness measures whether the evidence
  reached the LLM, not whether the LLM used it; no answers were generated or
  graded. Extra context (parent-child) can distract an LLM, and that cost is
  not measured here.
- **Parameters were fixed in advance, not tuned** per strategy. A tuned
  threshold or chunk size would change individual outcomes.
- **One embedding model.** Semantic boundaries and every ranking depend on
  it.
- **Hard negatives shape the results.** Without them, the first version of
  this corpus scored at the ceiling for 20 of 28 questions and did not
  separate the strategies at all.

## Reproducing and extending

```powershell
python -m src.experiments.chunking                  # uses OpenAI; embeddings cached
python -m src.experiments.chunking --only fixed,semantic
python -m src.experiments.chunking --offline        # free hashed embeddings, no API
```

The configuration is `experiments/chunking/config.json` (strategies and their
parameters, k, case studies); the questions are
`experiments/chunking/questions.json`. Embeddings are cached by text in
`experiments/chunking/.cache/` (git-ignored), so re-running costs nothing.
All runs together embedded about 800 unique short texts, a fraction of a
cent. Each run writes to `experiments/chunking/results/<name>/`: every
strategy's chunks (`chunks.jsonl`), FAISS index, per-question retrieval
results and metrics, the resolved configuration, `summary.json`, and the
regenerated `report.md`.

To evaluate chunking on your own documents, point `corpus_dir` at them and
write questions whose `evidence` passages are copied exactly from the
ingested text. The loader rejects any passage it cannot find, so a typo
fails loudly instead of scoring as a miss. Include documents that
resemble each other; without hard negatives every strategy looks perfect.
