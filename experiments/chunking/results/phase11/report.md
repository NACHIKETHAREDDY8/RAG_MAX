# Chunking experiment: phase11

Generated 2026-09-28T14:24:46+00:00 by `python -m src.experiments.chunking`.
This file is regenerated on every run; interpretation lives in
`docs/chunking_experiment.md`.

## Setup

- Embedding model: `text-embedding-3-small` (same for every strategy)
- Questions: 35, identical for every strategy
- k: 1, 3, 5; headline tables use k = 3
- Context expansion for parent/section strategies: on

| Document | Type | Characters | Questions |
|---|---|---:|---:|
| employee_handbook.md | markdown | 3,397 | 9 |
| engineering_onboarding.md | markdown | 2,467 | 3 |
| incident_postmortem.txt | txt | 3,306 | 7 |
| office_directory.csv | csv | 1,734 | 4 |
| q2_business_review_transcript.txt | txt | 2,266 | 2 |
| quarterly_review_transcript.txt | txt | 3,372 | 8 |
| search_outage_postmortem.txt | txt | 2,472 | 2 |

## Results at k = 3

| Strategy | Chunks | Avg chars | Avg tokens | Texts embedded | Precision | Hit | MRR | Evidence recall | Completeness | Complete answers | Context chars |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed | 45 | 465 | 100 | 45 | 0.39 | 0.97 | 0.87 | 0.90 | 0.91 | 0.83 | 1444 |
| fixed_1000 | 23 | 896 | 191 | 23 | 0.37 | 0.97 | 0.88 | 0.96 | 0.96 | 0.94 | 2805 |
| sliding_window | 54 | 485 | 103 | 54 | 0.46 | 1.00 | 0.89 | 0.98 | 0.97 | 0.94 | 1464 |
| sentence | 51 | 440 | 93 | 51 | 0.43 | 0.97 | 0.90 | 0.95 | 0.94 | 0.91 | 1328 |
| recursive | 51 | 372 | 79 | 51 | 0.36 | 0.97 | 0.91 | 0.94 | 0.94 | 0.91 | 1161 |
| token | 43 | 488 | 104 | 43 | 0.40 | 0.97 | 0.84 | 0.93 | 0.94 | 0.89 | 1522 |
| semantic | 43 | 441 | 94 | 258 | 0.32 | 0.94 | 0.90 | 0.93 | 0.93 | 0.91 | 1542 |
| semantic_plain | 39 | 487 | 103 | 254 | 0.34 | 0.97 | 0.86 | 0.95 | 0.95 | 0.91 | 1795 |
| structure | 35 | 563 | 119 | 35 | 0.32 | 0.94 | 0.85 | 0.93 | 0.93 | 0.91 | 1787 |
| metadata_aware | 48 | 410 | 87 | 48 | 0.36 | 0.97 | 0.91 | 0.94 | 0.94 | 0.91 | 1228 |
| parent_child | 64 | 296 | 63 | 64 | 0.32 | 0.94 | 0.83 | 0.97 | 0.97 | 0.97 | 3114 |
| hierarchical | 69 | 291 | 61 | 69 | 0.35 | 0.94 | 0.87 | 0.91 | 0.91 | 0.89 | 2336 |

### Completeness and MRR at every k

| Strategy | Completeness@1 | MRR@1 | Completeness@3 | MRR@3 | Completeness@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|---:|
| fixed | 0.67 | 0.77 | 0.91 | 0.87 | 0.95 | 0.87 |
| fixed_1000 | 0.76 | 0.80 | 0.96 | 0.88 | 0.99 | 0.89 |
| sliding_window | 0.75 | 0.80 | 0.97 | 0.89 | 0.99 | 0.89 |
| sentence | 0.79 | 0.83 | 0.94 | 0.90 | 1.00 | 0.90 |
| recursive | 0.80 | 0.86 | 0.94 | 0.91 | 0.99 | 0.92 |
| token | 0.63 | 0.71 | 0.94 | 0.84 | 0.97 | 0.85 |
| semantic | 0.84 | 0.86 | 0.93 | 0.90 | 1.00 | 0.91 |
| semantic_plain | 0.75 | 0.77 | 0.95 | 0.86 | 1.00 | 0.87 |
| structure | 0.75 | 0.77 | 0.93 | 0.85 | 0.99 | 0.86 |
| metadata_aware | 0.80 | 0.86 | 0.94 | 0.91 | 0.99 | 0.92 |
| parent_child | 0.83 | 0.74 | 0.97 | 0.83 | 1.00 | 0.83 |
| hierarchical | 0.81 | 0.83 | 0.91 | 0.87 | 1.00 | 0.88 |

## By document (k = 3)

Completeness / MRR per document. The best value in each row is in bold;
ties are all bold.

