"""
키워드 분석 모듈

- 빈도 분석
- TF-IDF 상위 키워드 도출
- 기능 카테고리 더미 변수 생성
"""
from __future__ import annotations

from collections import Counter

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from config.keywords import FEATURE_CATEGORIES
from config.settings import TOP_KEYWORDS_N
from src.preprocess.token_filter import clean_token_lists


def build_freq_table(token_lists: list[list[str]], top_n: int = TOP_KEYWORDS_N) -> pd.DataFrame:
    """전체 토큰 빈도 테이블 반환"""
    token_lists = clean_token_lists(token_lists)
    counter: Counter = Counter()
    for tl in token_lists:
        counter.update(tl)

    rows = [{"keyword": kw, "count": cnt} for kw, cnt in counter.most_common(top_n)]
    return pd.DataFrame(rows)


def build_tfidf_keywords(
    token_lists: list[list[str]],
    top_n: int = TOP_KEYWORDS_N,
) -> pd.DataFrame:
    """TF-IDF 기반 상위 키워드 반환"""
    token_lists = clean_token_lists(token_lists)
    docs = [" ".join(tl) for tl in token_lists]
    non_empty = [d for d in docs if d.strip()]
    if not non_empty:
        return pd.DataFrame(columns=["keyword", "tfidf_score"])

    vectorizer = TfidfVectorizer(max_features=top_n * 3, min_df=2)
    try:
        tfidf_matrix = vectorizer.fit_transform(non_empty)
    except ValueError:
        return pd.DataFrame(columns=["keyword", "tfidf_score"])

    scores = tfidf_matrix.mean(axis=0).A1
    feature_names = vectorizer.get_feature_names_out()
    scored = sorted(zip(feature_names, scores), key=lambda x: x[1], reverse=True)

    rows = [{"keyword": kw, "tfidf_score": round(sc, 4)} for kw, sc in scored[:top_n]]
    return pd.DataFrame(rows)


def map_feature_categories(token_lists: list[list[str]]) -> pd.DataFrame:
    """
    각 리뷰에 대해 기능 카테고리 등장 여부를 0/1 더미 변수로 반환.

    Returns:
        DataFrame, index = 리뷰 순번,
        columns = "keyword_{카테고리명}" 형태
    """
    token_lists = clean_token_lists(token_lists)
    # 카테고리별 키워드 집합 (소문자)
    cat_kw: dict[str, set[str]] = {
        cat: {kw.lower() for kw in kws}
        for cat, kws in FEATURE_CATEGORIES.items()
    }

    records = []
    for tl in token_lists:
        token_set = set(tl)
        row: dict[str, int] = {}
        for cat, kw_set in cat_kw.items():
            row[f"keyword_{cat}"] = int(bool(token_set & kw_set))
        records.append(row)

    return pd.DataFrame(records)


def get_category_columns(df: pd.DataFrame) -> list[str]:
    """DataFrame에서 keyword_* 컬럼 이름 반환"""
    return [c for c in df.columns if c.startswith("keyword_")]
