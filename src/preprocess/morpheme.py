"""
형태소 분석 모듈 (kiwipiepy)

- 명사(NNG, NNP), 핵심 동사(VV 원형), 형용사(VA 원형) 추출
- 영어 단어(SL) 소문자 보존
- 2글자 이상 토큰만 반환 (단, 영어는 1글자 이상)
"""
from __future__ import annotations

from functools import lru_cache

_kiwi = None  # 지연 초기화 (앱 시작 시 로딩 비용 최소화)

def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return _kiwi


# 추출 대상 품사 태그
_TARGET_POS = {
    "NNG",   # 일반명사
    "NNP",   # 고유명사
    "VV",    # 동사
    "VA",    # 형용사
    "SL",    # 외래어(영어 포함)
    "XR",    # 어근
}


def tokenize(text: str) -> list[str]:
    """텍스트 → 토큰 리스트 (형태소 분석)"""
    if not text or not text.strip():
        return []

    kiwi = _get_kiwi()
    tokens: list[str] = []

    try:
        result = kiwi.analyze(text)
        if not result:
            return []

        morphs = result[0].tokens  # 최고 확률 분석 결과

        for token in morphs:
            form = token.form
            tag  = token.tag.name if hasattr(token.tag, "name") else str(token.tag)

            # 품사 필터
            base_tag = tag[:2] if len(tag) >= 2 else tag
            if base_tag not in _TARGET_POS and tag not in _TARGET_POS:
                continue

            # 길이 필터
            if tag == "SL" and len(form) < 1:
                continue
            if tag != "SL" and len(form) < 2:
                continue

            # 소문자 변환
            tokens.append(form.lower())

    except Exception:
        # 분석 실패 시 공백 분리로 fallback
        tokens = [w.lower() for w in text.split() if len(w) >= 2]

    return tokens


def tokenize_series(texts) -> list[list[str]]:
    """리스트/Series 일괄 형태소 분석"""
    return [tokenize(t) for t in texts]
