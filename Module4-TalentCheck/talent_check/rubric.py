<<<<<<< HEAD
"""Level rubric: what each of the 10 levels of each skillset actually covers (STAGIN_1.CSV)."""
from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, Iterable, List

from .config import MAX_LEVEL, MIN_LEVEL, RUBRIC_AREA_TO_CODE
from .errors import CompanyDataError
from .text_utils import clean_text


class Rubric:
    def __init__(self, topics: Dict[str, Dict[int, List[str]]], warnings: List[str]):
        self.topics = topics          # code -> level -> [topic phrases]
        self.warnings = warnings

    def level_topics(self, code: str, level: int) -> List[str]:
        return list(self.topics.get(code, {}).get(level, []))

    def iter_topics(self):
        for code, levels in self.topics.items():
            for level, items in levels.items():
                for t in items:
                    yield code, level, t


def rubric_from_rows(rows: Iterable[Dict[str, Any]], source: str = "rubric") -> Rubric:
    topics: Dict[str, Dict[int, List[str]]] = {}
    warnings: List[str] = []
    for idx, raw in enumerate(rows, start=1):
        row = {clean_text(k).lower(): v for k, v in raw.items() if k is not None}
        area = clean_text(row.get("skill_area")).lower()
        code = RUBRIC_AREA_TO_CODE.get(area)
        if code is None:
            warnings.append(f"{source}: row {idx} unknown skill_area {area!r} - skipped")
            continue
        m = re.search(r"(\d+)", clean_text(row.get("levels")))
        if not m or not (MIN_LEVEL <= int(m.group(1)) <= MAX_LEVEL):
            warnings.append(f"{source}: row {idx} ({area}) has invalid level {row.get('levels')!r} - skipped")
            continue
        level = int(m.group(1))
        items = [clean_text(t) for t in clean_text(row.get("topics")).split(";")]
        items = [t for t in items if t]
        if not items:
            warnings.append(f"{source}: row {idx} ({area} L{level}) has no topics")
            continue
        topics.setdefault(code, {})[level] = items
    if not topics:
        raise CompanyDataError(f"{source}: no usable rubric rows")
    return Rubric(topics, warnings)


def load_rubric_csv(path: str) -> Rubric:
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
    except OSError as exc:
        raise CompanyDataError(f"Cannot read rubric CSV {path}: {exc}")
    return rubric_from_rows(list(csv.DictReader(io.StringIO(text))), source=path)
=======
"""Rubric integrity checks and canonical category mapping."""
from .schemas import CATEGORIES,CATEGORY_ALIASES
from .level_estimator import norm

def validate_rubric(topics):
    required={'skill_area','level_num','topics'}
    if not required<=set(topics.columns): raise RuntimeError(f'Rubric missing {sorted(required-set(topics.columns))}')
    if topics.duplicated(['skill_area','level_num']).any(): raise RuntimeError('Duplicate rubric area/level entries.')
    areas={norm(x) for x in topics.skill_area}
    missing=[]
    aliases={'COD':['coding'],'DSA':['data structures and algorithms'],'OOD':['object oriented design','object oriented programming and design'],'APTI':['aptitude','aptitude and problem solving'],'COMM':['communication','communication skills'],'AI':['ai','ai native engineering'],'CLOUD':['cloud','devops and cloud'],'SQL':['sql','sql and design','sql & design'],'SWE':['software engineering'],'SYSD':['system design','system design and architecture'],'NETW':['networking','computer networking'],'OS':['operating systems','operating system']}
    for cat in CATEGORIES:
        if not any(norm(a) in areas for a in aliases.get(cat,[CATEGORIES[cat]])): missing.append(cat)
    if missing: raise RuntimeError(f'Rubric lacks coverage for categories: {missing}')
    if not topics.level_num.between(1,10).all(): raise RuntimeError('Rubric levels outside 1–10.')
    return True

def validate_benchmarks(rows,columns):
    missing=[c for c in columns.values() if c not in rows.columns]
    if missing: raise RuntimeError(f'Benchmark columns missing: {missing}')
    import re
    for _,row in rows.iterrows():
        for cat,col in columns.items():
            m=re.match(r'^\s*(10|[1-9])(?:\s*(?:-|$))',str(row[col]))
            if not m: raise RuntimeError(f'Invalid benchmark level for {row.companies}/{cat}: {row[col]!r}')
    return True
>>>>>>> 4c9d1dbefd237039dacabfd3cd53abe17201b131
