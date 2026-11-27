<<<<<<< HEAD
"""Public entry point: run_talent_check(profile, company) -> contract-shaped result dict."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .config import DEFAULT_SCORING, ScoringConfig
from .level_estimator import RubricMatcher, estimate_levels
from .profile_adapter import normalise_profile
from .repository import DataRepository
from .scoring import compare


class TalentCheckService:
    def __init__(self, repository: Optional[DataRepository] = None, cfg: ScoringConfig = DEFAULT_SCORING):
        self.repo = repository or DataRepository()
        self.cfg = cfg
        self._matcher: Optional[RubricMatcher] = None
        self._matcher_rubric = None

    def _get_matcher(self):
        rubric = self.repo.get_rubric()
        if self._matcher is None or rubric is not self._matcher_rubric:
            self._matcher = RubricMatcher(rubric)
            self._matcher_rubric = rubric
        return rubric, self._matcher

    def run(self, profile: Any, company: Any = None, company_id: Any = None) -> Dict[str, Any]:
        prof = normalise_profile(profile)                       # raises ProfileError
        directory, source = self.repo.get_directory()
        record = directory.resolve(company=company, company_id=company_id)   # typed errors
        rubric, matcher = self._get_matcher()
        estimates = estimate_levels(prof, rubric, self.cfg, matcher)
        relevant = [w for w in directory.warnings if record.name in w]
        return compare(prof, estimates, record, rubric, self.cfg, data_source=source, data_warnings=relevant)

    def companies(self, query: str = "", limit: int = 200):
        directory, source = self.repo.get_directory()
        return {"data_source": source, "total": len(directory), "companies": directory.list(query, limit)}

    def company(self, company: Any = None, company_id: Any = None):
        directory, source = self.repo.get_directory()
        rec = directory.resolve(company=company, company_id=company_id)
        out = rec.to_dict()
        out["data_source"] = source
        return out


def run_talent_check(profile: Any, company: Any = None, company_id: Any = None,
                     service: Optional[TalentCheckService] = None) -> Dict[str, Any]:
    return (service or TalentCheckService()).run(profile, company=company, company_id=company_id)
=======
"""Application service; explanations are separate to preserve Module 3's exact JSON contract."""
from .scoring import score_profile,BENCHMARK_COLUMNS
from .repository import load_company_levels
from .profile_adapter import adapt_profile

def run_talent_check(payload):
    if not isinstance(payload,dict): raise ValueError('Request body must be a JSON object.')
    company=payload.get('company')
    if not isinstance(company,str) or not company.strip(): raise ValueError('company is required.')
    profile=adapt_profile(payload)
    result=score_profile(profile,company)
    levels={x['category_code']:x for x in result['skillset_gap']}
    strengths=[x['category_code'] for x in result['skillset_gap'] if not x['gap']]
    gaps=[x['category_code'] for x in result['skillset_gap'] if x['gap']]
    result['explanation']={
      'summary': f"{profile.get('name') or 'The candidate'} meets the benchmark in {len(strengths)} of 12 skill categories for {result['company']}; {len(gaps)} categories show a gap.",
      'strengths': strengths,
      'priority_gaps': sorted(gaps,key=lambda c: levels[c]['required_level']-levels[c]['candidate_level'],reverse=True)[:3],
      'recommendations': [f"Build and document a project demonstrating {c} at level {levels[c]['required_level']}. Current evidence supports level {levels[c]['candidate_level']}." for c in sorted(gaps,key=lambda c: levels[c]['required_level']-levels[c]['candidate_level'],reverse=True)[:3]]
    }
    return result
>>>>>>> 4c9d1dbefd237039dacabfd3cd53abe17201b131