| Document | fixed | fixed_1000 | sliding_window | sentence | recursive | token | semantic | semantic_plain | structure | metadata_aware | parent_child | hierarchical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| employee_handbook.md | 0.98 / 0.83 | **1.00** / 0.94 | **1.00** / 0.94 | **1.00** / 0.94 | **1.00** / **1.00** | 0.99 / 0.89 | **1.00** / **1.00** | **1.00** / 0.94 | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / **1.00** |
| engineering_onboarding.md | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / 0.83 | **1.00** / **1.00** |
| incident_postmortem.txt | 0.89 / 0.93 | **1.00** / 0.93 | 0.91 / 0.76 | 0.93 / 0.93 | 0.93 / 0.93 | 0.88 / **1.00** | 0.79 / 0.86 | 0.89 / 0.83 | 0.79 / 0.86 | 0.93 / 0.93 | **1.00** / 0.93 | 0.93 / 0.81 |
| office_directory.csv | **1.00** / **1.00** | **1.00** / 0.88 | **1.00** / 0.83 | 1.00 / 0.83 | **1.00** / **1.00** | 0.75 / 0.62 | 1.00 / 0.88 | 1.00 / 0.88 | **1.00** / 0.75 | **1.00** / **1.00** | **1.00** / **1.00** | **1.00** / **1.00** |
| q2_business_review_transcript.txt | 0.81 / 0.67 | 0.96 / **0.75** | **1.00** / 0.67 | **1.00** / **0.75** | 0.75 / **0.75** | **1.00** / 0.50 | **1.00** / **0.75** | **1.00** / **0.75** | **1.00** / **0.75** | 0.75 / **0.75** | **1.00** / 0.67 | **1.00** / **0.75** |
| quarterly_review_transcript.txt | 0.80 / 0.75 | 0.82 / 0.73 | 0.96 / **1.00** | 0.88 / 0.81 | **1.00** / 0.88 | 0.98 / 0.75 | 0.88 / 0.81 | 0.88 / 0.81 | 0.88 / 0.65 | **1.00** / 0.88 | 0.88 / 0.62 | 0.75 / 0.75 |
| search_outage_postmortem.txt | 0.91 / **1.00** | **1.00** / **1.00** | **1.00** / 0.75 | 0.79 / **1.00** | 0.50 / 0.50 | 0.94 / **1.00** | **1.00** / **1.00** | **1.00** / 0.67 | **1.00** / **1.00** | 0.50 / 0.50 | **1.00** / 0.42 | 0.71 / 0.67 |

## Per question (completeness at k = 3)

| Question | fixed | fixed_1000 | sliding_window | sentence | recursive | token | semantic | semantic_plain | structure | metadata_aware | parent_child | hierarchical |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| h1: How many days of paid annual leave do full-time employees get, and how many unused days can be carried over? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| h2: When do I need a doctor's note for sick leave? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| h3: How many paid days of parental leave are there, and who approves it? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| h4: What is the hotel reimbursement limit per night in Europe and in North America? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| h5: What should I do if the VPN status says degraded? | 0.83 | 1.00 | 1.00 | 1.00 | 1.00 | 0.95 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| h6: How many days a week can I work remotely, and what does a fully remote arrangement require? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| h7: Which commands do I run to log in and connect to the VPN with the staff profile? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| h8: How big is the annual learning budget and does unused budget roll over? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| h9: How quickly must a lost laptop be reported, and to whom? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| t1: What was revenue in Q3 and what drove the growth? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| t2: Why did the small business segment shrink? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| t3: Which roles does the hiring freeze cover, and which roles are still being hired? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| t4: Why is the billing service migration blocked and what is the workaround? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| t5: Why did churn go up in APAC and what is the plan to fix it? | 1.00 | 1.00 | 0.69 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| t6: What was the most serious security audit finding and what was decided about it? | 0.41 | 0.59 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 |
| t7: After the change announced in the Q3 review, where and when is the company offsite? | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 |
| t8: How much does cancelling the recruiting agency save, and who takes over recruiting? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.80 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| p1: What caused the checkout outage? | 0.50 | 1.00 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 | 1.00 | 0.50 |
| p2: Why did the on-call engineer find out about the checkout outage so late? | 0.73 | 1.00 | 1.00 | 1.00 | 1.00 | 0.68 | 0.00 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| p3: Why did the checkout service stay down instead of degrading gracefully? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.75 | 1.00 | 1.00 | 1.00 | 1.00 |
| p4: Why were some customers charged twice, and how was it resolved? | 1.00 | 1.00 | 0.89 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| p5: What was the estimated lost revenue from the checkout outage? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| p6: Who owns the action item to prevent double charges, and when is it due? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| p7: How long was checkout unavailable? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| c1: Who is the office manager of the Zürich office? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| c2: How many employees work in the São Paulo office? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| c3: Which office is in the JST time zone, and is desk booking required there? | 1.00 | 1.00 | 1.00 | 0.99 | 1.00 | 0.00 | 0.99 | 0.99 | 1.00 | 1.00 | 1.00 | 1.00 |
| c4: When did the Berlin Engineering office open? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| r1: Why was the TalentBridge recruiting contract renewed in Q2? | 0.61 | 0.91 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| r2: What was APAC churn in Q2, and who handled first-line support in Japanese at that time? | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 |
| s1: Why did the search outage take so long to diagnose? | 0.82 | 1.00 | 1.00 | 0.58 | 0.00 | 0.89 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 0.42 |
| s2: What filled up the disks on the search cluster nodes? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| e1: Who can approve a production deployment? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| e2: How much is the on-call allowance for engineers? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| e3: Which VPN profile do engineers use to reach staging, and how long does its session last? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

