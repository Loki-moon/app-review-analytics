"""
공통 토큰 검증 모듈

모든 키워드 분석 함수(build_freq_table, build_tfidf_keywords,
map_feature_categories)와 불용어 제거 파이프라인이 동일 규칙을 공유한다.
"""
from __future__ import annotations

import logging
import re

from config.keywords import ENGLISH_ALLOWLIST

logger = logging.getLogger(__name__)

# ── 정규식 ────────────────────────────────────────────────────────────────────
_HAN_RE          = re.compile(r'^[가-힣]+$')
_ENG_ONLY_RE     = re.compile(r'^[a-zA-Z]+$')
_VERSION_RE      = re.compile(r'^v?\d+[\.\d]*[a-zA-Z]?$', re.I)   # v2, 8.0, 1.0.3
_NUMBERED_RE     = re.compile(r'^\d+[\.\)]+$')                      # 1.  2)
_URL_RE          = re.compile(r'https?://|www\.|\.com|\.kr|\.net|\.org', re.I)
_HTML_RE         = re.compile(r'<[^>]+>|&[a-z]+;', re.I)
# 단일 문자(영문/숫자) + 숫자 조합: a1, 1a, b23 (5g 는 allowlist 에서 처리)
_JUNK_MIXED_RE   = re.compile(r'^[a-zA-Z]\d+$|^\d+[a-zA-Z]$')

_ALLOWLIST: frozenset[str] = frozenset(w.lower() for w in ENGLISH_ALLOWLIST)


# ── 핵심 검증 함수 ─────────────────────────────────────────────────────────────

def is_valid_token(token: str) -> bool:
    """
    True  → 유효한 토큰
    False → 제거 대상

    검사 순서
    1. allowlist 우선 통과
    2. 한글/영문 문자가 전혀 없으면 제거 (순수 숫자·특수문자·반복부호)
    3. 버전형 토큰 제거
    4. 번호형 토큰 제거
    5. URL/HTML 제거
    6. 1글자 영어 제거
    7. 저품질 영숫자 혼합 제거
    8. 1글자 한글 제거
    """
    t = token.strip().lower()
    if not t:
        return False

    # 1. allowlist — 항상 통과
    if t in _ALLOWLIST:
        return True

    # 2. 한글/영문 없음 → 숫자·특수문자·반복부호 → 제거
    if not re.search(r'[가-힣a-zA-Z]', t):
        return False

    # 3. 버전형: v2, 8.0, 1.0.3
    if _VERSION_RE.fullmatch(t):
        return False

    # 4. 번호형: 1. 2)
    if _NUMBERED_RE.fullmatch(t):
        return False

    # 5. URL/HTML 조각
    if _URL_RE.search(t) or _HTML_RE.search(t):
        return False

    # 6. 1글자 영어
    if _ENG_ONLY_RE.fullmatch(t) and len(t) == 1:
        return False

    # 7. 저품질 영숫자 혼합: a1, 1a, b23 등
    if _JUNK_MIXED_RE.fullmatch(t):
        return False

    # 8. 1글자 한글
    if _HAN_RE.fullmatch(t) and len(t) == 1:
        return False

    return True


def clean_token_list(tokens: list[str]) -> list[str]:
    kept, dropped = [], []
    for t in tokens:
        if is_valid_token(t):
            kept.append(t)
        else:
            dropped.append(t)
    if dropped:
        logger.debug("dropped tokens: %s", dropped)
    return kept


def clean_token_lists(token_lists: list[list[str]]) -> list[list[str]]:
    return [clean_token_list(tl) for tl in token_lists]
