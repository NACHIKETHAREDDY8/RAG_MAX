"""Prompt construction for the answer-generation phase."""

import json

from src.vector_store.models import SearchResult

def format_sources(context: list[SearchResult]) -> list[str]:
	"""Format existing source and page metadata for display."""
	sources = []

	for result in context:
		details = []
		if "source" in result.metadata:
			details.append(f"Source: {result.metadata['source']}")
		if "page" in result.metadata:
			details.append(f"Page: {result.metadata['page']}")

		if details:
			sources.append(f"{result.chunk_id} | " + " | ".join(details))

	return sources


def build_rag_prompt(question: str, context: list[SearchResult]) -> str:
	"""Build a grounded prompt from a question and retrieved chunks."""
	context_sections = []

	for result in context:
		metadata = json.dumps(result.metadata, sort_keys=True)
		source_details = format_sources([result])
		source_section = f"{source_details[0]}\n" if source_details else ""
		context_sections.append(
			f"Chunk ID: {result.chunk_id}\n"
			f"Similarity score: {result.score:.6f}\n"
			f"{source_section}"
			f"Metadata: {metadata}\n"
			f"Text:\n{result.text}"
		)

	formatted_context = "\n\n".join(context_sections) or "No context was retrieved."

	return (
		"System Instructions:\n"
		"You are a helpful question-answering assistant. Use only the provided "
		"context to answer the question. Do not use outside knowledge or invent "
		"facts. If the answer is not available in the context, say that the "
		"information is unavailable in the provided context.\n\n"
		"Context:\n"
		f"{formatted_context}\n\n"
		"Question:\n"
		f"{question}\n\n"
		"Answer:\n"
	)