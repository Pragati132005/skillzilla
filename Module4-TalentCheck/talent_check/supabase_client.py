<<<<<<< HEAD
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
=======
"""Fail-closed Supabase reads with stable ordering and pagination."""
def create_supabase_client():
    from .config import SUPABASE_URL,SUPABASE_KEY
    if not SUPABASE_URL or not SUPABASE_KEY: raise RuntimeError('Strict Supabase mode requires SUPABASE_URL and SUPABASE_KEY in .env.')
    if not SUPABASE_URL.startswith('https://') or '.supabase.co' not in SUPABASE_URL: raise RuntimeError('SUPABASE_URL must be the HTTPS URL of your Supabase project.')
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL,SUPABASE_KEY)
    except Exception as e: raise RuntimeError(f'Supabase client initialization failed ({type(e).__name__}). Check credentials and dependency.') from e

def read_table(client,table,order_column='id'):
    from .config import SUPABASE_PAGE_SIZE,SUPABASE_MAX_ROWS
    if not table.replace('_','').isalnum(): raise RuntimeError(f'Unsafe table identifier: {table!r}')
    rows=[]; offset=0
    while True:
        try: result=client.table(table).select('*').order(order_column).range(offset,offset+SUPABASE_PAGE_SIZE-1).execute()
        except Exception as e:
            msg=str(e).lower()
            if any(x in msg for x in ('permission','row level security','rls','401','403')): raise RuntimeError(f'Supabase permission denied for {table}; verify table grants, RLS policies and server-side key.') from e
            raise RuntimeError(f'Supabase read failed for {table} at offset {offset} ({type(e).__name__}).') from e
        batch=getattr(result,'data',None)
        if not isinstance(batch,list): raise RuntimeError(f'Supabase returned invalid data for {table}.')
        if not batch: break
        rows.extend(batch)
        if len(rows)>SUPABASE_MAX_ROWS: raise RuntimeError(f'{table} exceeded SUPABASE_MAX_ROWS={SUPABASE_MAX_ROWS}; refusing potentially incomplete data.')
        if len(batch)<SUPABASE_PAGE_SIZE: break
        offset+=len(batch)
    if not rows: raise RuntimeError(f'Supabase table {table} is empty or unreadable.')
>>>>>>> 4c9d1dbefd237039dacabfd3cd53abe17201b131
    return rows
