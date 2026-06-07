"""
Pure-Python extractive compressor for dag-thinking CCR pattern.
No ML dependencies — standard library only.
"""

import hashlib
import re
from typing import Optional, Tuple

IMPORTANCE_KEYWORDS = frozenset({
    "error", "critical", "key", "conclusion", "therefore",
    "must", "result", "finding", "risk", "assumption",
    "important", "required", "warning", "failure", "success",
    "evidence", "hypothesis", "objective", "synthesis", "action",
    "problem", "solution", "issue", "fix", "cause", "effect",
    "primary", "main", "core", "essential", "fundamental",
    "because", "since", "thus", "hence", "consequently",
})

# I06: thought_type별 가중 키워드 — ContentRouter 유사 압축 특화
# IMPORTANCE_KEYWORDS와 중복 없는 단어만 포함 (추가 정보량 확보)
_TYPE_KEYWORDS: dict[str, frozenset] = {
    "Objective":   frozenset({"goal", "aim", "target", "achieve", "scope", "purpose"}),
    "Hypothesis":  frozenset({"predict", "expect", "theory", "propose", "suggest", "might", "could"}),
    "Assumption":  frozenset({"assume", "given", "premise", "constraint", "presume", "baseline"}),
    "Evidence":    frozenset({"data", "shows", "measured", "observed", "metric", "found", "test"}),
    "Critique":    frozenset({"flaw", "weakness", "however", "counter", "limit", "gap", "challenge"}),
    "Synthesis":   frozenset({"conclude", "summary", "overall", "combine", "integrate", "reconcile"}),
    "Action":      frozenset({"implement", "deploy", "execute", "apply", "step", "plan", "proceed"}),
}

_PASSTHROUGH_LEN = 100       # real Claude payloads avg ~200 chars; was 280
_SAVINGS_THRESHOLD = 0.10    # skip if savings < 10%
_RATIO_TINY = 0.70           # 100–280 chars → keep 70%
_RATIO_SHORT = 0.58          # 280–700 chars → keep 58%
_RATIO_LONG = 0.42           # 700+ chars → keep 42%


# ---------------------------------------------------------------------------
# T06: ccr_hash — sha256 first 24 hex chars
# ---------------------------------------------------------------------------

def ccr_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


# ---------------------------------------------------------------------------
# T07: estimate_tokens — naive token count
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# T08: _is_list_content — detect bullet / numbered list
# ---------------------------------------------------------------------------

def _is_list_content(text: str) -> bool:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 3:
        return False
    list_lines = sum(
        1 for l in lines
        if re.match(r"^[-*•·]\s+", l) or re.match(r"^\d+[.)]\s+", l)
    )
    return list_lines / len(lines) >= 0.5


# ---------------------------------------------------------------------------
# T09: _score_sentence — keyword + position + length scoring
# ---------------------------------------------------------------------------

def _score_sentence(
    sentence: str,
    position: int,
    total: int,
    extra_keywords: frozenset = frozenset(),  # I06: thought_type별 추가 가중치
) -> float:
    words = re.findall(r"\b\w+\b", sentence.lower())
    keyword_hits = sum(1 for w in words if w in IMPORTANCE_KEYWORDS)
    extra_hits = sum(1 for w in words if w in extra_keywords)   # I06
    score = keyword_hits * 1.5 + extra_hits * 1.0               # I06

    # position bonus: first and last sentences are important
    if total > 1:
        if position == 0:
            score += 2.0
        elif position == total - 1:
            score += 1.0

    # length factor: prefer medium-length sentences (10–40 words)
    word_count = len(words)
    if 10 <= word_count <= 40:
        score += 0.5
    elif word_count < 5:
        score -= 0.5

    return score


# ---------------------------------------------------------------------------
# T10: _compress_list — importance-based top-K item sampling
# ---------------------------------------------------------------------------

def _compress_list(
    text: str,
    target_ratio: float,
    extra_keywords: frozenset = frozenset(),  # I06
) -> str:
    lines = [l for l in text.splitlines() if l.strip()]
    k = max(1, round(len(lines) * target_ratio))
    scored = [
        (_score_sentence(l, i, len(lines), extra_keywords), i, l)
        for i, l in enumerate(lines)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = sorted(scored[:k], key=lambda x: x[1])
    return "\n".join(item[2] for item in selected)


# ---------------------------------------------------------------------------
# T11: _compress_prose — sentence-level extractive compression
# ---------------------------------------------------------------------------

def _compress_prose(
    text: str,
    target_ratio: float,
    extra_keywords: frozenset = frozenset(),  # I06
) -> str:
    # Split into sentences preserving rough boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return text

    k = max(1, round(len(sentences) * target_ratio))
    scored = [
        (_score_sentence(s, i, len(sentences), extra_keywords), i, s)
        for i, s in enumerate(sentences)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = sorted(scored[:k], key=lambda x: x[1])
    return " ".join(item[2] for item in selected)


# ---------------------------------------------------------------------------
# T12: compress — main entry point
# ---------------------------------------------------------------------------

def compress(text: str, thought_type: Optional[str] = None) -> Tuple[str, str, int]:
    """
    Returns (compressed_text, ccr_hash_24char, tokens_saved).
    passthrough when: len < 100, or savings < 10%.
    thought_type: I06 — type-specific keywords boost relevant sentences.
    """
    hash_val = ccr_hash(text)

    if len(text) < _PASSTHROUGH_LEN:
        return text, hash_val, 0

    if len(text) >= 700:
        target_ratio = _RATIO_LONG
    elif len(text) >= 280:
        target_ratio = _RATIO_SHORT
    else:
        target_ratio = _RATIO_TINY

    # I06: thought_type별 추가 키워드 가중치
    extra_keywords = _TYPE_KEYWORDS.get(thought_type or "", frozenset())

    if _is_list_content(text):
        compressed = _compress_list(text, target_ratio, extra_keywords)
    else:
        compressed = _compress_prose(text, target_ratio, extra_keywords)

    original_tokens = estimate_tokens(text)
    compressed_tokens = estimate_tokens(compressed)
    tokens_saved = original_tokens - compressed_tokens

    # passthrough if savings < threshold
    if tokens_saved / original_tokens < _SAVINGS_THRESHOLD:
        return text, hash_val, 0

    return compressed, hash_val, tokens_saved
