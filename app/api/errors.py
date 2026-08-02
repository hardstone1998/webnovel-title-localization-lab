"""Safe, stable API error payloads."""

from __future__ import annotations

from typing import Any


def error_payload(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def validation_error_details(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep validation locations/messages but never echo submitted input values."""

    return [{key: value for key, value in error.items() if key != "input"} for error in errors]
