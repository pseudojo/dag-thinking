"""
Pure-Python extractive compressor for dag-thinking CCR pattern.
No ML dependencies — standard library only.
"""

import hashlib
import re

IMPORTANCE_KEYWORDS = frozenset(
    {
        "error",
        "critical",
        "key",
        "conclusion",
        "therefore",
        "must",
        "result",
        "finding",
        "risk",
        "assumption",
        "important",
        "required",
        "warning",
        "failure",
        "success",
        "evidence",
        "hypothesis",
        "objective",
        "synthesis",
        "action",
        "problem",
        "solution",
        "issue",
        "fix",
        "cause",
        "effect",
        "primary",
        "main",
        "core",
        "essential",
        "fundamental",
        "because",
        "since",
        "thus",
        "hence",
        "consequently",
    }
)

# IMPORTANCE_KEYWORDS와 중복 없는 단어만 포함 (추가 정보량 확보)
_TYPE_KEYWORDS: dict[str, frozenset] = {
    "Objective": frozenset({"goal", "aim", "target", "achieve", "scope", "purpose"}),
    "Hypothesis": frozenset(
        {
            "predict",
            "expect",
            "theory",
            "propose",
            "suggest",
            "might",
            "could",
        }
    ),
    "Assumption": frozenset({"assume", "given", "premise", "constraint", "presume", "baseline"}),
    "Evidence": frozenset({"data", "shows", "measured", "observed", "metric", "found", "test"}),
    "Critique": frozenset(
        {
            "flaw",
            "weakness",
            "however",
            "counter",
            "limit",
            "gap",
            "challenge",
        }
    ),
    "Synthesis": frozenset(
        {
            "conclude",
            "summary",
            "overall",
            "combine",
            "integrate",
            "reconcile",
        }
    ),
    "Action": frozenset({"implement", "deploy", "execute", "apply", "step", "plan", "proceed"}),
}

_PASSTHROUGH_LEN = 100
_SAVINGS_THRESHOLD = 0.10
_RATIO_TINY = 0.70  # 100–280 chars → keep 70%
_RATIO_SHORT = 0.58  # 280–700 chars → keep 58%
_RATIO_LONG = 0.42  # 700+ chars → keep 42%


def ccr_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def _is_cjk_char(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x3400 <= cp <= 0x4DBF  # CJK Extension A
        or 0x4E00 <= cp <= 0x9FFF  # CJK Unified Ideographs
        or 0xF900 <= cp <= 0xFAFF  # CJK Compatibility Ideographs
        or 0xAC00 <= cp <= 0xD7A3  # Hangul Syllables
        or 0x3040 <= cp <= 0x309F  # Hiragana
        or 0x30A0 <= cp <= 0x30FF  # Katakana
        or cp >= 0x20000  # CJK Extension B/C/D/E/F/I (SMP)
    )


