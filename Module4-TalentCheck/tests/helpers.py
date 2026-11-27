import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from talent_check.config import load_settings  # noqa: E402
from talent_check.repository import DataRepository  # noqa: E402
from talent_check.service import TalentCheckService  # noqa: E402


def offline_settings(**over):
    """Settings that never touch the network or the developer's real .env."""
    from dataclasses import replace
    s = load_settings(read_dotenv=False)
    base = replace(s, supabase_url=None, supabase_key=None, source="csv", strict_source=False,
                   data_dir=os.path.join(ROOT, "data"), cache_ttl=300.0)
    return replace(base, **over) if over else base


def make_service(**over):
    return TalentCheckService(DataRepository(offline_settings(**over)))


def load_samples():
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "samples", "profiles", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            p = json.load(fh)
        out[p["name"].split()[0]] = p
    return out
