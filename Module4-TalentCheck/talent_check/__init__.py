"""RADIX Talent Match - Module 4: Talent Check."""
from .config import SCORING_VERSION
from .service import TalentCheckService, run_talent_check

__all__ = ["TalentCheckService", "run_talent_check", "SCORING_VERSION"]
__version__ = SCORING_VERSION
