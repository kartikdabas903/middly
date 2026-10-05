"""Reusable normalization helpers for connector authors.

Source systems disagree on date formats, name casing, state codes, gender codes
and phone formats. Connectors use these helpers to map source values onto the
canonical vocabulary; the core still validates everything they return.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timezone
from difflib import SequenceMatcher

STATE_CODES = {
    "MH": "Maharashtra", "MP": "Madhya Pradesh", "GJ": "Gujarat", "KA": "Karnataka", "GA": "Goa",
    "TS": "Telangana", "TG": "Telangana", "CG": "Chhattisgarh", "DL": "Delhi", "UP": "Uttar Pradesh",
    "RJ": "Rajasthan", "TN": "Tamil Nadu", "KL": "Kerala", "WB": "West Bengal", "BR": "Bihar",
}

GENDER_CODES = {"M": "MALE", "MALE": "MALE", "F": "FEMALE", "FEMALE": "FEMALE", "O": "OTHER", "OTHER": "OTHER", "T": "OTHER"}

# Ordered education levels used by eligibility rules.
QUALIFICATION_LEVELS = ["NONE", "CLASS_8", "CLASS_10", "CLASS_12", "ITI", "DIPLOMA", "GRADUATE", "POSTGRADUATE", "DOCTORATE"]

_QUALIFICATION_ALIASES = {
    "SSC": "CLASS_10", "10TH": "CLASS_10", "MATRICULATION": "CLASS_10", "CLASS X": "CLASS_10",
    "HSC": "CLASS_12", "12TH": "CLASS_12", "INTERMEDIATE": "CLASS_12", "CLASS XII": "CLASS_12",
    "ITI": "ITI", "DIPLOMA": "DIPLOMA", "POLYTECHNIC DIPLOMA": "DIPLOMA",
    "B.TECH": "GRADUATE", "BTECH": "GRADUATE", "B.E.": "GRADUATE", "BE": "GRADUATE", "B.SC": "GRADUATE",
    "BSC": "GRADUATE", "B.COM": "GRADUATE", "BCOM": "GRADUATE", "BA": "GRADUATE", "B.A.": "GRADUATE", "BCA": "GRADUATE",
    "M.TECH": "POSTGRADUATE", "MTECH": "POSTGRADUATE", "M.SC": "POSTGRADUATE", "MBA": "POSTGRADUATE",
    "M.COM": "POSTGRADUATE", "MA": "POSTGRADUATE", "MCA": "POSTGRADUATE", "PHD": "DOCTORATE", "PH.D": "DOCTORATE",
}

EMPLOYMENT_STATUS_ALIASES = {
    "UNEMPLOYED": "UNEMPLOYED", "UNEMP": "UNEMPLOYED", "JOB_SEEKER": "UNEMPLOYED", "SEEKING": "UNEMPLOYED",
    "EMPLOYED": "EMPLOYED", "EMP": "EMPLOYED", "SALARIED": "EMPLOYED",
    "SELF_EMPLOYED": "SELF_EMPLOYED", "SELF": "SELF_EMPLOYED", "SELF-EMPLOYED": "SELF_EMPLOYED",
    "STUDENT": "STUDENT",
}

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y", "%Y%m%d")


def parse_date(value, formats: tuple[str, ...] = _DATE_FORMATS) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {text!r}")


def parse_datetime(value) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        d = parse_date(text)
        dt = datetime(d.year, d.month, d.day)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def clean_text(value) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_name(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return " ".join(part.capitalize() if part.isupper() or part.islower() else part for part in text.split(" "))


def name_key(value: str | None) -> str:
    """Comparison key: lowercase, letters only, honorifics removed."""
    if not value:
        return ""
    text = re.sub(r"[^a-z ]", " ", value.lower())
    tokens = [t for t in text.split() if t not in {"mr", "mrs", "ms", "shri", "smt", "kumari", "dr"}]
    return " ".join(tokens)


def name_similarity(a: str | None, b: str | None) -> float:
    ka, kb = name_key(a), name_key(b)
    if not ka or not kb:
        return 0.0
    return SequenceMatcher(None, ka, kb).ratio()


def names_compatible(a: str | None, b: str | None) -> bool:
    """True when one name is the other plus/minus middle names (e.g. 'Priya Deshmukh' vs 'Priya Sunil Deshmukh')."""
    ta, tb = set(name_key(a).split()), set(name_key(b).split())
    if not ta or not tb:
        return False
    return ta.issubset(tb) or tb.issubset(ta)


def normalize_state(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return STATE_CODES.get(text.upper(), text.title())


def normalize_gender(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return GENDER_CODES.get(text.upper())


def normalize_mobile(value) -> str | None:
    if value in (None, ""):
        return None
    digits = re.sub(r"\D", "", str(value))
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits


def is_valid_mobile(digits: str | None) -> bool:
    return bool(digits) and re.fullmatch(r"[6-9]\d{9}", digits) is not None


def mask_mobile(digits: str | None) -> str | None:
    if not digits:
        return None
    return "X" * max(0, len(digits) - 4) + digits[-4:]


def qualification_level(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return _QUALIFICATION_ALIASES.get(text.upper(), None)


def level_rank(level: str | None) -> int:
    try:
        return QUALIFICATION_LEVELS.index(level) if level else -1
    except ValueError:
        return -1


def normalize_employment_status(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    return EMPLOYMENT_STATUS_ALIASES.get(text.upper().replace(" ", "_"))
