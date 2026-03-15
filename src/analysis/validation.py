"""
통계 검증 모듈 (PRD 28번)

검증 항목:
1. 모형 적합도 (Model Fit)      - Pseudo R², AIC, BIC, Log-Likelihood
2. 회귀계수 유의성               - β, OR, CI, p-value per keyword
3. 상호작용 효과 검정             - Wald / LR test (keyword × service 더미)
4. 다중공선성                    - 상관계수 행렬, VIF
5. 평점 이분화 기준 민감도        - 3가지 임계 조건 비교
6. 기간 분할 안정성              - 전체 / 상반기 / 하반기 OR 비교
7. 표본 분포                    - 앱별 건수, 평점분포, 월별 추이
"""
from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.outliers_influence import variance_inflation_factor

from config.settings import NEGATIVE_THRESHOLD, POSITIVE_THRESHOLD
from src.analysis.model import build_regression_df, run_logistic_regression
from src.analysis.keyword import get_category_columns


# ─────────────────────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _significance_label(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


def _badge(status: str) -> str:
    """status: 'pass' | 'warn' | 'fail'"""
    mapping = {
        "pass": ("✅ 양호", "#D1FAE5", "#065F46"),
        "warn": ("⚠️ 주의", "#FEF3C7", "#92400E"),
        "fail": ("❌ 경고", "#FEE2E2", "#B91C1C"),
    }
    label, bg, color = mapping.get(status, mapping["warn"])
    return label, bg, color


# ─────────────────────────────────────────────────────────────────────────────
# 1. 모형 적합도
# ─────────────────────────────────────────────────────────────────────────────

