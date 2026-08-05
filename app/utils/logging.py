"""Service logging setup."""

from __future__ import annotations

import logging
from dataclasses import dataclass


@dataclass(frozen=True)
class RunLogContext:
    """Optional correlation data carried by a pipeline execution."""

    request_id: str | None = None

    @property
    def correlation_id(self) -> str:
        return self.request_id or "none"


def configure_logging(level: str) -> None:
    """Configure a concise process-wide log format once."""

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    else:
        root_logger.setLevel(level)
