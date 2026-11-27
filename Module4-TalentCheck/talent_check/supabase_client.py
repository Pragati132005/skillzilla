"""Minimal Supabase (PostgREST) reader using only the standard library.

Why not supabase-py?  This module only needs `select *` on two read-only tables; PostgREST over HTTPS
is the same transport supabase-py uses, with zero extra dependencies and no version drift between
teammates' machines.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .errors import SupabaseError

_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PAGE_SIZE = 1000


def fetch_table(url: str, key: str, table: str, *, timeout: float = 10.0,
                page_size: int = PAGE_SIZE, max_rows: int = 100000) -> List[Dict[str, Any]]:
    """Return every row of `table`, following PostgREST pagination. Raises SupabaseError."""
    if not url or not key:
        raise SupabaseError("SUPABASE_URL / SUPABASE_KEY are not configured")
    if not url.lower().startswith(("https://", "http://localhost", "http://127.0.0.1")):
        raise SupabaseError("SUPABASE_URL must use https://")
    if not _TABLE_RE.match(table or ""):
        raise SupabaseError(f"Invalid table name: {table!r}")

    base = f"{url.rstrip('/')}/rest/v1/{urllib.parse.quote(table)}"
    rows: List[Dict[str, Any]] = []
    start = 0
    while start < max_rows:
        end = start + page_size - 1
        # `order=id` keeps pages stable while paginating.
        req = urllib.request.Request(
            f"{base}?select=*&order=id.asc",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
                "Range-Unit": "items",
                "Range": f"{start}-{end}",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:  # pragma: no cover - best effort only
                pass
            hint = {
                401: "invalid API key",
                403: "key lacks permission (check Row Level Security policy for SELECT)",
                404: f"table '{table}' not found (check SUPABASE_*_TABLE)",
            }.get(exc.code, "request failed")
            raise SupabaseError(f"Supabase HTTP {exc.code}: {hint}", details=detail or None)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise SupabaseError(f"Cannot reach Supabase: {getattr(exc, 'reason', exc)}")
        try:
            page = json.loads(body)
        except ValueError:
            raise SupabaseError("Supabase returned non-JSON data")
        if not isinstance(page, list):
            raise SupabaseError("Supabase returned an unexpected payload", details=str(page)[:300])
        rows.extend(r for r in page if isinstance(r, dict))
        if len(page) < page_size:
            break
        start += page_size
    return rows
