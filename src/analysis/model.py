"""
로지스틱 회귀 분석 모듈

- 종속변수: sentiment_binary (4,5점=1 / 1,2점=0 / 3점 제외)
- 독립변수: 기능 키워드 더미
- 통제변수: review_length, 작성 월 더미, update_flag
- 반환: 기능 카테고리별 OR, 95% CI, p-value
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.tools.sm_exceptions import PerfectSeparationError

from config.settings import NEGATIVE_THRESHOLD, POSITIVE_THRESHOLD


def binarize_sentiment(scores: pd.Series) -> pd.Series:
    """평점 → 이진 감성 변수 (3점 제외 → NaN)"""
    result = pd.Series(np.nan, index=scores.index)
    result[scores >= POSITIVE_THRESHOLD] = 1.0
    result[scores <= NEGATIVE_THRESHOLD] = 0.0
    return result


def build_regression_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    분석용 데이터프레임 구성
    - sentiment_binary 생성
    - review_length 생성
    - month_dummy 생성
    - update_flag 확인
    """
    out = df.copy()

    # 종속변수
    out["sentiment_binary"] = binarize_sentiment(out["score"])
    out = out.dropna(subset=["sentiment_binary"])

    # 리뷰 길이 (통제)
    if "content_clean" in out.columns:
        out["review_length"] = out["content_clean"].str.len().fillna(0)
    elif "content" in out.columns:
        out["review_length"] = out["content"].str.len().fillna(0)
    else:
        out["review_length"] = 0

    # 작성 월 (통제) - review_date 컬럼 활용
    if "review_date" in out.columns:
        try:
            out["review_month"] = pd.to_datetime(out["review_date"]).dt.month
        except Exception:
            out["review_month"] = 1
    else:
        out["review_month"] = 1

    # update_flag (없으면 0)
    if "update_flag" not in out.columns:
        out["update_flag"] = 0
    out["update_flag"] = out["update_flag"].fillna(0).astype(int)

    return out


def run_logistic_regression(
    df: pd.DataFrame,
    feature_cols: list[str],
) -> pd.DataFrame:
    """
    기능 카테고리별 로지스틱 회귀 수행.

    각 feature_col 에 대해 단변량 회귀(+ 통제변수)를 수행하고
    OR, CI, p-value를 반환한다.

    Returns:
        DataFrame with columns:
            feature_category, beta, OR, ci_lower, ci_upper, p_value, n_reviews, n_positive
    """
    results = []

    # 통제변수 컬럼 (있는 것만)
    control_vars = []
    for col in ["review_length", "update_flag"]:
        if col in df.columns:
            control_vars.append(col)

    for col in feature_cols:
        cat_name = col.replace("keyword_", "")

        sub = df[[col, "sentiment_binary"] + control_vars].dropna()
        if len(sub) < 30:
            continue
        if sub[col].sum() < 5:
            continue
        if sub["sentiment_binary"].nunique() < 2:
            continue

        # 공식 구성
        ctrl_str = " + ".join(control_vars) if control_vars else ""
        formula = f"sentiment_binary ~ {col}"
        if ctrl_str:
            formula += f" + {ctrl_str}"

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = smf.logit(formula, data=sub).fit(disp=False, maxiter=200)

            coef = model.params[col]
            pval = model.pvalues[col]
            ci   = model.conf_int().loc[col]

            results.append({
                "feature_category": cat_name,
                "beta": round(coef, 4),
                "OR": round(np.exp(coef), 4),
                "ci_lower": round(np.exp(ci[0]), 4),
                "ci_upper": round(np.exp(ci[1]), 4),
                "p_value": round(pval, 4),
                "n_reviews": len(sub),
                "n_positive": int(sub["sentiment_binary"].sum()),
            })

        except (PerfectSeparationError, Exception):
            continue

    return pd.DataFrame(results)
