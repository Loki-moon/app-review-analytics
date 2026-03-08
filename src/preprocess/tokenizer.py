"""
형태소 분석 + 토큰 정제

kiwipiepy 0.22+ API:
  kiwi.analyze(text) → [(token_list, score), ...]
  최상위 후보 = result[0][0]  (token_list)
  Token.tag 은 'NNG' 같은 문자열

추출 POS:
  NNG (일반명사), NNP (고유명사)  — 한국어 명사 2음절+
  VA  (형용사 어간)               — 불편, 느리, 나쁘 등 2음절+
  VV  (동사 어간)                 — 튕기, 연결 등 2음절+
  XR  (어근)                      — 합성어 어근 2음절+
  SL  (외래어·영어)               — 2글자 이상
"""
from __future__ import annotations

import re

_kiwi = None


def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return _kiwi


_HAN_RE = re.compile(r'^[가-힣]+$')
_TARGET_POS = {"NNG", "NNP", "VA", "VV", "XR", "SL"}


def tokenize(text: str) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []

    kiwi = _get_kiwi()
    tokens: list[str] = []

    try:
        # 0.22+: result[0] = (token_list, score)
        result = kiwi.analyze(text)
        token_list = result[0][0]

        for tok in token_list:
            form = tok.form.lower()
            tag  = str(tok.tag)      # 이미 'NNG' 같은 문자열
            base = tag[:2]

            if tag not in _TARGET_POS and base not in _TARGET_POS:
                continue

            if tag == "SL":
                if len(form) >= 2:
                    tokens.append(form)
                continue

            # 한글 형태소만 통과시키고, 최소 길이 조건 적용
            if _HAN_RE.fullmatch(form) and len(form) >= 2:
                tokens.append(form)

    except Exception:
        # kiwipiepy 실패 시 공백 분리 fallback
        tokens = [w.lower() for w in text.split() if len(w) >= 2]

    return tokens


def tokenize_series(texts) -> list[list[str]]:
    return [tokenize(t) for t in texts]
