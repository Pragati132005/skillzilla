"""Small, dependency-free text helpers shared by every module."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, List

_MOJIBAKE_MARKERS = ("â€", "Ã", "Â", "â\x80")


def fix_mojibake(text: str) -> str:
    """Repair UTF-8 text that was decoded as cp1252 (e.g. 'Byjuâ€™s' -> 'Byju’s')."""
    if not any(m in text for m in _MOJIBAKE_MARKERS):
        return text
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def clean_text(value: Any) -> str:
    """Coerce anything to a tidy single-spaced string ('' for None / NaN-like)."""
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    text = fix_mojibake(str(value))
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


_DASHES = re.compile(r"[\u2010-\u2015\u2212]")


def normalise_for_match(text: str) -> str:
    """Lower-case, unify dashes/quotes and collapse whitespace for regex matching."""
    text = clean_text(text).lower()
    text = _DASHES.sub("-", text)
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    return text


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\s*[\n\r•·▪●]+\s*|\s;\s")


def split_units(text: str) -> List[str]:
    """Split a block of resume text into sentence/bullet sized units."""
    if not text:
        return []
    parts = [p.strip(" -–—\t") for p in _SENT_SPLIT.split(text)]
    return [p for p in parts if p]


_SUFFIXES = ("ization", "isation", "ations", "ation", "ments", "ment", "ities", "ity", "ings", "ing",
             "ness", "ies", "ied", "ers", "er", "ed", "es", "s", "ly")


def stem(token: str) -> str:
    """Very light stemmer - good enough for matching rubric topics to prose."""
    if len(token) <= 4:
        return token
    for suf in _SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            token = token[: -len(suf)]
            break
    return token


_STOP = {
    "a", "an", "and", "or", "the", "of", "to", "in", "on", "for", "with", "vs", "using", "use", "via",
    "basic", "basics", "introduction", "intro", "fundamentals", "fundamental", "concepts", "concept",
    "understanding", "overview", "usage", "based", "level", "advanced", "strategies", "techniques",
    "practices", "best", "principles", "design", "large", "scale", "system", "systems", "skills",
}


def content_tokens(text: str) -> List[str]:
    toks = re.findall(r"[a-z0-9+#]+", normalise_for_match(text))
    return [stem(t) for t in toks if t not in _STOP and len(t) > 1]


def clip(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def round_half_up(value: float) -> int:
    """Banker's rounding would make 2.5 -> 2 but 3.5 -> 4; levels need predictable half-up."""
    return int(value + 0.5) if value >= 0 else 0
