"""
Pure-Python extractive compressor for dag-thinking CCR pattern.
No ML dependencies — standard library only.
"""

import hashlib
import re

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
    "Objective":  frozenset({"goal", "aim", "target", "achieve", "scope", "purpose"}),
    "Hypothesis": frozenset({
        "predict", "expect", "theory", "propose", "suggest", "might", "could",
    }),
    "Assumption": frozenset({"assume", "given", "premise", "constraint", "presume", "baseline"}),
    "Evidence":   frozenset({"data", "shows", "measured", "observed", "metric", "found", "test"}),
    "Critique":   frozenset({
        "flaw", "weakness", "however", "counter", "limit", "gap", "challenge",
    }),
    "Synthesis":  frozenset({
        "conclude", "summary", "overall", "combine", "integrate", "reconcile",
    }),
    "Action":     frozenset({"implement", "deploy", "execute", "apply", "step", "plan", "proceed"}),
}

_PASSTHROUGH_LEN = 100
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
    cjk_count = sum(
        1 for ch in text
        if ('㐀' <= ch <= '䶿'   # CJK Extension A
            or '一' <= ch <= '鿿'  # CJK Unified Ideographs
            or '\uF900' <= ch <= '\uFAFF'  # CJK Compatibility Ideographs (U+F900-U+FAFF)
            or '가' <= ch <= '힣'  # Hangul Syllables
            or '぀' <= ch <= 'ゟ'  # Hiragana
            or '゠' <= ch <= 'ヿ'  # Katakana
            or ord(ch) >= 0x20000)         # CJK Extension B/C/D/E/F/I (SMP)
    )
    non_cjk = len(text) - cjk_count
    return max(1, cjk_count * 2 + non_cjk // 4)


# ---------------------------------------------------------------------------
# T08: _is_list_content — detect bullet / numbered list
# ---------------------------------------------------------------------------

def _is_list_content(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 3:
        return False
    list_lines = sum(
        1 for line in lines
        if re.match(r"^[-*•]\s+", line) or re.match(r"^\d+[.)]\s+", line)
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

    # I24: CJK-aware length factor
    # \b\w+\b treats an entire CJK run as one "word", so word_count would be 1
    # for a 15-char Hangul sentence — underestimating length.
    # When the text is primarily CJK (>50% of chars), use CJK char count instead.
    cjk_char_count = sum(1 for ch in sentence if ord(ch) > 0x2E7F)
    primarily_cjk = cjk_char_count > len(sentence) * 0.5 if sentence else False
    word_count = cjk_char_count if primarily_cjk else len(words)
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
    lines = [item for item in text.splitlines() if item.strip()]
    k = max(1, round(len(lines) * target_ratio))
    scored = [
        (_score_sentence(item, i, len(lines), extra_keywords), i, item)
        for i, item in enumerate(lines)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = sorted(scored[:k], key=lambda x: x[1])
    return "\n".join(item[2] for item in selected)


# ---------------------------------------------------------------------------
# T11: _compress_prose — sentence-level extractive compression
# ---------------------------------------------------------------------------

_CJK_TERMINATORS: frozenset[str] = frozenset("。！？")


def _join_sentences(sentences: list[str]) -> str:
    """분리된 문장을 원문 언어 특성에 맞게 재결합.

    CJK 종결자(。！？)로 끝나는 문장 → 공백 없이 연결
    그 외(ASCII .!?) → 단일 공백으로 연결
    """
    if not sentences:
        return ""
    parts: list[str] = []
    for i, s in enumerate(sentences):
        parts.append(s)
        if i < len(sentences) - 1:
            if s and s[-1] in _CJK_TERMINATORS:
                pass  # CJK 종결 — 구분자 없음
            else:
                parts.append(" ")
    return "".join(parts)


def _split_sentences(text: str) -> list[str]:
    """텍스트를 문장 단위로 분리.

    ASCII (.!?): 종결자 뒤 공백(whitespace+) 기준 분리
    CJK (。！？): 공백 없이도 종결자 자체로 즉시 분리
    """
    sentences = re.split(r"(?<=[.!?])\s+|(?<=[。！？])", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _compress_prose(
    text: str,
    target_ratio: float,
    extra_keywords: frozenset = frozenset(),  # I06
) -> str:
    # I11: _split_sentences로 위임 — 유니코드 문장 구분자 지원
    sentences = _split_sentences(text)
    if not sentences:
        return text

    k = max(1, round(len(sentences) * target_ratio))
    scored = [
        (_score_sentence(s, i, len(sentences), extra_keywords), i, s)
        for i, s in enumerate(sentences)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = sorted(scored[:k], key=lambda x: x[1])
    return _join_sentences([item[2] for item in selected])


# ---------------------------------------------------------------------------
# T12: compress — main entry point
# ---------------------------------------------------------------------------

def compress(text: str, thought_type: str | None = None) -> tuple[str, str, int]:
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