def estimate_tokens(text: str) -> int:
    cjk_count = sum(1 for ch in text if _is_cjk_char(ch))
    non_cjk = len(text) - cjk_count
    return max(1, cjk_count * 2 + non_cjk // 4)


def _is_list_content(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 3:
        return False
    list_lines = sum(
        1 for line in lines if re.match(r"^[+\-*•]\s+", line) or re.match(r"^\d+[.)]\s+", line)
    )
    return list_lines / len(lines) >= 0.5


def _score_sentence(
    sentence: str,
    position: int,
    total: int,
    extra_keywords: frozenset = frozenset(),
) -> float:
    words = re.findall(r"\b\w+\b", sentence.lower())
    keyword_hits = sum(1 for w in words if w in IMPORTANCE_KEYWORDS)
    extra_hits = sum(1 for w in words if w in extra_keywords)
    score = keyword_hits * 1.5 + extra_hits * 1.0

    if total > 1:
        if position == 0:
            score += 2.0
        elif position == total - 1:
            score += 1.0

    # \b\w+\b collapses an entire CJK run to one "word" — use char count instead
    cjk_char_count = sum(1 for ch in sentence if _is_cjk_char(ch))
    primarily_cjk = cjk_char_count > len(sentence) * 0.5 if sentence else False
    word_count = cjk_char_count if primarily_cjk else len(words)
    if 10 <= word_count <= 40:
        score += 0.5
    elif word_count < 5:
        score -= 0.5

    return score


def _select_top_k(
    units: list[str],
    target_ratio: float,
    extra_keywords: frozenset = frozenset(),
) -> list[str]:
    """중요도 상위 k개 단위를 선택해 원문 순서로 복원.

    floor_k=min(2, n): 다중 단위는 최소 2개 보존 — 1개로 과잉 압축 방지.
    """
    floor_k = min(2, len(units))
    k = max(floor_k, round(len(units) * target_ratio))
    scored = [
        (_score_sentence(u, i, len(units), extra_keywords), i, u) for i, u in enumerate(units)
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [u for _, _, u in sorted(scored[:k], key=lambda x: x[1])]


def _compress_list(
    text: str,
    target_ratio: float,
    extra_keywords: frozenset = frozenset(),
) -> str:
    lines = [item for item in text.splitlines() if item.strip()]
    return "\n".join(_select_top_k(lines, target_ratio, extra_keywords))


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

    ASCII (.!?): 소문자 3글자 이상 뒤 단일 종결자 + 공백 → 문장 경계
                 약어(Dr., e.g., vs., Fig.) — 앞에 대문자·공백·점이 있어 3-소문자 조건 불충족
                 연속 종결자(줄임표 `...`) — 내부 점이 소문자가 아니라 불매치
    복합 종결자: ?!/!!/??  등 두 글자 종결자 뒤 공백도 경계 인식
    CJK (。！？): 공백 없이도 종결자 자체로 즉시 분리

    re.sub 마킹 방식 — Python re 고정폭 룩비하인드 제약(대안 길이 동일 요구) 우회
    """
    t = text.strip()
    if not t:
        return []
    _M = ""  # Unicode PUA — 일반 텍스트에서 사용 불가능한 코드포인트
    t = re.sub(r"(?<=[。！？])", _M, t)  # CJK 즉시 분리
    t = re.sub(r"([!?]{2})\s+", r"\1" + _M, t)  # 복합 종결자 먼저
    t = re.sub(r"([a-z][!?])\s+", r"\1" + _M, t)  # !? 단일: 소문자 1개 충분
    t = re.sub(r"([a-z][a-z][a-z]\.)\s+", r"\1" + _M, t)  # . 소문자 3개+ (약어 방지)
    t = re.sub(r"([A-Z]{2,}\.)\s+", r"\1" + _M, t)  # . 대문자 약어: RPS./API.
    return [s.strip() for s in t.split(_M) if s.strip()]


def _compress_prose(
    text: str,
    target_ratio: float,
    extra_keywords: frozenset = frozenset(),
) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return text
    return _join_sentences(_select_top_k(sentences, target_ratio, extra_keywords))


def compress(text: str, thought_type: str | None = None) -> tuple[str, str, int]:
    """
    Returns (compressed_text, ccr_hash_24char, tokens_saved).
    passthrough when: len < 100, or savings < 10%.
    thought_type: type-specific keywords boost relevant sentences.
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

    extra_keywords = _TYPE_KEYWORDS.get(thought_type or "", frozenset())

    if _is_list_content(text):
        compressed = _compress_list(text, target_ratio, extra_keywords)
    else:
        compressed = _compress_prose(text, target_ratio, extra_keywords)

    original_tokens = estimate_tokens(text)
    compressed_tokens = estimate_tokens(compressed)
    tokens_saved = original_tokens - compressed_tokens

    if tokens_saved / original_tokens < _SAVINGS_THRESHOLD:
        return text, hash_val, 0

    return compressed, hash_val, tokens_saved
