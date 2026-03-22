"""
로지스틱 회귀 분석 모듈

- 종속변수: sentiment_binary (4,5점=1 / 1,2점=0 / 3점 제외)
- 독립변수: 기능 키워드 더미
- 통제변수: review_length, 작성 월 더미, update_flag
- 반환: 기능 카테고리별 OR, 95% CI, p-value

분석 방법 선택:
- 기능 언급 리뷰 >= 10건 → 로지스틱 회귀 (통제변수 포함)
- 기능 언급 리뷰 2~9건  → 피셔 정확검정 (소표본 대응, Haldane 보정)
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import fisher_exact
from statsmodels.tools.sm_exceptions import PerfectSeparationError

from config.settings import NEGATIVE_THRESHOLD, POSITIVE_THRESHOLD

# 로지스틱 회귀 vs 피셔 정확검정 기준 언급 수
_LOGIT_MIN_MENTIONS = 10
_FISHER_MIN_MENTIONS = 2


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


def _fisher_or(sub: pd.DataFrame, col: str) -> dict | None:
    """
    피셔 정확검정으로 OR, 95% CI, p-value 계산.

    2×2 분할표:
               긍정(1)  부정(0)
    언급(1)      a        b
    미언급(0)    c        d

    Haldane 보정: 빈 셀에 0.5 추가.
    """
    mentioned = sub[sub[col] == 1]["sentiment_binary"]
    not_mentioned = sub[sub[col] == 0]["sentiment_binary"]

    if mentioned.empty or not_mentioned.empty:
        return None

    a = int((mentioned == 1).sum())      # 언급 & 긍정
    b = int((mentioned == 0).sum())      # 언급 & 부정
    c = int((not_mentioned == 1).sum())  # 미언급 & 긍정
    d = int((not_mentioned == 0).sum())  # 미언급 & 부정

    # 피셔 정확검정 (p-value)
    _, pval = fisher_exact([[a, b], [c, d]])

    # Haldane-Anscombe 보정 (0 셀 처리)
    a_h, b_h, c_h, d_h = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    or_val = (a_h * d_h) / (b_h * c_h)
    log_or = np.log(or_val)
    se_log_or = np.sqrt(1/a_h + 1/b_h + 1/c_h + 1/d_h)
    ci_lower = np.exp(log_or - 1.96 * se_log_or)
    ci_upper = np.exp(log_or + 1.96 * se_log_or)

    return {
        "beta": round(log_or, 4),
        "OR": round(or_val, 4),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "p_value": round(pval, 4),
        "method": "fisher",
    }


def run_logistic_regression(
    df: pd.DataFrame,
    feature_cols: list[str],
) -> pd.DataFrame:
    """
    기능 카테고리별 OR 분석.

    언급 수 >= 10건: 로지스틱 회귀 (통제변수 포함)
    언급 수 2~9건:  피셔 정확검정 (소표본 대응)

    Returns:
        DataFrame with columns:
            feature_category, beta, OR, ci_lower, ci_upper, p_value,
            n_reviews, n_positive, method
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
        if sub["sentiment_binary"].nunique() < 2:
            continue

        n_mentions = int(sub[col].sum())

        if n_mentions < _FISHER_MIN_MENTIONS:
            continue

        # ── 피셔 정확검정 (소표본) ─────────────────────────────────────────
        if n_mentions < _LOGIT_MIN_MENTIONS:
            fisher_res = _fisher_or(sub, col)
            if fisher_res is None:
                continue
            results.append({
                "feature_category": cat_name,
                "n_reviews": len(sub),
                "n_positive": int(sub["sentiment_binary"].sum()),
                **fisher_res,
            })
            continue

        # ── 로지스틱 회귀 (충분한 표본) ───────────────────────────────────
        # 분산이 없는 통제변수 제거 (상수 컬럼 → 특이행렬 방지)
        active_ctrl = [v for v in control_vars if sub[v].nunique() > 1]
        ctrl_str = " + ".join(active_ctrl) if active_ctrl else ""
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
                "method": "logit",
            })

        except (PerfectSeparationError, Exception):
            # 수렴 실패·특이행렬 발생 시 피셔 정확검정으로 대체
            fisher_res = _fisher_or(sub, col)
            if fisher_res is not None:
                results.append({
                    "feature_category": cat_name,
                    "n_reviews": len(sub),
                    "n_positive": int(sub["sentiment_binary"].sum()),
                    **fisher_res,
                })

    return pd.DataFrame(results)
