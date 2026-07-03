"""Tests for the OpenAILLM adapter, with the OpenAI client fully mocked.

What matters here is the adapter's own logic: prompt assembly reaches the
client, the structured-output schema maps correctly into the domain value
object, and a refusal (no parsed payload) raises instead of returning junk.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.value_objects.document_analysis import DocumentAnalysis
from app.infrastructure.external_services.llm import (
    OpenAILLM,
    _AnalysisSchema,
    _EntitySchema,
    _RagAnswerSchema,
    format_context_passages,
)


class _FakeCompletions:
    """Stands in for client.chat.completions; records the call, returns a canned parse."""

    def __init__(self, parsed: Any) -> None:
        self._parsed = parsed
        self.kwargs: dict[str, Any] | None = None

    async def parse(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        message = SimpleNamespace(parsed=self._parsed)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _make_llm(parsed: Any) -> tuple[OpenAILLM, _FakeCompletions]:
    llm = OpenAILLM(api_key="test-key", model="gpt-4o-mini")
    completions = _FakeCompletions(parsed)
    # Replace the real client with a stub exposing the same call path.
    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))  # type: ignore[assignment]
    return llm, completions


_SCHEMA = _AnalysisSchema(
    summary="A 12-page service agreement.",
    key_entities=[_EntitySchema(name="Acme Corp", type="organization")],
    document_type="contract",
    language="en",
    confidence=0.92,
)


async def test_maps_structured_output_to_domain_value_object() -> None:
    llm, completions = _make_llm(_SCHEMA)

    analysis = await llm.analyze_document("SERVICE AGREEMENT ...")

    assert isinstance(analysis, DocumentAnalysis)
    assert analysis.summary == "A 12-page service agreement."
    assert analysis.document_type == "contract"
    assert analysis.language == "en"
    assert analysis.confidence == 0.92
    assert analysis.entities[0].name == "Acme Corp"
    assert analysis.entities[0].type == "organization"


async def test_sends_document_text_and_model_to_the_client() -> None:
    llm, completions = _make_llm(_SCHEMA)

    await llm.analyze_document("the document text")

    assert completions.kwargs is not None
    assert completions.kwargs["model"] == "gpt-4o-mini"
    assert completions.kwargs["response_format"] is _AnalysisSchema
    user_message = completions.kwargs["messages"][-1]
    assert user_message == {"role": "user", "content": "the document text"}


async def test_refusal_without_parsed_payload_raises() -> None:
    llm, _ = _make_llm(parsed=None)

    with pytest.raises(ValueError, match="no parseable analysis"):
        await llm.analyze_document("text")


def test_schema_rejects_out_of_range_confidence() -> None:
    """The Pydantic schema itself enforces the 0-1 confidence contract."""
    with pytest.raises(ValidationError):
        _AnalysisSchema(
            summary="s",
            key_entities=[],
            document_type="contract",
            language="en",
            confidence=1.5,
        )


# --- RAG answer generation (Phase 4) ----------------------------------------


def test_format_context_passages_numbers_passages() -> None:
    """Prompt construction: passages are 0-indexed so citations resolve."""
    block = format_context_passages(["first passage", "second passage"])
    assert block == "[0] first passage\n\n[1] second passage"


def test_format_context_passages_empty() -> None:
    assert format_context_passages([]) == ""


async def test_generate_answer_maps_to_rag_answer() -> None:
    llm, completions = _make_llm(
        _RagAnswerSchema(answer="30 days.", used_source_indices=[0, 2], confidence=0.9)
    )

    answer = await llm.generate_answer("Payment terms?", ["ctx a", "ctx b", "ctx c"])

    assert answer.answer == "30 days."
    assert answer.used_source_indices == (0, 2)
    assert answer.confidence == 0.9
    # The prompt carries the numbered contexts and the question.
    assert completions.kwargs is not None
    user_content = completions.kwargs["messages"][-1]["content"]
    assert "[0] ctx a" in user_content
    assert "[2] ctx c" in user_content
    assert user_content.endswith("Question: Payment terms?")
    assert completions.kwargs["response_format"] is _RagAnswerSchema


async def test_generate_answer_refusal_raises() -> None:
    llm, _ = _make_llm(parsed=None)
    with pytest.raises(ValueError, match="no parseable answer"):
        await llm.generate_answer("q", ["ctx"])
