"""Render an experiment's summary as a Markdown comparison report."""

from pathlib import Path
from typing import Any

METRIC_NOTES = """\
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
"""


def render_report(summary: dict[str, Any], case_studies: list[dict[str, Any]]) -> str:
    k = summary["top_k"]
    strategies = summary["strategies"]
    labels = list(strategies)
    lines = [
        f"# Chunking experiment: {summary['name']}",
        "",
        f"Generated {summary['generated_at']} by `python -m src.experiments.chunking`.",
        "This file is regenerated on every run; interpretation lives in",
        "`docs/chunking_experiment.md`.",
        "",
        "## Setup",
        "",
        f"- Embedding model: `{summary['embedding_model']}` (same for every strategy)",
        f"- Questions: {len(summary['questions'])}, identical for every strategy",
        f"- k: {', '.join(map(str, summary['ks']))}; headline tables use k = {k}",
        f"- Context expansion for parent/section strategies: {'on' if summary['expand_context'] else 'off'}",
        "",
        "| Document | Type | Characters | Questions |",
        "|---|---|---:|---:|",
    ]
    question_counts = _count_questions(summary)
    for document in summary["documents"]:
        lines.append(
            f"| {document['filename']} | {document['source_type']} | {document['chars']:,} "
            f"| {question_counts.get(document['filename'], 0)} |"
        )

    lines += [
        "",
        f"## Results at k = {k}",
        "",
        "| Strategy | Chunks | Avg chars | Avg tokens | Texts embedded | "
        "Precision | Hit | MRR | Evidence recall | Completeness | Complete answers | Context chars |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in labels:
        stats = strategies[label]["stats"]
        metrics = strategies[label]["metrics"][str(k)]
        lines.append(
            f"| {label} | {stats['chunks']} | {stats['avg_chars']:.0f} | {stats['avg_tokens']:.0f} "
            f"| {stats['embedded_texts']} | {metrics['precision']:.2f} | {metrics['hit']:.2f} "
            f"| {metrics['reciprocal_rank']:.2f} | {metrics['evidence_recall']:.2f} "
            f"| {metrics['completeness']:.2f} | {metrics['complete_answer']:.2f} "
            f"| {metrics['context_chars']:.0f} |"
        )

    lines += ["", "### Completeness and MRR at every k", ""]
    header = "| Strategy | " + " | ".join(
        f"Completeness@{value} | MRR@{value}" for value in summary["ks"]
    ) + " |"
    lines += [header, "|---|" + "---:|" * (2 * len(summary["ks"]))]
    for label in labels:
        cells = []
        for value in summary["ks"]:
            metrics = strategies[label]["metrics"][str(value)]
            cells += [f"{metrics['completeness']:.2f}", f"{metrics['reciprocal_rank']:.2f}"]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines += [
        "",
        f"## By document (k = {k})",
        "",
        "Completeness / MRR per document. The best value in each row is in bold;",
        "ties are all bold.",
        "",
        "| Document | " + " | ".join(labels) + " |",
        "|---|" + "---|" * len(labels),
    ]
    for document in summary["documents"]:
        name = document["filename"]
        values = {
            label: strategies[label]["by_document"].get(name) or {} for label in labels
        }
        if not any(values.values()):
            continue
        best_completeness = max(value.get("completeness", 0) for value in values.values())
        best_mrr = max(value.get("reciprocal_rank", 0) for value in values.values())
        cells = []
        for label in labels:
            value = values[label]
            completeness = _bold(f"{value['completeness']:.2f}", value["completeness"] == best_completeness)
            mrr = _bold(f"{value['reciprocal_rank']:.2f}", value["reciprocal_rank"] == best_mrr)
            cells.append(f"{completeness} / {mrr}")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    lines += [
        "",
        f"## Per question (completeness at k = {k})",
        "",
        "| Question | " + " | ".join(labels) + " |",
        "|---|" + "---:|" * len(labels),
    ]
    for question in summary["questions"]:
        cells = [
            f"{strategies[label]['per_question'][question['id']]['completeness']:.2f}"
            for label in labels
        ]
        lines.append(f"| {question['id']}: {question['question']} | " + " | ".join(cells) + " |")

    if case_studies:
        lines += ["", "## Chunk boundaries around selected answers", ""]
        for study in case_studies:
            lines += _render_case_study(study)

    lines += ["", "## Metric definitions", "", METRIC_NOTES]
    return "\n".join(lines).rstrip() + "\n"


def _render_case_study(study: dict[str, Any]) -> list[str]:
    lines = [f"### {study['question']}: {study['text']}", "", "Evidence:", ""]
    for passage in study["evidence"]:
        lines.append(f"- [{passage['start']}:{passage['end']}] “{passage['text']}”")

    for label, entry in study["strategies"].items():
        metrics = entry["metrics"]
        lines += [
            "",
            f"**{label}**: completeness {metrics['completeness']:.2f}, "
            f"MRR {metrics['reciprocal_rank']:.2f}, top results "
            + ", ".join(
                f"`{Path(item['filename'] or '').stem}/{_short(item['chunk_id'])}`"
                for item in entry["top_results"]
            ),
            "",
        ]
        for passage in entry["passages"]:
            where = "whole in one chunk" if passage["whole_in_one_chunk"] else "**split across chunks**"
            lines.append(f"- “{_clip(passage['passage'], 70)}” — {where}:")
            for chunk in passage["chunks"]:
                rank = f"rank {chunk['rank']}" if chunk["rank"] else "not retrieved"
                lines.append(
                    f"  - `{_short(chunk['chunk_id'])}` [{chunk['start']}:{chunk['end']}], {rank}: "
                    f"starts “{_clip(chunk['starts_with'], 60)}…”, ends “…{_clip_left(chunk['ends_with'], 60)}”"
                )

        if semantic := entry.get("semantic"):
            lines += [
                "",
                f"Semantic distances (breakpoint when distance > {semantic['threshold']:.3f}):",
                "",
                "| # | Sentence | Evidence | Distance to next | Cut after |",
                "|---:|---|:-:|---:|:-:|",
            ]
            for sentence in semantic["sentences"]:
                distance = sentence["distance_to_next"]
                lines.append(
                    f"| {sentence['index']} | {_clip(sentence['text'], 70)} "
                    f"| {'✓' if sentence['in_evidence'] else ''} "
                    f"| {'' if distance is None else f'{distance:.3f}'} "
                    f"| {'✂' if sentence['breakpoint_after'] else ''} |"
                )

    lines.append("")
    return lines


def _count_questions(summary: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for question in summary["questions"]:
        counts[question["document"]] = counts.get(question["document"], 0) + 1
    return counts


def _short(chunk_id: str) -> str:
    """Drop the tenant and document hash: 'default:ab12-1_chunk_3' → 'chunk_3'."""
    return chunk_id.rsplit("_", 2)[-2] + "_" + chunk_id.rsplit("_", 1)[-1]


def _bold(text: str, condition: bool) -> str:
    return f"**{text}**" if condition else text


def _clip(text: str, length: int) -> str:
    text = " ".join(text.split()).replace("|", "\\|")
    return text if len(text) <= length else text[: length - 1] + "…"


def _clip_left(text: str, length: int) -> str:
    text = " ".join(text.split()).replace("|", "\\|")
    return text if len(text) <= length else "…" + text[-(length - 1) :]
