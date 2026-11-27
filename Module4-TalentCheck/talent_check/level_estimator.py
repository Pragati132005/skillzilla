<<<<<<< HEAD
"""Estimate a candidate's level (0-10) in each of the 12 skillsets from the evidence in a profile.

Why not just "low -> 2"?  Because the same word hides very different people.  Every claim is turned
into an *evidence unit* (a skill line, a project, an internship ...).  For each skillset a unit gets a
value on the 1-10 rubric scale:

    value = tier(cue)                 what the keyword belongs to in the rubric  (Docker = DevOps L4)
            x applied-or-listed       a skill only *listed* counts 70 %, one that is *used* counts 100 %
            - hedges                  "basic", "exposure", "fundamentals" ...
            + strong words            "production", "scalable", "winner", "merged" ...
            + source bonus            internship / hackathon result / certificate
            + confidence adjustment   Module 2/3's high / medium / low

and the skillset level is built from those values:

    level = best value
            - corroboration penalty   (0.9 if a single unit supports it, 0.45 if two, 0 from three)
            + breadth bonus           (0.12 per extra unit, max 5)
            + CGPA nudge (optional, +/-0.25 on foundational CS skillsets)

Two candidates who both write "basic Java" therefore only tie if *everything* behind it ties: add a
project, an internship, a library, a result - the level moves.  The function is monotonic: more or
stronger evidence can never lower a level.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .config import BLOOM_LABEL, CATEGORY_ORDER, DEFAULT_SCORING, ScoringConfig
from .lexicon import (BLOOM_VERBS, CP_CONTEXT_RE, CUES, HEDGE_RE, STRONG_RE, VOLUME_RE)
from .profile_adapter import NormalisedProfile, Unit
from .rubric import Rubric
from .text_utils import clip, content_tokens, round_half_up

_CONF_ADJ = {"high": 0.0, "medium": -0.3, "low": -0.8, None: 0.0}
_FOUNDATIONAL = {"COD", "DSA", "OOD", "OS", "NETW", "SWE", "SQL"}
_WIN_RE = re.compile(r"\b(winner|won|first place|champion|1st)\b")
_PLACE_RE = re.compile(r"\b(finalist|runner-?up|second place|top \d+|shortlisted|semi-?finalist)\b")
DEFAULT_LISTED_TIER = 3.0   # a skill tagged to a skillset by Module 3 but with no sharper cue


@dataclass
class UnitValue:
    category: str
    value: float
    tier: float
    source: str
    text: str
    bloom: int
    applied: bool


@dataclass
class CategoryEstimate:
    code: str
    level_exact: float = 0.0
    level: int = 0
    has_evidence: bool = False
    bloom: int = 0
    evidence_count: int = 0
    top_evidence: List[UnitValue] = field(default_factory=list)


class RubricMatcher:
    """Matches unit text against rubric topic phrases (>=3 content words, >=75 % present)."""

    def __init__(self, rubric: Optional[Rubric]):
        self._topics: List[Tuple[str, int, frozenset]] = []
        if rubric is not None:
            for code, level, topic in rubric.iter_topics():
                toks = frozenset(content_tokens(topic))
                if len(toks) >= 3:
                    self._topics.append((code, level, toks))

    def match(self, text: str) -> Dict[str, float]:
        if not self._topics:
            return {}
        have = set(content_tokens(text))
        best: Dict[str, float] = {}
        for code, level, toks in self._topics:
            hit = len(toks & have)
            if hit >= 3 and hit / len(toks) >= 0.75:
                best[code] = max(best.get(code, 0.0), float(level))
        return best


def _bloom_of(text: str, applied: bool, hedged: bool) -> int:
    for rank in (5, 4, 3, 2):
        if BLOOM_VERBS[rank].search(text):
            return rank
    if hedged or not applied:
        return 1
    return 2


def _unit_cues(unit: Unit, matcher: RubricMatcher) -> Dict[str, float]:
    cues: Dict[str, float] = {}
    for rx, code, tier in CUES:
        if rx.search(unit.text):
            cues[code] = max(cues.get(code, 0.0), tier)
    for code, tier in matcher.match(unit.text).items():
        # rubric phrases are slightly less reliable than curated cues: shave half a level
        cues[code] = max(cues.get(code, 0.0), tier - 0.5)
    m = VOLUME_RE.search(unit.text)
    if m and CP_CONTEXT_RE.search(unit.text):
        n = int(m.group(1))
        dsa = 8.0 if n >= 500 else 7.2 if n >= 300 else 6.0 if n >= 150 else 5.0 if n >= 50 else 3.5 if n >= 10 else 2.5
        for code, t in (("DSA", dsa), ("COD", dsa - 1.0), ("APTI", dsa - 2.0)):
            cues[code] = max(cues.get(code, 0.0), t)
    if unit.tagged_category and unit.tagged_category not in cues:
        cues[unit.tagged_category] = DEFAULT_LISTED_TIER
    return cues


def _source_bonus(unit: Unit) -> float:
    if unit.source == "internship" or unit.source == "experience":
        return 0.6
    if unit.source == "hackathon":
        if _WIN_RE.search(unit.text):
            return 0.6
        if _PLACE_RE.search(unit.text):
            return 0.4
        return 0.1
    if unit.source == "certification":
        return 0.3
    if unit.source == "achievement":
        return 0.2
    return 0.0


def _is_applied(unit: Unit) -> bool:
    if unit.source in ("project", "internship", "hackathon", "achievement", "experience", "skill_evidence"):
        return True
    if unit.source == "certification":
        return True
    return any(BLOOM_VERBS[r].search(unit.text) for r in (2, 3, 4, 5))


def evaluate_units(profile: NormalisedProfile, matcher: RubricMatcher,
                   cfg: ScoringConfig = DEFAULT_SCORING) -> Dict[str, List[UnitValue]]:
    per_cat: Dict[str, List[UnitValue]] = {c: [] for c in CATEGORY_ORDER}
    for unit in profile.units:
        cues = _unit_cues(unit, matcher)
        if not cues:
            continue
        applied = _is_applied(unit)
        n_hedge = len(HEDGE_RE.findall(unit.text))
        n_strong = len(STRONG_RE.findall(unit.text))
        hedged = n_hedge > 0
        factor = 1.0 if applied else cfg.mention_only_factor
        if unit.source == "certification":
            factor = 0.85
        for code, tier in cues.items():
            if code not in per_cat:
                continue
            val = tier * factor
            val -= min(cfg.hedge_penalty * n_hedge, cfg.max_hedge_penalty)
            if applied and n_strong:
                val += min(0.4 * n_strong, 0.8)
            val = min(val, tier + 1.0)
            val += _source_bonus(unit) + _CONF_ADJ.get(unit.confidence, 0.0)
            val = clip(val, 0.0, 10.0)
            per_cat[code].append(UnitValue(code, round(val, 3), tier, unit.source, unit.raw,
                                           _bloom_of(unit.text, applied, hedged), applied))
    return per_cat


def estimate_levels(profile: NormalisedProfile, rubric: Optional[Rubric] = None,
                    cfg: ScoringConfig = DEFAULT_SCORING,
                    matcher: Optional[RubricMatcher] = None) -> Dict[str, CategoryEstimate]:
    matcher = matcher or RubricMatcher(rubric)
    per_cat = evaluate_units(profile, matcher, cfg)
    cgpa_nudge = 0.0
    if cfg.use_cgpa and profile.cgpa_ratio is not None:
        cgpa_nudge = clip((profile.cgpa_ratio - 0.75) / 0.15, -1.0, 1.0) * cfg.cgpa_max_nudge

    result: Dict[str, CategoryEstimate] = {}
    for code in CATEGORY_ORDER:
        values = sorted(per_cat[code], key=lambda u: u.value, reverse=True)
        est = CategoryEstimate(code=code)
        if not values:
            result[code] = est
            continue
        # one sentence can trigger several cues in a category: count each source text once
        seen, distinct = set(), []
        for v in values:
            if v.text in seen:
                continue
            seen.add(v.text)
            distinct.append(v)
        top = distinct[0].value
        near = [u for u in distinct if u.value >= top - 2.0]
        penalty = 0.9 if len(near) == 1 else 0.45 if len(near) == 2 else 0.0
        breadth = 0.12 * min(len(distinct) - 1, 5)
        level = top - penalty + breadth
        # realism ceiling: breadth/bonuses can never lift a skillset far above the best thing actually shown
        level = min(level, max(u.tier for u in distinct) + 0.7)
        if code in _FOUNDATIONAL:
            level += cgpa_nudge
        level = clip(level, 0.0, 10.0)
        est.level_exact = round(level, 2)
        est.has_evidence = True
        est.level = max(1, round_half_up(level))
        est.evidence_count = len(distinct)
        est.bloom = max(u.bloom for u in near)
        est.top_evidence = distinct[:3]
        result[code] = est
    return result


def bloom_label(rank: int) -> Optional[str]:
    return BLOOM_LABEL.get(rank)
=======
"""Deterministic rubric-driven proficiency estimator with deduplicated evidence."""
import re
from .schemas import CATEGORIES
ALIASES={'OOD':['Object-Oriented Design','Object-Oriented Programming and Design'],'APTI':['Aptitude','Aptitude and Problem Solving'],'COMM':['Communication','Communication Skills'],'AI':['AI','AI Native Engineering'],'CLOUD':['Cloud','DevOps and Cloud'],'SQL':['SQL','SQL and Design','SQL & Design'],'SYSD':['System Design','System Design and Architecture'],'NETW':['Networking','Computer Networking'],'OS':['Operating Systems','Operating System']}
def norm(s): return re.sub(r'[^a-z0-9+#.]+',' ',str(s).casefold()).strip()
def flatten(v):
    if v is None:return ''
    if isinstance(v,str):return v
    if isinstance(v,dict):return ' '.join(flatten(x) for k,x in v.items() if k not in {'email','phone','name','id'})
    if isinstance(v,(list,tuple,set)):return ' '.join(flatten(x) for x in v)
    return str(v)
def topic_match(topic,evidence):
    t,e=norm(topic),norm(evidence)
    if not t or not e:return False
    if t in e:return True
    stop={'and','or','the','of','for','with','to','in','a','an','on','using','basic','introduction'}
    tt={x for x in t.split() if x not in stop and len(x)>1}; et=set(e.split())
    return bool(tt) and len(tt&et)>=min(2,len(tt)) and len(tt&et)/len(tt)>=.65
def estimate_level(cat,evidence,topics):
    if cat not in CATEGORIES or not evidence:return 1
    areas={x.casefold() for x in ALIASES.get(cat,[CATEGORIES[cat]])}
    areas.add(CATEGORIES[cat].casefold())
    candidates=topics[topics.skill_area.astype(str).str.strip().str.casefold().isin(areas)]
    # Deduplicate repeated phrases and evidence before counting support.
    text=' '.join(dict.fromkeys(norm(x) for x in evidence if norm(x)))
    if candidates.empty:return 1
    matched=[]
    for _,row in candidates.iterrows():
        signals={norm(x) for x in str(row.topics).split(';') if norm(x) and topic_match(x,text)}
        level=int(row.level_num)
        if len(signals)>=(1 if level<=3 else 2): matched.append((level,signals))
    if not matched:
        applied=any(x in text for x in ('built', 'implemented', 'designed',
        'deployed', 'shipped', 'developed', 'tested',
        'wrote', 'created', 'used', 'queried',
        'executed', 'analyzed', 'analysed'))
        return 2 if applied else 1
    level=max(x[0] for x in matched)
    distinct=set().union(*(x[1] for x in matched))
    # Advanced levels require a breadth of independent rubric signals.
    if level>=7 and len(distinct)<4: level=min(level,6)
    if level>=5 and len(distinct)<2: level=min(level,4)
    return max(1,min(10,level))
>>>>>>> 4c9d1dbefd237039dacabfd3cd53abe17201b131
