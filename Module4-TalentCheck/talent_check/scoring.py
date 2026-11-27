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