## Chunk boundaries around selected answers

### t6: What was the most serious security audit finding and what was decided about it?

Evidence:

- [2636:2773] “The most serious one is that API keys used by the analytics pipeline have never been rotated, some of them are more than three years old.”
- [2774:2915] “The decision is that all of those keys will be rotated by the 15th of October, and from then on keys will rotate automatically every 90 days.”

**fixed**: completeness 0.41, MRR 0.50, top results `engineering_onboarding/chunk_5`, `quarterly_review_transcript/chunk_5`, `search_outage_postmortem/chunk_4`

- “The most serious one is that API keys used by the analytics pipeline …” — **split across chunks**:
  - `chunk_5` [2250:2750], rank 2: starts “n. The plan is to hire two Japanese-speaking support agents……”, ends “……tics pipeline have never been rotated, some of them are mor”
  - `chunk_6` [2700:3200], not retrieved: starts “line have never been rotated, some of them are more than th……”, ends “……ew Lisbon office opens in January with 20 desks, mostly for”
- “The decision is that all of those keys will be rotated by the 15th of…” — whole in one chunk:
  - `chunk_6` [2700:3200], not retrieved: starts “line have never been rotated, some of them are more than th……”, ends “……ew Lisbon office opens in January with 20 desks, mostly for”

**fixed_1000**: completeness 0.59, MRR 1.00, top results `quarterly_review_transcript/chunk_2`, `q2_business_review_transcript/chunk_1`, `incident_postmortem/chunk_2`

- “The most serious one is that API keys used by the analytics pipeline …” — whole in one chunk:
  - `chunk_2` [1800:2800], rank 1: starts “e November deadline. The remaining two services, reporting ……”, ends “……m are more than three years old. The decision is that all o”
  - `chunk_3` [2700:3372], not retrieved: starts “line have never been rotated, some of them are more than th……”, ends “……the 14th of March. That's everything for today, thanks all.”
- “The decision is that all of those keys will be rotated by the 15th of…” — whole in one chunk:
  - `chunk_2` [1800:2800], rank 1: starts “e November deadline. The remaining two services, reporting ……”, ends “……m are more than three years old. The decision is that all o”
  - `chunk_3` [2700:3372], not retrieved: starts “line have never been rotated, some of them are more than th……”, ends “……the 14th of March. That's everything for today, thanks all.”

**sentence**: completeness 1.00, MRR 1.00, top results `quarterly_review_transcript/chunk_8`, `incident_postmortem/chunk_6`, `search_outage_postmortem/chunk_4`

- “The most serious one is that API keys used by the analytics pipeline …” — whole in one chunk:
  - `chunk_8` [2529:2915], rank 1: starts “The external audit by Castell Security finished last week, ……”, ends “…… from then on keys will rotate automatically every 90 days.”
- “The decision is that all of those keys will be rotated by the 15th of…” — whole in one chunk:
  - `chunk_8` [2529:2915], rank 1: starts “The external audit by Castell Security finished last week, ……”, ends “…… from then on keys will rotate automatically every 90 days.”
  - `chunk_9` [2774:3226], rank 4: starts “The decision is that all of those keys will be rotated by t……”, ends “……anuary with 20 desks, mostly for the customer success team.”

**semantic**: completeness 1.00, MRR 1.00, top results `quarterly_review_transcript/chunk_5`, `engineering_onboarding/chunk_6`, `incident_postmortem/chunk_2`

- “The most serious one is that API keys used by the analytics pipeline …” — whole in one chunk:
  - `chunk_5` [2529:3095], rank 1: starts “The external audit by Castell Security finished last week, ……”, ends “……rts, and both have owners and should be fixed this quarter.”
- “The decision is that all of those keys will be rotated by the 15th of…” — whole in one chunk:
  - `chunk_5` [2529:3095], rank 1: starts “The external audit by Castell Security finished last week, ……”, ends “……rts, and both have owners and should be fixed this quarter.”

Semantic distances (breakpoint when distance > 0.326):

