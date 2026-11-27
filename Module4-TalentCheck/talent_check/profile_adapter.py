"""Turns the saved profile from Module 3 (Profile Builder) into clean evidence units.

Accepted input is deliberately tolerant - Module 3 is built by someone else and will evolve:

* contract fields:  name, email, education, skills[], hackathons[], internships[], certifications[],
  preferred_roles[], cv_file
* optional extras:  projects[], achievements[], experience[], summary, cgpa
* skills[] items may be full objects {skill_name, category_code, evidence, confidence} or plain strings
* list items in the other fields may be strings or objects (any string values are read)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import CATEGORY_ORDER
from .errors import ProfileError
from .text_utils import clean_text, normalise_for_match, split_units

MAX_SKILLS = 500
MAX_ITEMS_PER_LIST = 200
MAX_TEXT = 2000

_CODE_ALIASES = {
    "COD": "COD", "CODING": "COD", "CODE": "COD", "PROGRAMMING": "COD",
    "DSA": "DSA", "DS&A": "DSA", "DATA STRUCTURES": "DSA", "ALGORITHMS": "DSA",
    "OOD": "OOD", "OOP": "OOD", "OOPD": "OOD", "OBJECT ORIENTED DESIGN": "OOD",
    "APTI": "APTI", "APTITUDE": "APTI", "PROBLEM SOLVING": "APTI",
    "COMM": "COMM", "COMMUNICATION": "COMM", "COMMUNICATION SKILLS": "COMM",
    "AI": "AI", "ML": "AI", "AI NATIVE": "AI", "AI_NATIVE": "AI", "AI NATIVE ENGINEERING": "AI",
    "CLOUD": "CLOUD", "DEVOPS": "CLOUD", "DEVOPS AND CLOUD": "CLOUD", "DEVOPS_CLOUD": "CLOUD",
    "SQL": "SQL", "SQL_DESIGN": "SQL", "SQL & DESIGN": "SQL", "DATABASE": "SQL", "DBMS": "SQL",
    "SWE": "SWE", "SOFTWARE ENGINEERING": "SWE",
    "SYSD": "SYSD", "SYSTEM DESIGN": "SYSD", "SYSTEM_DESIGN": "SYSD",
    "NETW": "NETW", "NETWORKING": "NETW", "NETWORK": "NETW", "COMPUTER NETWORKING": "NETW",
    "OS": "OS", "OPERATING SYSTEM": "OS", "OPERATING SYSTEMS": "OS",
    "OTHER": "OTHER",
}
_CONFIDENCE = {"high": "high", "medium": "medium", "med": "medium", "low": "low"}


def normalise_category(value: Any) -> str:
    key = clean_text(value).upper().replace("-", " ")
    return _CODE_ALIASES.get(key, _CODE_ALIASES.get(key.replace(" ", "_"), "OTHER"))


@dataclass
class Unit:
    text: str                       # normalised (lower-case) text used for matching
    raw: str                        # original wording shown back to the user
    source: str                     # skill | skill_evidence | project | internship | hackathon |
                                    # certification | achievement | experience | summary
    confidence: Optional[str] = None
    tagged_category: Optional[str] = None


@dataclass
class NormalisedProfile:
    name: str = ""
    email: str = ""
    education: str = ""
    cgpa_ratio: Optional[float] = None
    preferred_roles: List[str] = field(default_factory=list)
    units: List[Unit] = field(default_factory=list)
    skill_count: int = 0
    warnings: List[str] = field(default_factory=list)


def _flatten(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, (str, int, float)):
        return clean_text(item)
    if isinstance(item, dict):
        return clean_text(" - ".join(clean_text(v) for v in item.values()
                                     if isinstance(v, (str, int, float)) and clean_text(v)))
    if isinstance(item, (list, tuple)):
        return clean_text(" ".join(_flatten(i) for i in item))
    return ""


def parse_cgpa(*texts: Any) -> Optional[float]:
    """'CGPA 8.6 / 10' -> 0.86 ; '82%' -> 0.82 ; 3.4/4 -> 0.85. None when absent/implausible."""
    for t in texts:
        if t is None:
            continue
        if isinstance(t, (int, float)) and not isinstance(t, bool):
            v = float(t)
            if 0 < v <= 10:
                return v / 10.0
            if 10 < v <= 100:
                return v / 100.0
            continue
        s = clean_text(t)
        m = re.search(r"(?:cgpa|gpa|cpi)\D{0,6}(\d+(?:\.\d+)?)\s*(?:/|out of)\s*(\d+(?:\.\d+)?)", s, re.I)
        if m:
            num, den = float(m.group(1)), float(m.group(2))
            if den > 0 and 0 < num <= den:
                return num / den
        m = re.search(r"(?:cgpa|gpa|cpi)\D{0,6}(\d+(?:\.\d+)?)", s, re.I)
        if m:
            v = float(m.group(1))
            if 0 < v <= 4.0:
                return v / 4.0
            if 4.0 < v <= 10:
                return v / 10.0
        m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%", s)
        if m and 0 < float(m.group(1)) <= 100:
            return float(m.group(1)) / 100.0
    return None


def _as_list(value: Any, field_name: str, warnings: List[str]) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        return [value]
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_ITEMS_PER_LIST:
            warnings.append(f"{field_name}: only the first {MAX_ITEMS_PER_LIST} items were read")
        return list(value)[:MAX_ITEMS_PER_LIST]
    warnings.append(f"{field_name}: unexpected type {type(value).__name__} - ignored")
    return []


def _kind_units(items: List[Any], source: str) -> List[Unit]:
    units: List[Unit] = []
    for item in items:
        text = _flatten(item)[:MAX_TEXT]
        for part in split_units(text) if len(text) > 160 else [text]:
            part = clean_text(part)
            if part:
                units.append(Unit(text=normalise_for_match(part), raw=part, source=source))
    return units


def _token_set(text: str) -> set:
    return set(re.findall(r"[a-z0-9+#]+", text))


def _overlaps(a: str, b: str) -> bool:
    """True when two units are essentially the same sentence (skill evidence quoting a project)."""
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.7


def load_profile_input(profile: Any) -> Dict[str, Any]:
    """Accept a dict, a JSON string, or a {'profile': {...}} wrapper."""
    if isinstance(profile, (str, bytes)):
        try:
            profile = json.loads(profile)
        except ValueError as exc:
            raise ProfileError(f"Profile is not valid JSON: {exc}")
    if not isinstance(profile, dict):
        raise ProfileError("Profile must be a JSON object")
    if "skills" not in profile and isinstance(profile.get("profile"), dict):
        profile = profile["profile"]
    return profile


def normalise_profile(profile: Any) -> NormalisedProfile:
    data = load_profile_input(profile)
    out = NormalisedProfile()
    w = out.warnings

    out.name = clean_text(data.get("name"))[:200]
    out.email = clean_text(data.get("email"))[:200]
    if not out.name:
        w.append("Profile has no name")
    edu = data.get("education")
    out.education = _flatten(edu)[:MAX_TEXT]
    out.cgpa_ratio = parse_cgpa(data.get("cgpa"), out.education)
    out.preferred_roles = [clean_text(r) for r in _as_list(data.get("preferred_roles"), "preferred_roles", w)
                           if clean_text(r)]

    raw_skills = data.get("skills")
    if raw_skills is None:
        raise ProfileError("Profile has no 'skills' field", details={"field": "skills"})
    if not isinstance(raw_skills, list):
        raise ProfileError("'skills' must be a list", details={"field": "skills"})
    if len(raw_skills) > MAX_SKILLS:
        w.append(f"skills: only the first {MAX_SKILLS} entries were read")
        raw_skills = raw_skills[:MAX_SKILLS]

    # Context units first, so skill evidence that merely quotes them can be merged away.
    context: List[Unit] = []
    for field_name, source in (("projects", "project"), ("internships", "internship"),
                               ("hackathons", "hackathon"), ("certifications", "certification"),
                               ("achievements", "achievement"), ("experience", "experience")):
        context.extend(_kind_units(_as_list(data.get(field_name), field_name, w), source))
    summary = clean_text(data.get("summary"))[:MAX_TEXT]
    if summary:
        context.extend(_kind_units([summary], "summary"))

    skills: Dict[str, Dict[str, Any]] = {}
    rank = {"low": 0, "medium": 1, "high": 2}
    for idx, entry in enumerate(raw_skills):
        if isinstance(entry, str):
            entry = {"skill_name": entry}
        if not isinstance(entry, dict):
            w.append(f"skills[{idx}] is not an object or string - ignored")
            continue
        name = clean_text(entry.get("skill_name") or entry.get("name") or entry.get("skill"))[:200]
        if not name:
            w.append(f"skills[{idx}] has no skill_name - ignored")
            continue
        cat = normalise_category(entry.get("category_code") or entry.get("category"))
        conf = _CONFIDENCE.get(clean_text(entry.get("confidence")).lower(), "medium")
        evidence = clean_text(entry.get("evidence"))[:MAX_TEXT]
        key = name.lower()
        cur = skills.get(key)
        if cur is None:
            skills[key] = {"name": name, "cat": cat, "conf": conf, "evidence": [evidence] if evidence else []}
        else:  # duplicate skill: keep the strongest confidence, merge evidence, keep a real category
            if rank[conf] > rank[cur["conf"]]:
                cur["conf"] = conf
            if cur["cat"] == "OTHER" and cat != "OTHER":
                cur["cat"] = cat
            if evidence and evidence not in cur["evidence"]:
                cur["evidence"].append(evidence)
            w.append(f"Duplicate skill '{name}' merged")

    out.skill_count = len(skills)
    units: List[Unit] = []
    for s in skills.values():
        tagged = s["cat"] if s["cat"] in CATEGORY_ORDER else None
        units.append(Unit(text=normalise_for_match(s["name"]), raw=s["name"], source="skill",
                          confidence=s["conf"], tagged_category=tagged))
        for ev in s["evidence"]:
            evn = normalise_for_match(ev)
            if any(_overlaps(evn, c.text) for c in context):
                # The evidence quotes a project/internship we already count: lend its confidence, don't double count.
                for c in context:
                    if _overlaps(evn, c.text) and c.confidence is None:
                        c.confidence = s["conf"]
                continue
            if any(_overlaps(evn, u.text) for u in units if u.source == "skill_evidence"):
                continue
            units.append(Unit(text=normalise_for_match(f"{s['name']} {ev}"), raw=ev, source="skill_evidence",
                              confidence=s["conf"], tagged_category=tagged))
    units.extend(context)
    out.units = units
    if not units:
        w.append("Profile contains no skills or evidence - every skillset will score 0")
    return out
