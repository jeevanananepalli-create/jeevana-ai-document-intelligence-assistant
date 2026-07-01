"""The document processing lifecycle, expressed as a domain value object.

This is the single source of truth for document state in the *business* layer.
It mirrors the same four values stored in the database and exposed by the API
(see docs/database-design.md and docs/api-contract.md), but it lives here in the
domain so the rules about *which transitions are legal* are framework-free and
unit-testable.
"""

from __future__ import annotations

from enum import StrEnum


class DocumentStatus(StrEnum):
    """The state a document can be in while it moves through the pipeline."""

    UPLOADED = "uploaded"  # file stored, queued; nothing processed yet
    PROCESSING = "processing"  # a worker is extracting/chunking/embedding
    COMPLETED = "completed"  # all processing succeeded
    FAILED = "failed"  # a processing step errored

    def can_transition_to(self, target: DocumentStatus) -> bool:
        """Return True if moving from this status to `target` is allowed.

        The legal transitions encode the pipeline's rules:
        - a new document starts `uploaded` and moves to `processing` (or `failed`
          if it fails before/at the start of processing);
        - `processing` ends in either `completed` or `failed`;
        - `failed` or `completed` documents may be re-processed (e.g. re-analyze).

        A document can never jump straight from `uploaded` to `completed` — it
        must pass through `processing`.
        """
        return target in _ALLOWED_TRANSITIONS[self]


# Defined after the class so the values can reference DocumentStatus members.
_ALLOWED_TRANSITIONS: dict[DocumentStatus, frozenset[DocumentStatus]] = {
    DocumentStatus.UPLOADED: frozenset({DocumentStatus.PROCESSING, DocumentStatus.FAILED}),
    DocumentStatus.PROCESSING: frozenset({DocumentStatus.COMPLETED, DocumentStatus.FAILED}),
    DocumentStatus.COMPLETED: frozenset({DocumentStatus.PROCESSING}),
    DocumentStatus.FAILED: frozenset({DocumentStatus.PROCESSING}),
}
