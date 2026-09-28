from types import SimpleNamespace

import pytest

from src.generation.llm import LLM, OpenAILLM
from src.generation.prompt import build_rag_prompt, format_sources
from src.generation.service import GenerationService
from src.tests.conftest import FakeLLM
from src.vector_store.models import SearchResult


CONTEXT = [
    SearchResult(
        chunk_id="doc_chunk_0",
        text="Cats sleep a lot.",
        metadata={"source": "animals.pdf", "page": 3},
        score=0.9,
    )
]


def test_format_sources():
    assert format_sources(CONTEXT) == ["doc_chunk_0 | Source: animals.pdf | Page: 3"]


def test_build_rag_prompt_contains_question_and_context():
    prompt = build_rag_prompt("Do cats sleep?", CONTEXT)

    assert "Use only the provided context" in prompt
    assert "Cats sleep a lot." in prompt
    assert "Source: animals.pdf | Page: 3" in prompt
    assert prompt.endswith("Question:\nDo cats sleep?\n\nAnswer:\n")


def test_prompt_leaves_out_chunking_bookkeeping():
    parent = "Cats sleep a lot. They also purr."
    result = SearchResult(
        chunk_id="doc_chunk_0",
        text=parent,
        metadata={
            "filename": "animals.pdf",
            "section_path": "Cats > Sleep",
            "chunk_strategy": "parent_child",
            "chunk_start": 0,
            "chunk_end": 17,
            "parent_id": "doc_parent_0",
            "context_id": "doc_parent_0",
            "matched_text": "Cats sleep a lot.",
        },
        score=0.9,
    )

    prompt = build_rag_prompt("Do cats sleep?", [result])

    assert prompt.count("Cats sleep a lot.") == 1
    assert '"section_path": "Cats > Sleep"' in prompt
    for key in ("chunk_start", "parent_id", "context_id", "matched_text", "chunk_strategy"):
        assert key not in prompt


def test_generation_service_sends_grounded_prompt_to_llm():
    llm = FakeLLM("They do.")

    answer = GenerationService(llm).generate("Do cats sleep?", CONTEXT)

    assert answer == "They do."
    assert llm.prompts == [build_rag_prompt("Do cats sleep?", CONTEXT)]


def test_openai_llm_returns_stripped_answer():
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="  Yes.  "))]
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: response)
        )
    )

    llm = OpenAILLM(client=client)

    assert isinstance(llm, LLM)
    assert llm.generate("prompt") == "Yes."
    with pytest.raises(ValueError):
        llm.generate("  ")
