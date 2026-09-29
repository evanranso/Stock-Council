"""Maps each segment to its adapter."""

from __future__ import annotations

from . import (
    analysts,
    congress,
    earnings,
    economy,
    filings,
    financials,
    insiders,
    institutions,
    news,
    options,
    price,
    related,
)
from .base import Fetcher

ADAPTERS: dict[str, Fetcher] = {
    m.SEGMENT: m.fetch
    for m in (
        price,
        financials,
        analysts,
        earnings,
        insiders,
        congress,
        news,
        filings,
        institutions,
        options,
        economy,
        related,
    )
}
