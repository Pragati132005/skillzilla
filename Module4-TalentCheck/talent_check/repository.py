"""Where the company + rubric data come from.

Priority (TALENT_CHECK_SOURCE=auto):  Supabase  ->  last good in-memory copy  ->  bundled CSV snapshot.
`strict_source` removes the last two fallbacks so a wrong table name can never be hidden during a demo.
Every response reports which source actually served it (`data_source`).
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from .company_data import (CompanyDirectory, load_company_csv, load_company_json,
                           records_from_rows)
from .config import Settings, load_settings
from .errors import CompanyDataError, SupabaseError
from .rubric import Rubric, load_rubric_csv, rubric_from_rows
from .supabase_client import fetch_table

COMPANY_CSV = "staging_company_skill_levels_rows.csv"
COMPANY_JSON = "talent_check_company_skillsets.json"
RUBRIC_CSV = "skill_level_rubric.csv"


@dataclass
class _Cached:
    value: object
    source: str
    loaded_at: float


class DataRepository:
    def __init__(self, settings: Optional[Settings] = None, clock: Callable[[], float] = time.monotonic):
        self.settings = settings or load_settings()
        self._clock = clock
        self._lock = threading.Lock()
        self._company: Optional[_Cached] = None
        self._rubric: Optional[_Cached] = None
        self.last_error: Optional[str] = None

    # ------------------------------------------------------------------ companies
    def get_directory(self, force_refresh: bool = False) -> Tuple[CompanyDirectory, str]:
        with self._lock:
            if self._fresh(self._company) and not force_refresh:
                return self._company.value, self._company.source  # type: ignore[union-attr]
            directory, source = self._load_company()
            self._company = _Cached(directory, source, self._clock())
            return directory, source

    def _fresh(self, cached: Optional[_Cached]) -> bool:
        return cached is not None and (self._clock() - cached.loaded_at) < self.settings.cache_ttl

    def _wants_supabase(self) -> bool:
        s = self.settings
        if s.source == "csv":
            return False
        if s.source == "supabase":
            return True
        return s.supabase_configured

    def _local_company(self) -> Tuple[CompanyDirectory, str]:
        d = self.settings.data_dir
        json_path = os.path.join(d, COMPANY_JSON)
        if os.path.exists(json_path):
            try:
                return load_company_json(json_path), f"json:{COMPANY_JSON}"
            except CompanyDataError as exc:   # facilitator's file in an unexpected shape: use the CSV, say so
                directory = load_company_csv(os.path.join(d, COMPANY_CSV))
                directory.warnings.append(f"{COMPANY_JSON} ignored ({exc.message}); using {COMPANY_CSV}")
                return directory, f"csv:{COMPANY_CSV}"
        return load_company_csv(os.path.join(d, COMPANY_CSV)), f"csv:{COMPANY_CSV}"

    def _load_company(self) -> Tuple[CompanyDirectory, str]:
        s = self.settings
        if not self._wants_supabase():
            self.last_error = None
            return self._local_company()
        try:
            rows = fetch_table(s.supabase_url or "", s.supabase_key or "", s.company_table)
            directory = records_from_rows(rows, source=f"supabase:{s.company_table}")
            self.last_error = None
            return directory, f"supabase:{s.company_table}"
        except CompanyDataError as exc:   # includes SupabaseError
            self.last_error = exc.message
            if s.strict_source or s.source == "supabase":
                raise
            if self._company is not None:   # stale-but-real beats a bundled snapshot
                return self._company.value, f"{self._company.source} (stale cache; {exc.message})"  # type: ignore[return-value]
            directory, src = self._local_company()
            return directory, f"{src} (fallback; {exc.message})"

    # ------------------------------------------------------------------ rubric
    def get_rubric(self, force_refresh: bool = False) -> Rubric:
        with self._lock:
            if self._fresh(self._rubric) and not force_refresh:
                return self._rubric.value  # type: ignore[return-value]
            rubric = self._load_rubric()
            self._rubric = _Cached(rubric, "rubric", self._clock())
            return rubric

    def _load_rubric(self) -> Rubric:
        s = self.settings
        if s.rubric_table and self._wants_supabase():
            try:
                rows = fetch_table(s.supabase_url or "", s.supabase_key or "", s.rubric_table)
                return rubric_from_rows(rows, source=f"supabase:{s.rubric_table}")
            except CompanyDataError:
                if s.strict_source:
                    raise
        return load_rubric_csv(os.path.join(s.data_dir, RUBRIC_CSV))

    # ------------------------------------------------------------------ misc
    def health(self) -> dict:
        directory, source = self.get_directory()
        return {"companies": len(directory), "data_source": source,
                "supabase_configured": self.settings.supabase_configured,
                "last_error": self.last_error, "warnings": directory.warnings[:20]}