| # | Sentence | Evidence | Distance to next | Cut after |
|---:|---|:-:|---:|:-:|
| 25 | Now the security audit. |  | 0.323 |  |
| 26 | The external audit by Castell Security finished last week, and they r… |  | 0.058 |  |
| 27 | The most serious one is that API keys used by the analytics pipeline … | ✓ | 0.181 |  |
| 28 | The decision is that all of those keys will be rotated by the 15th of… | ✓ | 0.189 |  |
| 29 | The other two findings are about overly broad admin permissions in th… |  | 0.346 | ✂ |
| 30 | Last topic, a couple of announcements. |  | 0.287 |  |

**structure**: completeness 0.00, MRR 0.00, top results `incident_postmortem/chunk_2`, `engineering_onboarding/chunk_5`, `q2_business_review_transcript/chunk_2`

- “The most serious one is that API keys used by the analytics pipeline …” — whole in one chunk:
  - `chunk_2` [1908:2773], not retrieved: starts “Next, customer churn in the Asia Pacific region. APAC churn……”, ends “……r been rotated, some of them are more than three years old.”
- “The decision is that all of those keys will be rotated by the 15th of…” — whole in one chunk:
  - `chunk_3` [2774:3372], rank 4: starts “The decision is that all of those keys will be rotated by t……”, ends “……the 14th of March. That's everything for today, thanks all.”

### r1: Why was the TalentBridge recruiting contract renewed in Q2?

Evidence:

- [848:1015] “We renewed the contract with the TalentBridge recruiting agency for another year, because they filled most of the senior roles and our own recruiters are fully booked.”

**fixed**: completeness 0.61, MRR 1.00, top results `q2_business_review_transcript/chunk_1`, `quarterly_review_transcript/chunk_2`, `quarterly_review_transcript/chunk_1`

- “We renewed the contract with the TalentBridge recruiting agency for a…” — **split across chunks**:
  - `chunk_1` [450:950], rank 1: starts “nt this quarter. Gross margin came in at 69 percent, slight……”, ends “……dge recruiting agency for another year, because they filled”
  - `chunk_2` [900:1400], rank 4: starts “ting agency for another year, because they filled most of t……”, ends “……llowed by notifications. Nobody has looked at billing in de”

**fixed_1000**: completeness 0.91, MRR 1.00, top results `q2_business_review_transcript/chunk_0`, `quarterly_review_transcript/chunk_0`, `quarterly_review_transcript/chunk_1`

- “We renewed the contract with the TalentBridge recruiting agency for a…” — **split across chunks**:
  - `chunk_0` [0:1000], rank 1: starts “Good morning everyone, this is the Q2 business review, let'……”, ends “……y filled most of the senior roles and our own recruiters ar”
  - `chunk_1` [900:1900], rank 4: starts “ting agency for another year, because they filled most of t……”, ends “……ell Security is booked for the third quarter, and the scope”

**semantic**: completeness 1.00, MRR 1.00, top results `q2_business_review_transcript/chunk_1`, `quarterly_review_transcript/chunk_1`, `quarterly_review_transcript/chunk_0`

- “We renewed the contract with the TalentBridge recruiting agency for a…” — whole in one chunk:
  - `chunk_1` [157:1138], rank 1: starts “Second quarter revenue was 3.75 million euros, up 8 percent……”, ends “……ked every department to re-justify open roles in September.”

Semantic distances (breakpoint when distance > 0.320):

| # | Sentence | Evidence | Distance to next | Cut after |
|---:|---|:-:|---:|:-:|
| 7 | On hiring, we closed four data engineering roles and two account exec… |  | 0.278 |  |
| 8 | Time to hire went down to 38 days on average. |  | 0.159 |  |
| 9 | We renewed the contract with the TalentBridge recruiting agency for a… | ✓ | 0.101 |  |
| 10 | There is no hiring freeze planned at the moment, but finance asked ev… |  | 0.289 |  |
| 11 | Next, infrastructure. |  | 0.345 | ✂ |

### p3: Why did the checkout service stay down instead of degrading gracefully?

Evidence:

- [1546:1662] “The checkout client then retried each failed payment immediately, up to three times, with no delay between attempts.”
- [1663:1785] “Those retries tripled the load on an already saturated pool, so the queue never drained even when traffic dipped slightly.”
- [1786:1866] “This retry storm is why the service stayed down instead of degrading gracefully.”

**fixed**: completeness 1.00, MRR 1.00, top results `incident_postmortem/chunk_3`, `incident_postmortem/chunk_4`, `incident_postmortem/chunk_0`

- “The checkout client then retried each failed payment immediately, up …” — whole in one chunk:
  - `chunk_3` [1350:1850], rank 1: starts “recovered by 13:49. Root Cause The direct cause was the red……”, ends “……retry storm is why the service stayed down instead of degra”
