from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from el_factory.model import Page


def paginate(rows: Sequence[dict[str, Any]], cursor: int, page_size: int) -> Page:
    """Offset paging where the cursor is the page index; the last page reports no next cursor."""
    start = cursor * page_size
    chunk = list(rows[start : start + page_size])
    has_next = start + page_size < len(rows)
    return Page(rows=chunk, next_cursor=cursor + 1 if has_next else None)
