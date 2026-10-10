"""Deterministic text signals (English + Thai) used by guardrail rules.

Kept separate from the rules so the lexicons can grow, and be tested, on their own.
Latin terms match on word boundaries; Thai terms match as substrings (Thai has no spaces).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from triage.models import Language


def _lexicon(*terms: str) -> re.Pattern[str]:
    parts = [re.escape(t) if _THAI_CHAR.search(t) else rf"\b{re.escape(t)}\b" for t in terms]
    return re.compile("|".join(parts), re.IGNORECASE)


_THAI_CHAR = re.compile(r"[\u0e00-\u0e7f]")
_LATIN_CHAR = re.compile(r"[a-zA-Z]")

CHARGEBACK = _lexicon(
    "chargeback",
    "charge back",
    "dispute",
    "disputing",
    "disputed",
    "credit card company",
    "แจ้งธนาคาร",
    "ร้องเรียนธนาคาร",
    "ปฏิเสธรายการ",
)
BILLING = _lexicon(
    "charge",
    "charges",
    "charged",
    "payment",
    "refund",
    "refunded",
    "invoice",
    "billing",
    "card",
    "subscription",
    "เรียกเก็บ",
    "ชำระเงิน",
    "คืนเงิน",
    "บัตรเครดิต",
    "ใบแจ้งหนี้",
)
OUTAGE = _lexicon(
    "error 500",
    "500 error",
    "outage",
    "is down",
    "site down",
    "can't access",
    "cannot access",
    "can't log in",
    "cannot log in",
    "not loading",
    "เข้าไม่ได้",
    "ระบบล่ม",
    "ใช้งานไม่ได้",
)
SECURITY = _lexicon(
    "hacked",
    "breach",
    "compromised",
    "unauthorized access",
    "unauthorised access",
    "data leak",
    "leaked",
    "phishing",
    "stolen account",
    "ถูกแฮก",
    "ข้อมูลรั่ว",
    "แฮก",
)
LEGAL = _lexicon(
    "lawyer",
    "attorney",
    "lawsuit",
    "sue",
    "legal action",
    "gdpr",
    "court",
    "ทนาย",
    "ฟ้อง",
    "ดำเนินคดี",
)
INJECTION = _lexicon(
    "ignore previous instructions",
    "ignore all previous",
    "ignore your instructions",
    "disregard previous",
    "disregard your instructions",
    "system prompt",
    "you are now",
    "developer mode",
    "ไม่ต้องสนใจคำสั่ง",
)
PROMISES = re.compile(
    "|".join(
        [
            r"\bwe(?:'ll| will| are going to| shall)\s+(?:\w+\s+){0,2}"
            r"(?:refund|reverse|reimburse|credit|compensate)",
            r"\byou(?:'ll| will)\s+(?:be|get)\s+(?:\w+\s+)?"
            r"(?:refunded|reimbursed|credited|compensated|a refund)",
            r"\b(?:refund|reversal|credit)s?\s+(?:has|have|is|are|will)\s+(?:been|being|be)\s+"
            r"(?:issued|processed|applied|approved)",
            r"\bguarantee[ds]?\b",
            r"\b(?:fixed|resolved|restored|back up|back online)\s+(?:by|within|in)\s+"
            r"(?:\d+|the next|tomorrow|today|tonight|end of)",
            r"\bwithin\s+\d+\s+(?:minutes?|hours?)\b",
            r"\bfree\s+(?:month|months|credit|upgrade)\b",
            r"คืนเงินให้",
            r"จะได้รับเงินคืน",
            r"ชดเชย",
            r"รับประกัน",
            r"ภายใน\s*\d+\s*(?:ชั่วโมง|นาที)",
        ]
    ),
    re.IGNORECASE,
)


def mentions(pattern: re.Pattern[str], text: str) -> bool:
    return pattern.search(text) is not None


def find_promises(text: str) -> list[str]:
    return [m.group(0) for m in PROMISES.finditer(text)]


def detect_language(texts: Iterable[str]) -> Language:
    """Script-based detection: good enough to tell Thai from English, honest otherwise."""
    joined = " ".join(texts)
    thai = len(_THAI_CHAR.findall(joined))
    latin = len(_LATIN_CHAR.findall(joined))
    letters = sum(1 for ch in joined if ch.isalpha())
    if letters == 0:
        return Language.OTHER
    if thai / letters >= 0.3:
        return Language.TH
    if latin / letters >= 0.7:
        return Language.EN
    return Language.OTHER