def compute_model_fit(df: pd.DataFrame, feature_cols: list[str]) -> dict[str, Any]:
    """앱별 로지스틱 회귀 전체 모형 적합도 지표 반환"""
    rows = []
    control_vars = [c for c in ["review_length", "update_flag"] if c in df.columns]

    for app_name, group in df.groupby("app_name"):
        reg_df = build_regression_df(group)
        if len(reg_df) < 30:
            continue

        valid_feats = [c for c in feature_cols if reg_df[c].sum() >= 5]
        if not valid_feats:
            continue

        feat_str = " + ".join(valid_feats)
        ctrl_str = (" + " + " + ".join(control_vars)) if control_vars else ""
        formula = f"sentiment_binary ~ {feat_str}{ctrl_str}"

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = smf.logit(formula, data=reg_df).fit(disp=False, maxiter=200)

            null_model = smf.logit("sentiment_binary ~ 1", data=reg_df).fit(disp=False, maxiter=200)
            pseudo_r2 = 1 - (model.llf / null_model.llf)

            rows.append({
                "app_name": str(app_name),
                "log_likelihood": round(model.llf, 3),
                "aic": round(model.aic, 3),
                "bic": round(model.bic, 3),
                "pseudo_r2": round(pseudo_r2, 4),
                "n_obs": int(model.nobs),
                "status": "pass" if pseudo_r2 >= 0.2 else ("warn" if pseudo_r2 >= 0.1 else "fail"),
                "_model": model,
            })
        except Exception:
            continue

    return {
        "table": pd.DataFrame([{k: v for k, v in r.items() if k != "_model"} for r in rows]),
        "_models": {r["app_name"]: r["_model"] for r in rows if "_model" in r},
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. 회귀계수 유의성
# ─────────────────────────────────────────────────────────────────────────────

def compute_coef_significance(combined_or: pd.DataFrame) -> pd.DataFrame:
    """combined_or DataFrame 기반 유의성 테이블 생성"""
    if combined_or.empty:
        return pd.DataFrame()

    df = combined_or.copy()
    df["significance"] = df["p_value"].apply(_significance_label)
    df["is_significant"] = df["p_value"] < 0.05
    df["status"] = df["p_value"].apply(
        lambda p: "pass" if p < 0.05 else "warn" if p < 0.1 else "fail"
    )
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 3. 상호작용 효과 검정
# ─────────────────────────────────────────────────────────────────────────────

def compute_interaction_test(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """
    기능 키워드 × 앱 더미 상호작용항 Wald / LR test 수행.
    앱이 2개 이상인 경우에만 의미 있음.
    """
    app_names = df["app_name"].unique().tolist()
    if len(app_names) < 2:
        return pd.DataFrame()

    # 앱 더미 (기준=첫 번째 앱)
    base_app = app_names[0]
    df = df.copy()
    df["app_dummy"] = (df["app_name"] != base_app).astype(int)

    reg_df = build_regression_df(df)
    if len(reg_df) < 50:
        return pd.DataFrame()

    control_vars = [c for c in ["review_length", "update_flag"] if c in reg_df.columns]
    rows = []

    for col in feature_cols:
        cat = col.replace("keyword_", "")
        if reg_df[col].sum() < 5:
            continue

        interaction_term = f"interaction_{cat}"
        reg_df[interaction_term] = reg_df[col] * reg_df["app_dummy"]

        ctrl_str = (" + " + " + ".join(control_vars)) if control_vars else ""
        formula_full    = f"sentiment_binary ~ {col} + app_dummy + {interaction_term}{ctrl_str}"
        formula_reduced = f"sentiment_binary ~ {col} + app_dummy{ctrl_str}"

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m_full    = smf.logit(formula_full,    data=reg_df).fit(disp=False, maxiter=200)
                m_reduced = smf.logit(formula_reduced, data=reg_df).fit(disp=False, maxiter=200)

            # LR test statistic
            lr_stat = 2 * (m_full.llf - m_reduced.llf)
            from scipy.stats import chi2
            lr_pval = chi2.sf(lr_stat, df=1)

            # Wald p-value
            wald_pval = m_full.pvalues.get(interaction_term, float("nan"))

            rows.append({
                "feature_category": cat,
                "wald_pvalue": round(wald_pval, 4),
                "lr_pvalue": round(lr_pval, 4),
                "wald_sig": _significance_label(wald_pval),
                "lr_sig": _significance_label(lr_pval),
                "status": "pass" if lr_pval < 0.05 else "warn" if lr_pval < 0.1 else "fail",
            })
        except Exception:
            continue

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 4. 다중공선성
# ─────────────────────────────────────────────────────────────────────────────

def compute_multicollinearity(df: pd.DataFrame, feature_cols: list[str]) -> dict[str, Any]:
    """상관계수 행렬 + VIF 테이블"""
    sub = df[feature_cols].copy().dropna()
    if sub.empty or len(sub.columns) < 2:
        return {"corr_matrix": pd.DataFrame(), "vif_table": pd.DataFrame()}

    # 분산이 0인 컬럼 제거
    sub = sub.loc[:, sub.std() > 0]
    if sub.shape[1] < 2:
        return {"corr_matrix": pd.DataFrame(), "vif_table": pd.DataFrame()}

    corr_matrix = sub.corr().round(3)
    corr_matrix.index   = [c.replace("keyword_", "") for c in corr_matrix.index]
    corr_matrix.columns = [c.replace("keyword_", "") for c in corr_matrix.columns]

    # VIF
    vif_rows = []
    X = sub.copy()
    X.insert(0, "const", 1.0)
    feat_list = list(sub.columns)
    for i, col in enumerate(feat_list):
        try:
            vif_val = variance_inflation_factor(X.values, i + 1)
        except Exception:
            vif_val = float("nan")
        vif_rows.append({
            "feature_category": col.replace("keyword_", ""),
            "vif": round(vif_val, 3),
            "status": "pass" if vif_val < 5 else ("warn" if vif_val < 10 else "fail"),
        })

    return {
        "corr_matrix": corr_matrix,
        "vif_table": pd.DataFrame(vif_rows),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. 평점 이분화 기준 민감도
# ─────────────────────────────────────────────────────────────────────────────

def compute_threshold_sensitivity(raw_df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """
    3가지 조건별 OR 비교:
    - baseline: 3점 제외
    - incl_pos : 3점 → 긍정(1)
    - incl_neg : 3점 → 부정(0)
    """
    results = {}

    conditions = {
        "3점 제외 (기본)": None,
        "3점 → 긍정 포함": 1,
        "3점 → 부정 포함": 0,
    }

    for cond_name, three_label in conditions.items():
        df = raw_df.copy()
        if three_label is None:
            df["sentiment_binary"] = df["score"].apply(
                lambda s: 1.0 if s >= POSITIVE_THRESHOLD else (0.0 if s <= NEGATIVE_THRESHOLD else float("nan"))
            )
        else:
            df["sentiment_binary"] = df["score"].apply(
                lambda s: 1.0 if (s >= POSITIVE_THRESHOLD or s == 3) else 0.0
                if three_label == 1
                else (0.0 if (s <= NEGATIVE_THRESHOLD or s == 3) else 1.0)
            )

        df = df.dropna(subset=["sentiment_binary"])
        if "content" in df.columns:
            df["review_length"] = df["content"].str.len().fillna(0)
        if "update_flag" not in df.columns:
            df["update_flag"] = 0

        app_ors = []
        for app_name, group in df.groupby("app_name"):
            try:
                or_df = run_logistic_regression(group, feature_cols)
                or_df["app_name"] = app_name
                or_df["condition"] = cond_name
                app_ors.append(or_df)
            except Exception:
                continue

        if app_ors:
            results[cond_name] = pd.concat(app_ors, ignore_index=True)

    if not results:
        return pd.DataFrame()

    combined = pd.concat(results.values(), ignore_index=True)

    # 방향 일치 여부: OR > 1 / OR < 1 기준
    pivot = combined.pivot_table(
        index=["feature_category", "app_name"],
        columns="condition",
        values="OR",
    )
    pivot["direction_consistent"] = pivot.apply(
        lambda row: len(set((v > 1) for v in row.dropna())) == 1, axis=1
    )
    pivot = pivot.reset_index()

    return combined, pivot


# ─────────────────────────────────────────────────────────────────────────────
# 6. 기간 분할 안정성
# ─────────────────────────────────────────────────────────────────────────────

def compute_period_stability(raw_df: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """전체 / 상반기 / 하반기 OR 비교"""
    df = raw_df.copy()
    df["review_date_dt"] = pd.to_datetime(df["review_date"], errors="coerce")
    df = df.dropna(subset=["review_date_dt"])

    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    mid_date = df["review_date_dt"].min() + (df["review_date_dt"].max() - df["review_date_dt"].min()) / 2

    subsets = {
        "전체": df,
        "상반기": df[df["review_date_dt"] <= mid_date],
        "하반기": df[df["review_date_dt"] > mid_date],
    }

    all_rows = []
    for period_name, sub in subsets.items():
        if sub.empty:
            continue
        reg_df = build_regression_df(sub)
        for app_name, group in reg_df.groupby("app_name"):
            try:
                or_df = run_logistic_regression(group, feature_cols)
                or_df["app_name"] = app_name
                or_df["period"] = period_name
                all_rows.append(or_df)
            except Exception:
                continue

    if not all_rows:
        return pd.DataFrame(), pd.DataFrame()

    combined = pd.concat(all_rows, ignore_index=True)

    # 방향 일치 히트맵용 피벗
    pivot = combined.pivot_table(
        index="feature_category",
        columns="period",
        values="OR",
        aggfunc="mean",
    ).reset_index()

    periods = ["전체", "상반기", "하반기"]
    available = [p for p in periods if p in pivot.columns]
    if len(available) >= 2:
        pivot["direction_consistent"] = pivot[available].apply(
            lambda row: len(set((v > 1) for v in row.dropna())) <= 1, axis=1
        )
    else:
        pivot["direction_consistent"] = True

    return combined, pivot


# ─────────────────────────────────────────────────────────────────────────────
# 7. 표본 분포
# ─────────────────────────────────────────────────────────────────────────────

def compute_sample_distribution(raw_df: pd.DataFrame) -> dict[str, Any]:
    """앱별 리뷰 수, 평점 분포, 월별 추이, 긍정/부정 비율"""
    if raw_df.empty:
        return {}

    # 기본 통계
    app_counts = raw_df.groupby("app_name").size().reset_index(name="review_count")
    score_dist  = raw_df.groupby(["app_name", "score"]).size().reset_index(name="count")

    # 긍정/부정 비율
    df = raw_df.copy()
    df["sentiment"] = df["score"].apply(
        lambda s: "긍정" if s >= POSITIVE_THRESHOLD else ("부정" if s <= NEGATIVE_THRESHOLD else "보통")
    )
    sentiment_dist = df.groupby(["app_name", "sentiment"]).size().reset_index(name="count")

    # 월별 추이
    df["review_date_dt"] = pd.to_datetime(df["review_date"], errors="coerce")
    df["year_month"] = df["review_date_dt"].dt.to_period("M").astype(str)
    monthly = df.groupby(["app_name", "year_month"]).size().reset_index(name="count")
    monthly = monthly.sort_values("year_month")

    # 앱별 불균형 여부 판단
    imbalance_status = {}
    for app_name, group in df.groupby("app_name"):
        total = len(group)
        pos = (group["sentiment"] == "긍정").sum()
        neg = (group["sentiment"] == "부정").sum()
        ratio = max(pos, neg) / (min(pos, neg) + 1e-9)
        imbalance_status[str(app_name)] = "warn" if ratio > 3 else "pass"

    return {
        "app_counts": app_counts,
        "score_dist": score_dist,
        "sentiment_dist": sentiment_dist,
        "monthly": monthly,
        "imbalance_status": imbalance_status,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 전체 검증 요약
# ─────────────────────────────────────────────────────────────────────────────

def run_all_validations(
    raw_df: pd.DataFrame,
    processed_df: pd.DataFrame,
    combined_or: pd.DataFrame,
) -> dict[str, Any]:
    """
    모든 검증 지표를 한 번에 계산하여 반환.
    pipeline_result["processed_df"]와 combined_or를 입력으로 받는다.
    """
    feature_cols = get_category_columns(processed_df) if not processed_df.empty else []

    result: dict[str, Any] = {}

    # 1. 모형 적합도
    try:
        result["model_fit"] = compute_model_fit(processed_df, feature_cols)
    except Exception as e:
        result["model_fit"] = {"error": str(e)}

    # 2. 회귀계수 유의성
    try:
        result["coef_sig"] = compute_coef_significance(combined_or)
    except Exception as e:
        result["coef_sig"] = pd.DataFrame()

    # 3. 상호작용 효과 검정
    try:
        result["interaction"] = compute_interaction_test(processed_df, feature_cols)
    except Exception as e:
        result["interaction"] = pd.DataFrame()

    # 4. 다중공선성
    try:
        result["multicol"] = compute_multicollinearity(processed_df, feature_cols)
    except Exception as e:
        result["multicol"] = {"corr_matrix": pd.DataFrame(), "vif_table": pd.DataFrame()}

    # 5. 민감도 분석 (임계값)
    try:
        sens = compute_threshold_sensitivity(raw_df, feature_cols)
        result["threshold_sens"] = sens if isinstance(sens, tuple) else (pd.DataFrame(), pd.DataFrame())
    except Exception as e:
        result["threshold_sens"] = (pd.DataFrame(), pd.DataFrame())

    # 6. 기간 분할 안정성
    try:
        result["period_stab"] = compute_period_stability(raw_df, feature_cols)
    except Exception as e:
        result["period_stab"] = (pd.DataFrame(), pd.DataFrame())

    # 7. 표본 분포
    try:
        result["sample_dist"] = compute_sample_distribution(raw_df)
    except Exception as e:
        result["sample_dist"] = {}

    # 8. raw_df 기초 통계 (민감도/기간 분할 데이터 부족 안내용)
    try:
        from config.settings import POSITIVE_THRESHOLD, NEGATIVE_THRESHOLD  # noqa: F401
        df_tmp = raw_df.copy()
        df_tmp["review_date_dt"] = pd.to_datetime(df_tmp.get("review_date", None), errors="coerce")
        mid = (
            df_tmp["review_date_dt"].min()
            + (df_tmp["review_date_dt"].max() - df_tmp["review_date_dt"].min()) / 2
        ) if df_tmp["review_date_dt"].notna().any() else None
        raw_stats: dict[str, Any] = {}
        for app_name, grp in raw_df.groupby("app_name"):
            total = len(grp)
            pos   = int((grp["score"] >= POSITIVE_THRESHOLD).sum()) if "score" in grp.columns else 0
            neg   = int((grp["score"] <= NEGATIVE_THRESHOLD).sum()) if "score" in grp.columns else 0
            if mid is not None and "review_date" in grp.columns:
                grp_dt = pd.to_datetime(grp["review_date"], errors="coerce")
                n_first  = int((grp_dt <= mid).sum())
                n_second = int((grp_dt  > mid).sum())
            else:
                n_first = n_second = 0
            raw_stats[app_name] = {
                "total": total, "pos": pos, "neg": neg,
                "n_first_half": n_first, "n_second_half": n_second,
            }
        result["raw_stats"] = raw_stats
    except Exception:
        result["raw_stats"] = {}

    return result
