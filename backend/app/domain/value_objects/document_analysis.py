"""AI analysis results for a document, as immutable domain value objects.

`DocumentAnalysis` groups everything the LLM derives from a document — summary,
entities, classification, language, confidence — into one value. Grouping them
(instead of five loose fields on Document) keeps the entity readable and makes
"has this document been analyzed?" a single `is not None` check.

These are plain dataclasses with no framework imports. The OpenAI adapter has its
own Pydantic schema for structured output and maps into these — the domain never
depends on how the analysis was produced.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ExtractedEntity:
    """A named thing the LLM found in the document (a person, org, date, ...)."""

    name: str
    type: str  # e.g. person, organization, date, monetary_value, location


@dataclass(frozen=True, slots=True)
class DocumentAnalysis:
    """The complete AI-derived analysis of one document."""

    summary: str
    document_type: str  # contract | research | invoice | report | letter | other
    language: str  # ISO 639-1 code, e.g. "en"
    confidence: float  # the model's self-reported confidence, 0.0-1.0
    entities: tuple[ExtractedEntity, ...] = field(default_factory=tuple)
