"""Small, deterministic website audits with no runtime dependencies."""

from .audit import audit_html
from .fetch import FetchError, FetchedPage, fetch_url
from .models import Finding, Report, Rule

__version__ = "0.1.0"
__all__ = ["audit_html", "fetch_url", "FetchError", "FetchedPage", "Finding", "Report", "Rule"]
