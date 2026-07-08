"""Shared response envelope helpers for MCP tool payloads."""

from __future__ import annotations

from typing import Any


def response_envelope(
    *,
    candidate: bool = False,
    would_write: bool = False,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    next_action: str = "none",
) -> dict[str, Any]:
    """Return standard, JSON-serializable tool response envelope fields."""

    return {
        "candidate": candidate,
        "would_write": would_write,
        "warnings": warnings or [],
        "errors": errors or [],
        "next_action": next_action,
    }


def candidate_envelope(
    *,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    next_action: str = "review_candidate",
) -> dict[str, Any]:
    """Return the standard envelope for candidate-only responses."""

    return response_envelope(
        candidate=True,
        would_write=False,
        warnings=warnings,
        errors=errors,
        next_action=next_action,
    )
