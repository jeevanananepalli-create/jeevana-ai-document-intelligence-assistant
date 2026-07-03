"""OpenAI implementation of the LLMPort, using structured output.

Structured output means the model is constrained to return JSON matching a
Pydantic schema — the SDK validates it before we ever see it, so there is no
brittle string parsing and no "the model added prose around the JSON" failure
mode. If the model cannot satisfy the schema, the SDK raises, and the pipeline
treats that as "analysis unavailable" (the document does not fail).

The Pydantic schema here is an infrastructure detail: it mirrors the domain's
DocumentAnalysis value object and is mapped into it, so the domain never
depends on Pydantic or the OpenAI SDK.
"""

from __future__ import annotations

from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.domain.value_objects.document_analysis import DocumentAnalysis, ExtractedEntity

_SYSTEM_PROMPT = (
    "You are a document analysis assistant. Analyze the provided document text and return: "
    "a concise summary (3-5 sentences), the key named entities (people, organizations, "
    "dates, monetary values, locations), the document type, the ISO 639-1 language code, "
    "and your confidence (0.0-1.0) in this analysis. Base everything strictly on the "
    "provided text; do not invent facts."
)


class _EntitySchema(BaseModel):
    """One extracted entity, as the model must return it."""

    name: str
    type: Literal["person", "organization", "date", "monetary_value", "location", "other"]


class _AnalysisSchema(BaseModel):
    """The structured shape the model is constrained to produce."""

    summary: str
    key_entities: list[_EntitySchema]
    document_type: Literal["contract", "research", "invoice", "report", "letter", "other"]
    language: str = Field(description="ISO 639-1 code of the document's main language")
    confidence: float = Field(ge=0.0, le=1.0)


class OpenAILLM:
    """Analyze documents via the OpenAI API with schema-bound responses."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def analyze_document(self, text: str) -> DocumentAnalysis:
        completion = await self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format=_AnalysisSchema,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:  # the model refused or produced no parseable output
            raise ValueError("LLM returned no parseable analysis")
        return _to_domain(parsed)


def _to_domain(schema: _AnalysisSchema) -> DocumentAnalysis:
    """Map the infrastructure schema to the pure domain value object."""
    return DocumentAnalysis(
        summary=schema.summary,
        document_type=schema.document_type,
        language=schema.language,
        confidence=schema.confidence,
        entities=tuple(
            ExtractedEntity(name=entity.name, type=entity.type) for entity in schema.key_entities
        ),
    )
