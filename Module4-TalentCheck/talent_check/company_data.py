"""Company requirement data: parsing, validation, de-duplication and name resolution.

Source rows look like (Supabase table == CSV)::

    id | companies | coding | data_structures_and_algorithms | ... | operating_system
    4  | Google LLC (Subsidiary of Alphabet Inc.) | 8-CR | 9-CR | ... | 9-CR

Each skill cell is "<level 1-10>-<Bloom code>" (``5-AP``); one column even uses spaces (``5 - AP``).
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import (BLOOM_RANK, CATEGORY_ORDER, CODE_TO_COLUMN, COLUMN_TO_CODE,
                     MAX_LEVEL, MIN_LEVEL)
from .errors import AmbiguousCompanyError, CompanyDataError, CompanyNotFoundError
from .text_utils import clean_text

_CELL_RE = re.compile(r"^(\d{1,2})(?:\s*[-:/]\s*([A-Za-z]{2}))?$")

_NAME_KEYS = ("companies", "company", "company_name", "name")
_LEGAL_WORDS = {
    "inc", "llc", "ltd", "limited", "private", "pvt", "plc", "corp", "corporation", "co", "company",
    "se", "gmbh", "nv", "ag", "the", "of", "and", "subsidiary", "alphabet", "pvt.", "ltd.",
}
_ALIASES = {
    "ibm": "international business machines",
    "tcs": "tata consultancy services",
    "jpmorgan": "jpmorgan chase",
    "jp morgan": "jpmorgan chase",
    "bny mellon": "bank of new york mellon",
    "l&t infotech": "larsen toubro infotech",
    "lti": "larsen toubro infotech",
    "ofss": "oracle financial services software",
    "oracle fss": "oracle financial services software",
    "mufg": "mitsubishi ufj financial group",
    "hcl": "hcl technologies",
    "sap": "sap labs india",
    "spacex": "space exploration technologies",
    "cba": "commonwealth bank of australia",
}


class CellError(ValueError):
    pass


def parse_cell(value: Any) -> Optional[Tuple[int, Optional[str]]]:
    """'5-AP' / '5 - AP' / 5 / 5.0 / '5' -> (5, 'AP'|None). Blank -> None. Invalid -> CellError."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise CellError(f"boolean is not a level: {value!r}")
    if isinstance(value, float) and value != value:   # NaN (pandas-style empty cell)
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (value in (float("inf"), float("-inf")) or value != int(value)):
            raise CellError(f"non-integer level: {value!r}")
        level, bloom = int(value), None
    else:
        text = clean_text(value)
        if text == "" or text.lower() in {"n/a", "na", "null", "none", "-", "nan"}:
            return None
        m = _CELL_RE.match(text)
        if not m:
            raise CellError(f"unparseable level cell: {text!r}")
        level = int(m.group(1))
        bloom = m.group(2).upper() if m.group(2) else None
    if not (MIN_LEVEL <= level <= MAX_LEVEL):
        raise CellError(f"level {level} outside {MIN_LEVEL}-{MAX_LEVEL}")
    if bloom is not None and bloom not in BLOOM_RANK:
        raise CellError(f"unknown depth code {bloom!r}")
    return level, bloom


def normalise_company_name(name: str) -> str:
    """'Google LLC (Subsidiary of Alphabet Inc.)' -> 'google'. Used only for matching."""
    text = clean_text(name).lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("&", " ").replace("’", "").replace("'", "")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [w for w in text.split() if w not in _LEGAL_WORDS]
    return " ".join(words)


@dataclass
class CompanyRecord:
    id: int
    name: str
    levels: Dict[str, Optional[Tuple[int, Optional[str]]]]   # code -> (level, bloom) | None
    warnings: List[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return normalise_company_name(self.name)

    def requirement(self, code: str) -> Optional[Tuple[int, Optional[str]]]:
        return self.levels.get(code)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "requirements": {
                code: (None if self.levels.get(code) is None else
                       {"level": self.levels[code][0], "bloom": self.levels[code][1]})
                for code in CATEGORY_ORDER
            },
        }