- “Those retries tripled the load on an already saturated pool, so the q…” — whole in one chunk:
  - `chunk_3` [1350:1850], rank 1: starts “recovered by 13:49. Root Cause The direct cause was the red……”, ends “……retry storm is why the service stayed down instead of degra”
- “This retry storm is why the service stayed down instead of degrading …” — **split across chunks**:
  - `chunk_3` [1350:1850], rank 1: starts “recovered by 13:49. Root Cause The direct cause was the red……”, ends “……retry storm is why the service stayed down instead of degra”
  - `chunk_4` [1800:2300], rank 2: starts “rm is why the service stayed down instead of degrading grac……”, ends “……st payment succeeded at the payment provider after the clie”

**semantic_plain**: completeness 0.75, MRR 0.50, top results `incident_postmortem/chunk_0`, `incident_postmortem/chunk_2`, `incident_postmortem/chunk_4`

- “The checkout client then retried each failed payment immediately, up …” — whole in one chunk:
  - `chunk_2` [1382:1785], rank 2: starts “The direct cause was the reduced connection pool. With only……”, ends “…… the queue never drained even when traffic dipped slightly.”
- “Those retries tripled the load on an already saturated pool, so the q…” — whole in one chunk:
  - `chunk_2` [1382:1785], rank 2: starts “The direct cause was the reduced connection pool. With only……”, ends “…… the queue never drained even when traffic dipped slightly.”
- “This retry storm is why the service stayed down instead of degrading …” — whole in one chunk:
  - `chunk_3` [1786:2028], rank 5: starts “This retry storm is why the service stayed down instead of ……”, ends “……he timeout value and did not notice the second line. Impact”

Semantic distances (breakpoint when distance > 0.295):

| # | Sentence | Evidence | Distance to next | Cut after |
|---:|---|:-:|---:|:-:|
| 15 | The direct cause was the reduced connection pool. |  | 0.256 |  |
| 16 | With only 20 connections available, most requests waited in the queue… |  | 0.102 |  |
| 17 | The checkout client then retried each failed payment immediately, up … | ✓ | 0.161 |  |
| 18 | Those retries tripled the load on an already saturated pool, so the q… | ✓ | 0.334 | ✂ |
| 19 | This retry storm is why the service stayed down instead of degrading … | ✓ | 0.144 |  |
| 20 | The configuration file had no validation, and the change was reviewed… |  | 0.274 |  |
| 21 | Impact |  | 0.402 | ✂ |

**semantic**: completeness 1.00, MRR 1.00, top results `incident_postmortem/chunk_2`, `incident_postmortem/chunk_0`, `incident_postmortem/chunk_3`

- “The checkout client then retried each failed payment immediately, up …” — whole in one chunk:
  - `chunk_2` [1371:2020], rank 1: starts “Root Cause The direct cause was the reduced connection pool……”, ends “……ed on the timeout value and did not notice the second line.”
- “Those retries tripled the load on an already saturated pool, so the q…” — whole in one chunk:
  - `chunk_2` [1371:2020], rank 1: starts “Root Cause The direct cause was the reduced connection pool……”, ends “……ed on the timeout value and did not notice the second line.”
- “This retry storm is why the service stayed down instead of degrading …” — whole in one chunk:
  - `chunk_2` [1371:2020], rank 1: starts “Root Cause The direct cause was the reduced connection pool……”, ends “……ed on the timeout value and did not notice the second line.”

Semantic distances (breakpoint when distance > 0.295):

| # | Sentence | Evidence | Distance to next | Cut after |
|---:|---|:-:|---:|:-:|
| 15 | The direct cause was the reduced connection pool. |  | 0.256 |  |
| 16 | With only 20 connections available, most requests waited in the queue… |  | 0.102 |  |
| 17 | The checkout client then retried each failed payment immediately, up … | ✓ | 0.161 |  |
| 18 | Those retries tripled the load on an already saturated pool, so the q… | ✓ | 0.334 |  |
| 19 | This retry storm is why the service stayed down instead of degrading … | ✓ | 0.144 |  |
| 20 | The configuration file had no validation, and the change was reviewed… |  | 0.274 | ✂ |
| 21 | Impact |  | 0.402 |  |

**parent_child**: completeness 1.00, MRR 1.00, top results `incident_postmortem/chunk_5`, `incident_postmortem/chunk_0`, `incident_postmortem/chunk_1`

- “The checkout client then retried each failed payment immediately, up …” — whole in one chunk:
  - `chunk_5` [1546:1866], rank 1: starts “The checkout client then retried each failed payment immedi……”, ends “……hy the service stayed down instead of degrading gracefully.”
- “Those retries tripled the load on an already saturated pool, so the q…” — whole in one chunk:
  - `chunk_5` [1546:1866], rank 1: starts “The checkout client then retried each failed payment immedi……”, ends “……hy the service stayed down instead of degrading gracefully.”
