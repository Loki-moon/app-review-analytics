"""
텍스트 정규화 모듈

수행 작업:
- 줄바꿈 제거
- 이모지 제거 (옵션)
- 특수문자 최소화
- 반복 문자 정리 (ㅋㅋㅋㅋ → ㅋㅋ 등)
- HTML 엔티티 제거
- 영문 소문자 통일
"""
from __future__ import annotations

import re
import unicodedata


_EMOJI_RE = re.compile(
    "["
    "\U00010000-\U0010FFFF"   # 보조 다국어 평면 (rare emoji)
    "\U0001F300-\U0001F9FF"   # 이모지 기호
    "\U00002702-\U000027B0"   # Dingbats
    "]+",
    flags=re.UNICODE,
)

_REPEAT_RE = re.compile(r"(.)\1{2,}")          # 3회 이상 연속 → 2회로
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_ENTITY_RE = re.compile(r"&[a-zA-Z]+;|&#\d+;")
_SPECIAL_RE = re.compile(r"[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ.,!?%]")  # 허용 문자 외 제거
_WHITESPACE_RE = re.compile(r"\s+")


def normalize(text: str, remove_emoji: bool = True) -> str:
    """단일 텍스트 정규화"""
    if not isinstance(text, str) or not text.strip():
        return ""

    # HTML 태그·엔티티 제거
    text = _HTML_TAG_RE.sub(" ", text)
    text = _HTML_ENTITY_RE.sub(" ", text)

    # 줄바꿈·탭을 공백으로
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")

    # 이모지 제거
    if remove_emoji:
        text = _EMOJI_RE.sub(" ", text)

    # 유니코드 정규화 (NFKC)
    text = unicodedata.normalize("NFKC", text)

    # 영문 소문자
    text = text.lower()

    # 반복 문자 정리
    text = _REPEAT_RE.sub(r"\1\1", text)

    # 특수문자 제거 (한글·영문·숫자·기본 구두점 유지)
    text = _SPECIAL_RE.sub(" ", text)

    # 공백 정리
    text = _WHITESPACE_RE.sub(" ", text).strip()

    return text


def normalize_series(texts, remove_emoji: bool = True):
    """pandas Series 또는 리스트에 일괄 적용"""
    return [normalize(t, remove_emoji=remove_emoji) for t in texts]
