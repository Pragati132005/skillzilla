"""Central constants + environment-driven settings."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

SCORING_VERSION = "1.0.0"

# Canonical order of the 12 RADIX skillsets (shared data contract, section 06 of the brief).
CATEGORY_ORDER: List[str] = [
    "COD", "DSA", "OOD", "APTI", "COMM", "AI",
    "CLOUD", "SQL", "SWE", "SYSD", "NETW", "OS",
]

CATEGORY_NAMES: Dict[str, str] = {
    "COD": "Coding",
    "DSA": "Data Structures & Algorithms",
    "OOD": "Object-Oriented Design",
    "APTI": "Aptitude & Problem Solving",
    "COMM": "Communication",
    "AI": "AI",
    "CLOUD": "DevOps & Cloud",
    "SQL": "SQL & Design",
    "SWE": "Software Engineering",
    "SYSD": "System Design & Architecture",
    "NETW": "Computer Networking",
    "OS": "Operating Systems",
}

# Supabase / CSV column  ->  contract category code
COLUMN_TO_CODE: Dict[str, str] = {
    "coding": "COD",
    "data_structures_and_algorithms": "DSA",
    "object_oriented_programming_and_design": "OOD",
    "aptitude_and_problem_solving": "APTI",
    "communication_skills": "COMM",
    "ai_native_engineering": "AI",
    "devops_and_cloud": "CLOUD",
    "sql_and_design": "SQL",
    "software_engineering": "SWE",
    "system_design_and_architecture": "SYSD",
    "computer_networking": "NETW",
    "operating_system": "OS",
}
CODE_TO_COLUMN: Dict[str, str] = {v: k for k, v in COLUMN_TO_CODE.items()}

# Rubric "skill_area" (normalised: lower-case, trimmed)  ->  contract category code
RUBRIC_AREA_TO_CODE: Dict[str, str] = {
    "coding": "COD",
    "data structures and algorithms": "DSA",
    "object-oriented programming and design": "OOD",
    "aptitude and problem solving": "APTI",
    "communication skills": "COMM",
    "ai native engineering": "AI",
    "devops and cloud": "CLOUD",
    "sql & design": "SQL",
    "software engineering": "SWE",
    "system design and architecture": "SYSD",
    "computer networking": "NETW",
    "operating system": "OS",
}

# Bloom-style depth codes used in the company table ("5-AP").
BLOOM_RANK: Dict[str, int] = {"RE": 0, "CU": 1, "AP": 2, "AS": 3, "EV": 4, "CR": 5}
BLOOM_LABEL: Dict[int, str] = {0: "RE", 1: "CU", 2: "AP", 3: "AS", 4: "EV", 5: "CR"}
BLOOM_MEANING: Dict[str, str] = {
    "RE": "Remember", "CU": "Understand", "AP": "Apply",
    "AS": "Analyse", "EV": "Evaluate", "CR": "Create",
}

MIN_LEVEL = 1
MAX_LEVEL = 10


@dataclass(frozen=True)
class ScoringConfig:
    """Every tunable number lives here so the team can debate it in one place."""
    bloom_weight: float = 0.10          # share of each skillset's score driven by depth-of-skill (Bloom) match
    use_cgpa: bool = True               # small +/-0.25 level nudge on foundational CS skillsets
    cgpa_max_nudge: float = 0.25
    critical_gap_levels: int = 3        # shortfall (in levels) at which a gap is flagged "critical"
    ready_threshold: float = 80.0       # >= : "Ready"
    almost_threshold: float = 60.0      # >= : "Almost ready"
    developing_threshold: float = 40.0  # >= : "Developing", below: "Early stage"
    mention_only_factor: float = 0.70   # a skill that is only *listed* (no applied evidence) counts at 70 %
    hedge_penalty: float = 0.8          # "basic", "exposure", "fundamentals" ... lower the implied level
    max_hedge_penalty: float = 1.6


DEFAULT_SCORING = ScoringConfig()


def _load_dotenv(path: str = ".env") -> None:
    """Tiny .env reader (no dependency). Real environment variables always win."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_num(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    supabase_url: Optional[str]
    supabase_key: Optional[str]
    company_table: str
    rubric_table: Optional[str]
    source: str                 # auto | supabase | csv
    strict_source: bool
    cache_ttl: float
    host: str
    port: int
    cors_origins: List[str]
    data_dir: str

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


def load_settings(read_dotenv: bool = True) -> Settings:
    if read_dotenv:
        _load_dotenv()
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    origins = os.environ.get("TALENT_CHECK_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    return Settings(
        supabase_url=(os.environ.get("SUPABASE_URL") or "").strip().rstrip("/") or None,
        supabase_key=(os.environ.get("SUPABASE_KEY") or "").strip() or None,
        company_table=(os.environ.get("SUPABASE_COMPANY_TABLE") or "staging_company_skill_levels").strip(),
        rubric_table=(os.environ.get("SUPABASE_RUBRIC_TABLE") or "").strip() or None,
        source=(os.environ.get("TALENT_CHECK_SOURCE") or "auto").strip().lower(),
        strict_source=_env_bool("TALENT_CHECK_STRICT_SOURCE", False),
        cache_ttl=_env_num("TALENT_CHECK_CACHE_TTL", 300.0),
        host=os.environ.get("TALENT_CHECK_HOST", "127.0.0.1"),
        port=int(_env_num("TALENT_CHECK_PORT", 8010)),
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        data_dir=os.path.join(base, "data"),
    )
