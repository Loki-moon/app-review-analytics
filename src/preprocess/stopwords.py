"""
불용어 제거 모듈 (PRD 31 4~5단계)

우선순위:
1. kostopwords 기본 사전 (있을 때만)
2. config/keywords.py STOPWORDS 도메인 사전
3. 전체 등장 빈도 2회 미만 토큰 제거 (remove_stopwords_batch)
"""
from __future__ import annotations

from collections import Counter

from config.keywords import STOPWORDS as _DEFAULT_STOPWORDS
from src.preprocess.token_filter import clean_token_lists

# kostopwords (선택)
try:
    from kostopwords import get_stopwords as _ks_get
    _KOST_SET: frozenset[str] = frozenset(w.lower() for w in _ks_get())
    KOSTOPWORDS_AVAILABLE = True
except Exception:
    _KOST_SET = frozenset()
    KOSTOPWORDS_AVAILABLE = False

_DOMAIN_SET: frozenset[str] = frozenset(w.lower() for w in _DEFAULT_STOPWORDS)

_DEFAULT_SET: frozenset[str] = _KOST_SET | _DOMAIN_SET


def remove_stopwords(
    tokens: list[str],
    extra_stopwords: set[str] | None = None,
) -> list[str]:
    """토큰 리스트에서 불용어 제거 (빈도 필터 없음)"""
    sw = _DEFAULT_SET
    if extra_stopwords:
        sw = sw | {w.lower() for w in extra_stopwords}
    return [t for t in tokens if t not in sw]


def remove_stopwords_batch(
    token_lists: list[list[str]],
    extra_stopwords: set[str] | None = None,
    min_freq: int = 1,
) -> list[list[str]]:
    """
    리뷰 리스트 일괄 처리

    1. 불용어 제거
    2. min_freq 미만 전체 등장 빈도 토큰 제거 (기본 2회)
    """
    sw = _DEFAULT_SET
    if extra_stopwords:
        sw = sw | {w.lower() for w in extra_stopwords}

    # 1차: 공통 토큰 검증 (숫자·특수문자·저품질 토큰 제거)
    filtered = clean_token_lists(token_lists)

    # 2차: 불용어 제거
    filtered = [[t for t in tl if t not in sw] for tl in filtered]

    # 3차: 전체 코퍼스 빈도 계산 후 min_freq 미만 제거
    if min_freq > 1:
        counter: Counter = Counter(t for tl in filtered for t in tl)
        rare = frozenset(t for t, cnt in counter.items() if cnt < min_freq)
        filtered = [[t for t in tl if t not in rare] for tl in filtered]

    return filtered
