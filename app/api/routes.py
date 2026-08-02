"""Route registration exports."""

from .health import router as health_router
from .title_localizations import router as title_localizations_router

__all__ = ["health_router", "title_localizations_router"]
