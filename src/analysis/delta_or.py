"""
ΔOR 계산 및 우선순위 점수 모듈

- ΔOR = OR_A - OR_B (기준 앱 대비 비교 앱의 기능 영향력 차이)
- 우선순위 점수 = w_delta * |ΔOR| + w_vuln * 취약도
- 취약도: OR < 1인 경우 (1 - OR), 그 외 0
"""
from __future__ import annotations

import pandas as pd

from config.settings import PRIORITY_WEIGHTS


def compute_delta_or(
    or_results: dict[str, pd.DataFrame],
    base_app: str,
) -> pd.DataFrame:
    """
    OR 결과를 앱별로 병합하여 ΔOR 계산.

    Args:
        or_results: {app_name: OR DataFrame} (run_logistic_regression 반환값)
        base_app: 기준 앱 이름 (보통 첫 번째 앱)

    Returns:
        feature_category, app_name, OR, ci_lower, ci_upper, p_value,
        delta_or, priority_score
    """
    if base_app not in or_results:
        base_app = next(iter(or_results))

    base_df = or_results[base_app].copy()
    base_df = base_df.rename(
        columns={"OR": "OR_base", "ci_lower": "ci_lower_base", "ci_upper": "ci_upper_base"}
    )

    rows = []

    for app_name, app_df in or_results.items():
        merged = app_df.merge(
            base_df[["feature_category", "OR_base"]],
            on="feature_category",
            how="left",
        )
        merged["delta_or"] = (merged["OR"] - merged["OR_base"]).round(4)

        # 취약도: OR < 1 이면 (1 - OR), 그 외 0
        merged["vulnerability"] = merged["OR"].apply(lambda x: max(0.0, 1.0 - x))

        # 우선순위 점수
        w_d = PRIORITY_WEIGHTS["w_delta"]
        w_v = PRIORITY_WEIGHTS["w_vuln"]
        merged["priority_score"] = (
            w_d * merged["delta_or"].abs() + w_v * merged["vulnerability"]
        ).round(4)

        merged["app_name"] = app_name
        rows.append(merged)

    if not rows:
        return pd.DataFrame()

    result = pd.concat(rows, ignore_index=True)

    col_order = [
        "feature_category", "app_name",
        "beta", "OR", "ci_lower", "ci_upper", "p_value",
        "delta_or", "priority_score", "n_reviews", "n_positive",
    ]
    existing = [c for c in col_order if c in result.columns]
    return result[existing].sort_values(["feature_category", "app_name"])


def get_priority_matrix_df(
    combined: pd.DataFrame,
    base_app: str | None = None,
) -> pd.DataFrame:
    """
    우선순위 매트릭스용 집계 DataFrame (기준앱 기준).

    base_app이 주어지면 기준앱 시각에서 ΔOR을 계산합니다.
      delta_or_mean = OR_base - mean(OR_competitors)
      → 양수(+): 기준앱 경쟁 우위 / 음수(-): 기준앱 경쟁 열위

    base_app이 없으면 기존 방식(전체 평균)을 사용합니다.
    """
    if combined.empty:
        return pd.DataFrame()

    app_names = combined["app_name"].unique().tolist()

    if base_app is not None and base_app in app_names:
        base_df = combined[combined["app_name"] == base_app].copy()
        comp_df = combined[combined["app_name"] != base_app]

        if base_df.empty:
            return pd.DataFrame()

        # 경쟁사 평균 OR
        if not comp_df.empty:
            comp_mean = (
                comp_df.groupby("feature_category")["OR"]
                .mean()
                .rename("OR_comp_mean")
            )
            base_df = base_df.merge(comp_mean, on="feature_category", how="left")
            base_df["OR_comp_mean"] = base_df["OR_comp_mean"].fillna(base_df["OR"])
        else:
            base_df["OR_comp_mean"] = base_df["OR"]

        # 기준앱 시각: 양수 = 기준앱 우위, 음수 = 기준앱 열위
        base_df["delta_or_mean"] = (base_df["OR"] - base_df["OR_comp_mean"]).round(4)
        base_df["vulnerability"]  = (1.0 - base_df["OR"]).clip(lower=0)

        w_d = PRIORITY_WEIGHTS["w_delta"]
        w_v = PRIORITY_WEIGHTS["w_vuln"]
        base_df["priority_score_max"] = (
            w_d * base_df["delta_or_mean"].abs() + w_v * base_df["vulnerability"]
        ).round(4)

        return base_df[["feature_category", "delta_or_mean", "priority_score_max", "OR"]].rename(
            columns={"OR": "or_mean"}
        ).reset_index(drop=True)

    # ── 기존 방식 (base_app 미지정 시) ──────────────────────────────────────────
    pivot = (
        combined.groupby("feature_category")
        .agg(
            delta_or_mean=("delta_or", "mean"),
            priority_score_max=("priority_score", "max"),
            or_mean=("OR", "mean"),
        )
        .reset_index()
    )
    return pivot
