"""Tests for the DocumentStatus lifecycle rules."""

from __future__ import annotations

import pytest

from app.domain.value_objects.document_status import DocumentStatus


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (DocumentStatus.UPLOADED, DocumentStatus.PROCESSING),
        (DocumentStatus.UPLOADED, DocumentStatus.FAILED),  # failed before processing began
        (DocumentStatus.PROCESSING, DocumentStatus.COMPLETED),
        (DocumentStatus.PROCESSING, DocumentStatus.FAILED),
        (DocumentStatus.FAILED, DocumentStatus.PROCESSING),  # re-process
        (DocumentStatus.COMPLETED, DocumentStatus.PROCESSING),  # re-analyze
    ],
)
def test_allowed_transitions(source: DocumentStatus, target: DocumentStatus) -> None:
    assert source.can_transition_to(target) is True


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (DocumentStatus.UPLOADED, DocumentStatus.COMPLETED),  # must pass through processing
        (DocumentStatus.COMPLETED, DocumentStatus.COMPLETED),
        (DocumentStatus.PROCESSING, DocumentStatus.UPLOADED),  # cannot go backwards
        (DocumentStatus.FAILED, DocumentStatus.COMPLETED),
    ],
)
def test_disallowed_transitions(source: DocumentStatus, target: DocumentStatus) -> None:
    assert source.can_transition_to(target) is False


def test_status_value_matches_wire_format() -> None:
    """The enum's string value is exactly what the API and DB store."""
    assert DocumentStatus.UPLOADED == "uploaded"
    assert DocumentStatus.COMPLETED.value == "completed"