class CompanyDirectory:
    """All companies, indexed by id and by normalised name."""

    def __init__(self, records: List[CompanyRecord], warnings: Optional[List[str]] = None):
        self.warnings: List[str] = list(warnings or [])
        self.by_id: Dict[int, CompanyRecord] = {}
        for r in records:
            self.by_id[r.id] = r
        # Name -> record. Duplicate names: the highest id wins (latest row), loudly.
        self.by_key: Dict[str, CompanyRecord] = {}
        grouped: Dict[str, List[CompanyRecord]] = {}
        for r in sorted(records, key=lambda x: x.id):
            grouped.setdefault(r.key, []).append(r)
        for key, group in grouped.items():
            chosen = group[-1]
            self.by_key[key] = chosen
            if len(group) > 1:
                ids = ", ".join(str(g.id) for g in group)
                self.warnings.append(
                    f"Duplicate company '{chosen.name}' (ids {ids}); name lookups use id {chosen.id}. "
                    f"Pass company_id to pick a specific row."
                )

    def __len__(self) -> int:
        return len(self.by_id)

    def list(self, query: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        q = normalise_company_name(query) if query else ""
        raw_q = clean_text(query).lower()
        out = []
        for r in sorted(self.by_id.values(), key=lambda x: x.name.lower()):
            if not q and not raw_q or (q and q in r.key) or (raw_q and raw_q in r.name.lower()):
                out.append({"id": r.id, "name": r.name})
        return out[: max(1, limit)]

    def resolve(self, company: Any = None, company_id: Any = None) -> CompanyRecord:
        """Find one company by id or (fuzzy) name; raise typed errors, never guess silently."""
        if company_id is not None and clean_text(company_id) != "":
            try:
                cid = int(str(company_id).strip())
            except ValueError:
                raise CompanyNotFoundError(f"company_id {company_id!r} is not a number")
            rec = self.by_id.get(cid)
            if rec is None:
                raise CompanyNotFoundError(f"No company with id {cid}")
            return rec
        if isinstance(company, int) and not isinstance(company, bool):
            return self.resolve(company_id=company)
        text = clean_text(company)
        if not text:
            raise CompanyNotFoundError("No company given (send 'company' or 'company_id')")
        if text.isdigit():
            return self.resolve(company_id=text)

        key = normalise_company_name(text)
        key = _ALIASES.get(key, _ALIASES.get(text.lower(), key))
        if not key:
            raise CompanyNotFoundError(f"Company name {text!r} has no usable words")
        if key in self.by_key:
            return self.by_key[key]
        q_tokens = set(key.split())
        subset = [r for r in self.by_key.values() if q_tokens and q_tokens <= set(r.key.split())]
        if len(subset) == 1:
            return subset[0]
        if len(subset) > 1:
            raise AmbiguousCompanyError(
                f"{text!r} matches several companies - pick one",
                details=[{"id": r.id, "name": r.name} for r in sorted(subset, key=lambda x: x.name)])
        close = get_close_matches(key, list(self.by_key.keys()), n=3, cutoff=0.8)
        if len(close) == 1:
            return self.by_key[close[0]]
        suggestions = [{"id": self.by_key[c].id, "name": self.by_key[c].name}
                       for c in get_close_matches(key, list(self.by_key.keys()), n=5, cutoff=0.5)]
        raise CompanyNotFoundError(f"No company matches {text!r}", details=suggestions or None)


# ---------------------------------------------------------------------------- row -> record


def _pick(row: Dict[str, Any], keys: Iterable[str]) -> Any:
    for k in keys:
        if k in row:
            return row[k]
    return None


def _norm_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {clean_text(k).lower().replace(" ", "_"): v for k, v in row.items() if k is not None}


def _extract_cell(row: Dict[str, Any], code: str) -> Any:
    """Find the cell for a category code under any of the names the snapshot may use."""
    value = _pick(row, (CODE_TO_COLUMN[code], code.lower(), code))
    if isinstance(value, dict):  # {"level": 5, "bloom": "AP"} snapshot style
        level = value.get("level", value.get("required_level"))
        bloom = value.get("bloom") or value.get("depth")
        if level is None:
            return None
        return f"{level}-{bloom}" if bloom else level
    return value


def records_from_rows(rows: Iterable[Dict[str, Any]], source: str = "rows") -> CompanyDirectory:
    records: List[CompanyRecord] = []
    warnings: List[str] = []
    seen_ids: Dict[int, str] = {}
    next_auto_id = 100000
    for idx, raw in enumerate(rows, start=1):
        if not isinstance(raw, dict):
            warnings.append(f"{source}: row {idx} is not an object - skipped")
            continue
        row = _norm_row(raw)
        name = clean_text(_pick(row, _NAME_KEYS))
        if not name:
            warnings.append(f"{source}: row {idx} has no company name - skipped")
            continue
        rid_raw = row.get("id")
        try:
            rid = int(str(rid_raw).strip())
        except (TypeError, ValueError):
            rid = next_auto_id
            next_auto_id += 1
            warnings.append(f"{source}: '{name}' has no valid id - assigned {rid}")
        if rid in seen_ids:
            warnings.append(f"{source}: id {rid} repeated ('{seen_ids[rid]}' and '{name}') - later row kept")
        seen_ids[rid] = name

        levels: Dict[str, Optional[Tuple[int, Optional[str]]]] = {}
        rec_warnings: List[str] = []
        for code in CATEGORY_ORDER:
            cell = _extract_cell(row, code)
            try:
                levels[code] = parse_cell(cell)
            except CellError as exc:
                levels[code] = None
                rec_warnings.append(f"{name}: {CODE_TO_COLUMN[code]} {exc}")
            else:
                if levels[code] is None:
                    rec_warnings.append(f"{name}: {CODE_TO_COLUMN[code]} is empty")
        if all(v is None for v in levels.values()):
            warnings.append(f"{source}: '{name}' has no usable skill levels - skipped")
            continue
        warnings.extend(rec_warnings)
        records.append(CompanyRecord(id=rid, name=name, levels=levels, warnings=rec_warnings))
    if not records:
        raise CompanyDataError(f"{source}: no usable company rows found", details=warnings[:20])
    return CompanyDirectory(records, warnings)


def _check_columns(fieldnames: Optional[List[str]], source: str) -> None:
    present = {clean_text(f).lower().replace(" ", "_") for f in (fieldnames or []) if f}
    if not present & set(_NAME_KEYS):
        raise CompanyDataError(f"{source}: no company-name column (expected 'companies')")
    missing = [c for c in COLUMN_TO_CODE if c not in present]
    if missing:
        raise CompanyDataError(f"{source}: missing skill columns: {', '.join(missing)}")


def load_company_csv(path: str) -> CompanyDirectory:
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
    except OSError as exc:
        raise CompanyDataError(f"Cannot read company CSV {path}: {exc}")
    reader = csv.DictReader(io.StringIO(text))
    _check_columns(reader.fieldnames, path)
    return records_from_rows(list(reader), source=path)


def load_company_json(path: str) -> CompanyDirectory:
    """Loads talent_check_company_skillsets.json (list of rows, or {'companies': [...]})."""
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise CompanyDataError(f"Cannot read company JSON {path}: {exc}")
    if isinstance(data, dict):
        data = data.get("companies") or data.get("rows") or data.get("data") or []
    if not isinstance(data, list):
        raise CompanyDataError(f"{path}: expected a list of company rows")
    return records_from_rows(data, source=path)


def directory_to_snapshot(directory: CompanyDirectory) -> List[Dict[str, Any]]:
    """Serialise to the table's own shape so the snapshot round-trips through records_from_rows."""
    rows = []
    for rec in sorted(directory.by_id.values(), key=lambda r: r.id):
        row: Dict[str, Any] = {"id": rec.id, "companies": rec.name}
        for code in CATEGORY_ORDER:
            cell = rec.levels.get(code)
            row[CODE_TO_COLUMN[code]] = None if cell is None else (
                f"{cell[0]}-{cell[1]}" if cell[1] else str(cell[0]))
        rows.append(row)
    return rows
