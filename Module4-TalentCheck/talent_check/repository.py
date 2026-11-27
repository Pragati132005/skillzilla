<<<<<<< HEAD
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
=======
from functools import lru_cache
import pandas as pd
from .config import *
from .supabase_client import create_supabase_client,read_table

def _read(table,path):
    if STRICT_SOURCE_MODE: return pd.DataFrame(read_table(create_supabase_client(),table,'id'))
    if not path.exists(): raise RuntimeError(f'Local CSV not found: {path}')
    return pd.read_csv(path)

def _topics(df):
    need={'id','skill_area','levels','topics'}
    if not need<=set(df.columns): raise RuntimeError(f'Skill topic source missing columns: {sorted(need-set(df.columns))}')
    df=df.copy(); df['skill_area']=df.skill_area.astype(str).str.strip()
    df['level_num']=df.levels.astype(str).str.extract(r'(?i)level\s*(\d+)')[0]
    if df.level_num.isna().any(): raise RuntimeError('Skill topic source contains invalid levels.')
    df['level_num']=df.level_num.astype(int)
    if not df.level_num.between(1,10).all(): raise RuntimeError('Skill topic levels must be 1–10.')
    if df.topics.isna().any() or (df.topics.astype(str).str.strip()=='').any(): raise RuntimeError('Empty topic rubric entries found.')
    dup=df.duplicated(['skill_area','level_num'],keep=False)
    if dup.any(): raise RuntimeError(f'Duplicate rubric entries: {df.loc[dup, ["skill_area","level_num"]].to_dict("records")[:10]}')
    return df.sort_values(['skill_area','level_num','id'],kind='stable').reset_index(drop=True)

def _companies(df):
    columns={'id','companies','coding','data_structures_and_algorithms','object_oriented_programming_and_design','aptitude_and_problem_solving','communication_skills','ai_native_engineering','devops_and_cloud','sql_and_design','software_engineering','system_design_and_architecture','computer_networking','operating_system'}
    if not columns<=set(df.columns): raise RuntimeError(f'Company benchmark source missing columns: {sorted(columns-set(df.columns))}')
    df=df.copy(); df['companies']=df.companies.astype(str).str.strip()
    if (df.companies=='').any(): raise RuntimeError('Blank company names in benchmark source.')
    df['company_normalized']=df.companies.str.casefold()
    # Keep all rows so a duplicate name can be reported with row IDs and handled
    # explicitly by the scoring layer. Never select the first matching row.
    return df.sort_values(['companies','id'],kind='stable').reset_index(drop=True)
@lru_cache(maxsize=1)
def load_skill_topics(): return _topics(_read(SUPABASE_SKILL_TOPICS_TABLE,SKILL_TOPICS_CSV))
@lru_cache(maxsize=1)
def load_company_levels(): return _companies(_read(SUPABASE_COMPANY_LEVELS_TABLE,COMPANY_LEVELS_CSV))
def clear_cache(): load_skill_topics.cache_clear(); load_company_levels.cache_clear()
>>>>>>> 4c9d1dbefd237039dacabfd3cd53abe17201b131
