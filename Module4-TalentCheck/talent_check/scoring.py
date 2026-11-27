<<<<<<< HEAD
"""Readiness score + per-skillset gap breakdown (the Module 4 output).

Definition of "ready" (a design decision the brief asks the team to make explicitly):

    attainment_i = min(candidate_level_i / required_level_i, 1) x depth_factor_i
    depth_factor_i = (1 - w) + w x min(candidate_depth_i / required_depth_i, 1)        w = bloom_weight (0.10)
    readiness = 100 x  sum(required_level_i x attainment_i) / sum(required_level_i)

* Weighting by required level means the skillsets a company cares about most dominate the score.
* Surplus never compensates for a shortfall elsewhere (attainment is capped at 1).
* A skillset is a *gap* when candidate_level < required_level (integer levels, exactly what the UI shows),
  so the score can always be recomputed by hand from the visible numbers.
* Skillsets the company table leaves blank are excluded (no requirement = nothing to fall short of).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .company_data import CompanyRecord
from .config import (BLOOM_LABEL, BLOOM_MEANING, BLOOM_RANK, CATEGORY_NAMES, CATEGORY_ORDER, DEFAULT_SCORING,
                     SCORING_VERSION, ScoringConfig)
from .level_estimator import CategoryEstimate
from .profile_adapter import NormalisedProfile
from .rubric import Rubric


def readiness_label(score: float, cfg: ScoringConfig = DEFAULT_SCORING) -> str:
    if score >= cfg.ready_threshold:
        return "Ready"
    if score >= cfg.almost_threshold:
        return "Almost ready"
    if score >= cfg.developing_threshold:
        return "Developing"
    return "Early stage"


def _depth_factor(cand_rank: int, req_bloom: Optional[str], cfg: ScoringConfig) -> float:
    if req_bloom is None or req_bloom not in BLOOM_RANK or BLOOM_RANK[req_bloom] == 0:
        return 1.0
    ratio = min(cand_rank / BLOOM_RANK[req_bloom], 1.0)
    return (1.0 - cfg.bloom_weight) + cfg.bloom_weight * ratio


def compare(profile: NormalisedProfile, estimates: Dict[str, CategoryEstimate], company: CompanyRecord,
            rubric: Optional[Rubric] = None, cfg: ScoringConfig = DEFAULT_SCORING,
            data_source: str = "", data_warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    gaps: List[Dict[str, Any]] = []
    weight_sum = 0.0
    weighted = 0.0
    critical: List[Dict[str, Any]] = []
    strengths: List[Dict[str, Any]] = []
    next_steps: List[Dict[str, Any]] = []

    for code in CATEGORY_ORDER:
        est = estimates[code]
        req = company.requirement(code)
        req_level = req[0] if req else None
        req_bloom = req[1] if req else None
        cand_level = est.level if est.has_evidence else 0
        cand_bloom = BLOOM_LABEL.get(est.bloom) if est.has_evidence else None

        entry: Dict[str, Any] = {
            "category_code": code,
            "required_level": req_level,
            "candidate_level": cand_level,
            "gap": bool(req_level is not None and cand_level < req_level),
            # ---- extras (safe for Module 3 to ignore) ----
            "category_name": CATEGORY_NAMES[code],
            "candidate_level_exact": est.level_exact,
            "required_depth": req_bloom,
            "candidate_depth": cand_bloom,
            "has_evidence": est.has_evidence,
            "gap_size": 0 if req_level is None else max(0, req_level - cand_level),
            "status": "no_requirement" if req_level is None else
                      ("no_evidence" if not est.has_evidence else ("gap" if cand_level < req_level else "met")),
            "evidence": [
                {"text": u.text[:160], "source": u.source, "implied_level": round(u.value, 1)}
                for u in est.top_evidence
            ],
        }
        if req_level is not None:
            att = min(cand_level / req_level, 1.0) * _depth_factor(est.bloom if est.has_evidence else 0,
                                                                 req_bloom, cfg)
            entry["attainment"] = round(att, 3)
            weight_sum += req_level
            weighted += req_level * att
            if entry["gap"] and entry["gap_size"] >= cfg.critical_gap_levels:
                critical.append({"category_code": code, "gap_size": entry["gap_size"]})
            if not entry["gap"] and est.has_evidence:
                strengths.append({"category_code": code, "candidate_level": cand_level,
                                  "required_level": req_level})
            if entry["gap"] and rubric is not None:
                target = min(cand_level + 1, req_level)
                topics = rubric.level_topics(code, target)
                if topics:
                    next_steps.append({"category_code": code, "target_level": target,
                                       "focus_topics": topics, "gap_size": entry["gap_size"]})
        else:
            entry["attainment"] = None
        gaps.append(entry)

    score = round(100.0 * weighted / weight_sum, 1) if weight_sum > 0 else 0.0
    critical.sort(key=lambda g: (-g["gap_size"], CATEGORY_ORDER.index(g["category_code"])))
    next_steps.sort(key=lambda g: (-g["gap_size"], CATEGORY_ORDER.index(g["category_code"])))
    strengths.sort(key=lambda s: (-(s["candidate_level"] - s["required_level"]), CATEGORY_ORDER.index(s["category_code"])))

    warnings = list(profile.warnings)
    warnings.extend(w for w in (data_warnings or []))
    warnings.extend(company.warnings)
    no_evidence = [g["category_code"] for g in gaps if g["status"] == "no_evidence"]
    if no_evidence:
        warnings.append("No evidence found in the profile for: " + ", ".join(no_evidence))

    return {
        # ---- contract fields (section 06 of the brief) ----
        "company": company.name,
        "skillset_gap": gaps,
        "readiness_score": score,
        # ---- extras ----
        "company_id": company.id,
        "readiness_label": readiness_label(score, cfg),
        "candidate": {"name": profile.name, "email": profile.email},
        "critical_gaps": critical[:5],
        "strengths": strengths[:5],
        "next_steps": next_steps[:5],
        "depth_legend": BLOOM_MEANING,
        "data_source": data_source,
        "scoring_version": SCORING_VERSION,
        "warnings": warnings,
    }
=======
import re
from .schemas import CATEGORIES,CATEGORY_ALIASES
from .repository import load_skill_topics,load_company_levels
from .level_estimator import estimate_level,flatten,norm
from .rubric import validate_rubric,validate_benchmarks
BENCHMARK_COLUMNS={'COD':'coding','DSA':'data_structures_and_algorithms','OOD':'object_oriented_programming_and_design','APTI':'aptitude_and_problem_solving','COMM':'communication_skills','AI':'ai_native_engineering','CLOUD':'devops_and_cloud','SQL':'sql_and_design','SWE':'software_engineering','SYSD':'system_design_and_architecture','NETW':'computer_networking','OS':'operating_system'}
def _category(v):
 s=str(v or '').strip()
 if s.upper() in CATEGORIES:return s.upper()
 return CATEGORY_ALIASES.get(norm(s),'OTHER')
def _find_company(company,rows):
 target=norm(company)
 if not target: raise ValueError('company must not be blank.')
 names=rows.companies.astype(str)
 exact=rows[names.map(norm)==target]
 if len(exact)==1:return exact.iloc[0]
 # Strict selection: no fuzzy/substring match that could pick the wrong benchmark.
 if len(exact)>1:raise ValueError(f'Duplicate exact company benchmark for {company!r}. Fix source data.')
 available=sorted(names.tolist())
 raise ValueError(f'Unknown company {company!r}. Use an exact canonical name. Available companies: {available[:30]}')
def _required_level(raw):
 m=re.match(r'^\s*(10|[1-9])(?:\s*(?:-|$))',str(raw))
 if not m: raise ValueError(f'Invalid company benchmark level: {raw!r}')
 return int(m.group(1))
def _evidence(profile):
 evidence={cat:[] for cat in CATEGORIES}
 global_parts=[]
 for key in ('education','projects','hackathons','internships','certifications','achievements','experience','technical_skills','summary','bio','work_experience'):
  if profile.get(key):global_parts.append(flatten(profile[key]))
 for item in profile.get('skills',[]) or []:
  if isinstance(item,str): global_parts.append(item); continue
  if not isinstance(item,dict): continue
  cat=_category(item.get('category_code') or item.get('category') or item.get('skill_area'))
  text=' '.join(str(item.get(k) or '') for k in ('skill_name','evidence','description','name','proficiency','details'))
  if text.strip() and cat in evidence:evidence[cat].append(text)
  if text.strip():global_parts.append(text)
 # Category signal routing uses explicit category evidence first, then category-specific global evidence.
 alltext=' '.join(global_parts)
 signals={'COD':['coding','programming','python','java','c++','debugging','functions','code'],'DSA':['data structures','algorithms','big o','complexity','recursion'],'OOD':['object oriented','oop','classes','design patterns'],'APTI':['aptitude','problem solving','logical reasoning','quantitative'],'COMM':['communication','presentation','stakeholder','documentation'],'AI':['machine learning','artificial intelligence','scikit learn','regression','neural network'],'CLOUD':['cloud','docker','kubernetes','devops','deployment','distributed','scalable'],'SQL':['sql','mysql','database','query','relational'],'SWE':['software engineering','testing','unit tests','version control','maintainable','production'],'SYSD':['system design','architecture','pub sub','distributed service'],'NETW':['networking','tcp','http','dns','network protocols'],'OS':['operating system','process scheduling','multithreaded','linux','memory management']}
 for cat,terms in signals.items():
  if not evidence[cat] and any(norm(term) in norm(alltext) for term in terms): evidence[cat].append(alltext)
 return evidence
def score_profile(profile,company):
    topics=load_skill_topics(); companies=load_company_levels()
    validate_rubric(topics); validate_benchmarks(companies,BENCHMARK_COLUMNS)
    row=_find_company(company,companies); ev=_evidence(profile)
    output=[]; points=[]
    for cat,col in BENCHMARK_COLUMNS.items():
        required=_required_level(row[col]); candidate=estimate_level(cat,ev[cat],topics)
        gap=candidate<required
        output.append({'category_code':cat,'required_level':required,'candidate_level':candidate,'gap':gap})
        points.append(max(0, min(1, candidate / required)) if required>0 else 0)
  # An empty profile must not receive readiness credit.
  #has_evidence = bool(profile.get("skills"))

  #if not has_evidence:
       # readiness = 0
  #else:
   #     readiness = round(100 * sum(points) / len(points))
 
  #return {'company':str(row.companies),'skillset_gap':output,'readiness_score':max(0,min(100,readiness))}
 
    def _has_usable_evidence(profile):
        if not isinstance(profile, dict):
            return False

        evidence_fields = (
            "skills",
            "summary",
            "bio",
            "projects",
            "hackathons",
            "experience",
            "internships",
            "internships_and_experience",
            "certifications",
            "education",
            "achievements",
            "technical_skills",
            "work_experience",
        )

        def contains_evidence(value):
            if isinstance(value, str):
                return bool(value.strip())

            if isinstance(value, dict):
                return any(
                    contains_evidence(item)
                    for item in value.values()
                )

            if isinstance(value, (list, tuple)):
                return any(contains_evidence(item) for item in value)

            return False

        return any(
            contains_evidence(profile.get(field))
            for field in evidence_fields
        )

 
    has_evidence = _has_usable_evidence(profile)
    if not has_evidence:
        readiness = 0
    else:
        readiness = round(100 * sum(points) / len(points)) if points else 0

    return {
        "company": str(row.companies),
        "skillset_gap": output,
        "readiness_score": max(0, min(100, readiness))
 }
    
    
>>>>>>> 4c9d1dbefd237039dacabfd3cd53abe17201b131