- “This retry storm is why the service stayed down instead of degrading …” — whole in one chunk:
  - `chunk_5` [1546:1866], rank 1: starts “The checkout client then retried each failed payment immedi……”, ends “……hy the service stayed down instead of degrading gracefully.”

### p1: What caused the checkout outage?

Evidence:

- [254:420] “The outage was caused by a configuration change to the payments database connection pool, and it was made worse by client retries and by an alert that reached nobody.”
- [513:676] “The change was meant to lower the idle timeout of database connections, but it also reduced the maximum size of the connection pool for payments-db from 200 to 20.”

**fixed**: completeness 0.50, MRR 1.00, top results `incident_postmortem/chunk_0`, `incident_postmortem/chunk_3`, `incident_postmortem/chunk_4`

- “The outage was caused by a configuration change to the payments datab…” — whole in one chunk:
  - `chunk_0` [0:500], rank 1: starts “Checkout Outage Postmortem Summary On 14 August 2026 the ch……”, ends “……TC a routine configuration change was deployed to the payme”
- “The change was meant to lower the idle timeout of database connection…” — whole in one chunk:
  - `chunk_1` [450:950], not retrieved: starts “ine configuration change was deployed to the payments servi……”, ends “……to the old payments pager rotation, which had been decommis”

**fixed_1000**: completeness 1.00, MRR 1.00, top results `incident_postmortem/chunk_0`, `incident_postmortem/chunk_1`, `incident_postmortem/chunk_2`

- “The outage was caused by a configuration change to the payments datab…” — whole in one chunk:
  - `chunk_0` [0:1000], rank 1: starts “Checkout Outage Postmortem Summary On 14 August 2026 the ch……”, ends “…… decommissioned in July when the team was reorganised, so n”
- “The change was meant to lower the idle timeout of database connection…” — whole in one chunk:
  - `chunk_0` [0:1000], rank 1: starts “Checkout Outage Postmortem Summary On 14 August 2026 the ch……”, ends “…… decommissioned in July when the team was reorganised, so n”

**semantic_plain**: completeness 0.50, MRR 1.00, top results `incident_postmortem/chunk_0`, `incident_postmortem/chunk_2`, `incident_postmortem/chunk_4`

- “The outage was caused by a configuration change to the payments datab…” — whole in one chunk:
  - `chunk_0` [0:430], rank 1: starts “Checkout Outage Postmortem Summary On 14 August 2026 the ch……”, ends “……lient retries and by an alert that reached nobody. Timeline”
- “The change was meant to lower the idle timeout of database connection…” — whole in one chunk:
  - `chunk_1` [431:1381], rank 4: starts “At 13:02 UTC a routine configuration change was deployed to……”, ends “……3:44, and checkout had fully recovered by 13:49. Root Cause”

Semantic distances (breakpoint when distance > 0.295):

| # | Sentence | Evidence | Distance to next | Cut after |
|---:|---|:-:|---:|:-:|
| 2 | On 14 August 2026 the checkout service was unavailable for 47 minutes… |  | 0.069 |  |
| 3 | During that time customers could browse the store and fill their bask… |  | 0.179 |  |
| 4 | The outage was caused by a configuration change to the payments datab… | ✓ | 0.230 |  |
| 5 | Timeline | ✓ | 0.289 |  |
| 6 | At 13:02 UTC a routine configuration change was deployed to the payme… | ✓ | 0.098 |  |
| 7 | The change was meant to lower the idle timeout of database connection… | ✓ | 0.103 |  |
| 8 | Lunchtime traffic in Europe was close to its daily peak, and within t… |  | 0.229 |  |
| 9 | The first alert, for payment latency above five seconds, fired at 13:… |  | 0.254 |  |

**semantic**: completeness 0.50, MRR 1.00, top results `incident_postmortem/chunk_0`, `incident_postmortem/chunk_3`, `incident_postmortem/chunk_2`

- “The outage was caused by a configuration change to the payments datab…” — whole in one chunk:
  - `chunk_0` [0:420], rank 1: starts “Checkout Outage Postmortem Summary On 14 August 2026 the ch……”, ends “……orse by client retries and by an alert that reached nobody.”
- “The change was meant to lower the idle timeout of database connection…” — whole in one chunk:
  - `chunk_1` [422:1369], rank 4: starts “Timeline At 13:02 UTC a routine configuration change was de……”, ends “……d back at 13:44, and checkout had fully recovered by 13:49.”

Semantic distances (breakpoint when distance > 0.295):

