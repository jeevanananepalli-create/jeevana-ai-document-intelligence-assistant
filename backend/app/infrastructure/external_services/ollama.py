"""Ollama implementation of the LLMPort for local, key-free inference."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.domain.value_objects.document_analysis import DocumentAnalysis, ExtractedEntity
from app.domain.value_objects.search import RagAnswer
from app.infrastructure.external_services.llm import (
    _ANALYSIS_SYSTEM_PROMPT,
    _QA_SYSTEM_PROMPT,
    _AnalysisSchema,
    _RagAnswerSchema,
    format_context_passages,
)


class OllamaLLM:
    """Generate structured document analysis and grounded answers via Ollama."""

    def __init__(self, *, base_url: str, model: str, timeout_seconds: float = 180.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout_seconds)
        self._model = model

    async def analyze_document(self, text: str) -> DocumentAnalysis:
        payload = await self._chat(
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=text,
            schema=_AnalysisSchema.model_json_schema(),
        )
        parsed = _AnalysisSchema.model_validate(payload)
        return DocumentAnalysis(
            summary=parsed.summary,
            document_type=parsed.document_type,
            language=parsed.language,
            confidence=parsed.confidence,
            entities=tuple(
                ExtractedEntity(name=entity.name, type=entity.type)
                for entity in parsed.key_entities
            ),
        )

    async def generate_answer(self, question: str, contexts: list[str]) -> RagAnswer:
        user_prompt = (
            f"Context passages:\n\n{format_context_passages(contexts)}\n\nQuestion: {question}"
        )
        payload = await self._chat(
            system_prompt=_QA_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=_RagAnswerSchema.model_json_schema(),
        )
        parsed = _RagAnswerSchema.model_validate(payload)
        return RagAnswer(
            answer=parsed.answer,
            confidence=parsed.confidence,
            used_source_indices=tuple(parsed.used_source_indices),
        )

    async def _chat(self, *, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> Any:
        response = await self._client.post(
            "/api/chat",
            json={
                "model": self._model,
                "stream": False,
                "format": schema,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        return json.loads(content)

    async def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()
