"""Shared response envelope helpers for MCP tool payloads."""

from __future__ import annotations

import time
from typing import Any

TOOL_VERSION = "0.1.0"


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


def public_success(
    data: dict[str, Any],
    *,
    request_id: str | None = None,
    warnings: list[str] | None = None,
    started_at: float | None = None,
) -> dict[str, Any]:
    """Return the public Tool Specification response envelope."""

    return {
        "success": True,
        "data": data,
        "warnings": warnings or [],
        "error": None,
        "meta": {
            "request_id": request_id,
            "elapsed_ms": _elapsed_ms(started_at),
            "tool_version": TOOL_VERSION,
        },
    }


def public_error(
    code: str,
    message: str,
    *,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
    started_at: float | None = None,
) -> dict[str, Any]:
    """Return a structured public error without leaking tracebacks."""

    return {
        "success": False,
        "data": None,
        "warnings": [],
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "meta": {
            "request_id": request_id,
            "elapsed_ms": _elapsed_ms(started_at),
            "tool_version": TOOL_VERSION,
        },
    }


def start_timer() -> float:
    """Return a monotonic timestamp for public response metadata."""

    return time.perf_counter()


def _elapsed_ms(started_at: float | None) -> int:
    """Return elapsed milliseconds for a started timer."""

    if started_at is None:
        return 0
    return int((time.perf_counter() - started_at) * 1000)