| # | Sentence | Evidence | Distance to next | Cut after |
|---:|---|:-:|---:|:-:|
| 2 | On 14 August 2026 the checkout service was unavailable for 47 minutes… |  | 0.069 |  |
| 3 | During that time customers could browse the store and fill their bask… |  | 0.179 |  |
| 4 | The outage was caused by a configuration change to the payments datab… | ✓ | 0.230 | ✂ |
| 5 | Timeline | ✓ | 0.289 |  |
| 6 | At 13:02 UTC a routine configuration change was deployed to the payme… | ✓ | 0.098 |  |
| 7 | The change was meant to lower the idle timeout of database connection… | ✓ | 0.103 |  |
| 8 | Lunchtime traffic in Europe was close to its daily peak, and within t… |  | 0.229 |  |
| 9 | The first alert, for payment latency above five seconds, fired at 13:… |  | 0.254 |  |

**parent_child**: completeness 1.00, MRR 1.00, top results `incident_postmortem/chunk_1`, `incident_postmortem/chunk_0`, `incident_postmortem/chunk_6`

- “The outage was caused by a configuration change to the payments datab…” — whole in one chunk:
  - `chunk_1` [28:420], rank 1: starts “Summary On 14 August 2026 the checkout service was unavaila……”, ends “……orse by client retries and by an alert that reached nobody.”
- “The change was meant to lower the idle timeout of database connection…” — whole in one chunk:
  - `chunk_2` [422:802], not retrieved: starts “Timeline At 13:02 UTC a routine configuration change was de……”, ends “……n two minutes requests were queueing for a free connection.”

### p2: Why did the on-call engineer find out about the checkout outage so late?

Evidence:

- [804:876] “The first alert, for payment latency above five seconds, fired at 13:09.”
- [877:1016] “It was routed to the old payments pager rotation, which had been decommissioned in July when the team was reorganised, so nobody was paged.”
- [1017:1161] “The on-call engineer only learned about the outage at 13:31, when customer support escalated a spike in complaints through the incident channel.”

**fixed**: completeness 0.73, MRR 1.00, top results `incident_postmortem/chunk_2`, `incident_postmortem/chunk_0`, `engineering_onboarding/chunk_4`

- “The first alert, for payment latency above five seconds, fired at 13:…” — whole in one chunk:
  - `chunk_1` [450:950], not retrieved: starts “ine configuration change was deployed to the payments servi……”, ends “……to the old payments pager rotation, which had been decommis”
- “It was routed to the old payments pager rotation, which had been deco…” — **split across chunks**:
  - `chunk_1` [450:950], not retrieved: starts “ine configuration change was deployed to the payments servi……”, ends “……to the old payments pager rotation, which had been decommis”
  - `chunk_2` [900:1400], rank 1: starts “d payments pager rotation, which had been decommissioned in……”, ends “……had fully recovered by 13:49. Root Cause The direct cause w”
- “The on-call engineer only learned about the outage at 13:31, when cus…” — whole in one chunk:
  - `chunk_2` [900:1400], rank 1: starts “d payments pager rotation, which had been decommissioned in……”, ends “……had fully recovered by 13:49. Root Cause The direct cause w”

**structure**: completeness 0.00, MRR 0.00, top results `incident_postmortem/chunk_0`, `incident_postmortem/chunk_4`, `incident_postmortem/chunk_2`

- “The first alert, for payment latency above five seconds, fired at 13:…” — whole in one chunk:
  - `chunk_1` [422:1369], rank 4: starts “Timeline At 13:02 UTC a routine configuration change was de……”, ends “……d back at 13:44, and checkout had fully recovered by 13:49.”
- “It was routed to the old payments pager rotation, which had been deco…” — whole in one chunk:
  - `chunk_1` [422:1369], rank 4: starts “Timeline At 13:02 UTC a routine configuration change was de……”, ends “……d back at 13:44, and checkout had fully recovered by 13:49.”
- “The on-call engineer only learned about the outage at 13:31, when cus…” — whole in one chunk:
  - `chunk_1` [422:1369], rank 4: starts “Timeline At 13:02 UTC a routine configuration change was de……”, ends “……d back at 13:44, and checkout had fully recovered by 13:49.”

**semantic**: completeness 0.00, MRR 0.00, top results `incident_postmortem/chunk_0`, `incident_postmortem/chunk_4`, `incident_postmortem/chunk_2`

- “The first alert, for payment latency above five seconds, fired at 13:…” — whole in one chunk:
  - `chunk_1` [422:1369], rank 4: starts “Timeline At 13:02 UTC a routine configuration change was de……”, ends “……d back at 13:44, and checkout had fully recovered by 13:49.”
- “It was routed to the old payments pager rotation, which had been deco…” — whole in one chunk:
  - `chunk_1` [422:1369], rank 4: starts “Timeline At 13:02 UTC a routine configuration change was de……”, ends “……d back at 13:44, and checkout had fully recovered by 13:49.”
- “The on-call engineer only learned about the outage at 13:31, when cus…” — whole in one chunk:
  - `chunk_1` [422:1369], rank 4: starts “Timeline At 13:02 UTC a routine configuration change was de……”, ends “……d back at 13:44, and checkout had fully recovered by 13:49.”

Semantic distances (breakpoint when distance > 0.295):

| # | Sentence | Evidence | Distance to next | Cut after |
|---:|---|:-:|---:|:-:|
| 7 | The change was meant to lower the idle timeout of database connection… |  | 0.103 |  |
| 8 | Lunchtime traffic in Europe was close to its daily peak, and within t… |  | 0.229 |  |
| 9 | The first alert, for payment latency above five seconds, fired at 13:… | ✓ | 0.254 |  |
| 10 | It was routed to the old payments pager rotation, which had been deco… | ✓ | 0.226 |  |
| 11 | The on-call engineer only learned about the outage at 13:31, when cus… | ✓ | 0.197 |  |
| 12 | The engineer identified the connection pool change at 13:40 by compar… |  | 0.170 |  |
| 13 | The change was rolled back at 13:44, and checkout had fully recovered… |  | 0.161 | ✂ |

**parent_child**: completeness 1.00, MRR 0.50, top results `incident_postmortem/chunk_0`, `incident_postmortem/chunk_3`, `incident_postmortem/chunk_1`

- “The first alert, for payment latency above five seconds, fired at 13:…” — whole in one chunk:
  - `chunk_3` [804:1161], rank 2: starts “The first alert, for payment latency above five seconds, fi……”, ends “……calated a spike in complaints through the incident channel.”
- “It was routed to the old payments pager rotation, which had been deco…” — whole in one chunk:
  - `chunk_3` [804:1161], rank 2: starts “The first alert, for payment latency above five seconds, fi……”, ends “……calated a spike in complaints through the incident channel.”
- “The on-call engineer only learned about the outage at 13:31, when cus…” — whole in one chunk:
  - `chunk_3` [804:1161], rank 2: starts “The first alert, for payment latency above five seconds, fi……”, ends “……calated a spike in complaints through the incident channel.”

### t7: After the change announced in the Q3 review, where and when is the company offsite?

Evidence:

- [3227:3331] “And the company offsite is moving from Lisbon to Porto, it will now be on the 12th to the 14th of March.”

**fixed**: completeness 0.00, MRR 0.00, top results `q2_business_review_transcript/chunk_4`, `q2_business_review_transcript/chunk_0`, `quarterly_review_transcript/chunk_0`

- “And the company offsite is moving from Lisbon to Porto, it will now b…” — whole in one chunk:
  - `chunk_7` [3150:3372], rank 4: starts “office opens in January with 20 desks, mostly for the custo……”, ends “……the 14th of March. That's everything for today, thanks all.”

**sentence**: completeness 0.00, MRR 0.00, top results `q2_business_review_transcript/chunk_5`, `q2_business_review_transcript/chunk_0`, `quarterly_review_transcript/chunk_0`

- “And the company offsite is moving from Lisbon to Porto, it will now b…” — whole in one chunk:
  - `chunk_10` [3135:3372], rank 5: starts “The new Lisbon office opens in January with 20 desks, mostl……”, ends “……the 14th of March. That's everything for today, thanks all.”

**semantic**: completeness 0.00, MRR 0.00, top results `q2_business_review_transcript/chunk_5`, `quarterly_review_transcript/chunk_0`, `q2_business_review_transcript/chunk_0`

- “And the company offsite is moving from Lisbon to Porto, it will now b…” — whole in one chunk:
  - `chunk_6` [3096:3372], rank 4: starts “Last topic, a couple of announcements. The new Lisbon offic……”, ends “……the 14th of March. That's everything for today, thanks all.”

Semantic distances (breakpoint when distance > 0.326):

| # | Sentence | Evidence | Distance to next | Cut after |
|---:|---|:-:|---:|:-:|
| 30 | Last topic, a couple of announcements. |  | 0.287 |  |
| 31 | The new Lisbon office opens in January with 20 desks, mostly for the … |  | 0.102 |  |
| 32 | And the company offsite is moving from Lisbon to Porto, it will now b… | ✓ | 0.252 |  |
| 33 | That's everything for today, thanks all. |  |  |  |


## Metric definitions

| Metric | Meaning |
|---|---|
| Precision@k | share of the k retrieved chunks that hold at least half of an evidence passage (or are at least half evidence) |
| Hit@k | a relevant chunk is among the k retrieved |
| MRR | 1 / rank of the first relevant chunk (0 when none in the top k); how high the answer ranks |
| Evidence recall | share of evidence passages at least 80% present in the context the LLM receives |
| Completeness | share of evidence characters present in the context the LLM receives |
| Complete answers | share of questions for which *every* evidence passage was delivered |
| Context chars | characters the LLM has to read per question (cost and noise) |

Precision, Hit and MRR are measured on the retrieved chunks; recall,
completeness and context size on the delivered context, which for
parent-child and hierarchical is the parents/sections the matches expand to.
