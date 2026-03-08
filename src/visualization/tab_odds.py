"""
Tab 3: Odds Ratio Analysis

- 기능 카테고리별 OR 테이블 (앱별)
- 신뢰구간 도트 플롯 (Plotly)
- ΔOR 테이블
- 앱별 분리 결과해석 (Insight box)
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.visualization._common import (
    SUBTEXT, LINE, TEXT,
    apply_dark_theme, centered_title,
    get_ordered_app_names, app_color, render_insight_box,
)


def _significance_label(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


def _or_dot_plot(combined: pd.DataFrame, app_names: list[str]) -> go.Figure:
    fig = go.Figure()
    for app_name in app_names:
        app_df = combined[combined["app_name"] == app_name].copy()
        if app_df.empty:
            continue
        color = app_color(app_name, app_names)
        fig.add_trace(go.Scatter(
            x=app_df["OR"],
            y=app_df["feature_category"],
            mode="markers",
            name=app_name,
            marker=dict(color=color, size=10, symbol="circle"),
            error_x=dict(
                type="data", symmetric=False,
                array=(app_df["ci_upper"] - app_df["OR"]).tolist(),
                arrayminus=(app_df["OR"] - app_df["ci_lower"]).tolist(),
                color=color, thickness=1.5, width=5,
            ),
            hovertemplate=(
                f"<b>{app_name}</b><br>"
                "기능: %{y}<br>"
                "OR: %{x:.3f}<br>"
                "95% CI: [%{customdata[0]:.3f}, %{customdata[1]:.3f}]<br>"
                "p-value: %{customdata[2]:.4f}"
                "<extra></extra>"
            ),
            customdata=app_df[["ci_lower", "ci_upper", "p_value"]].values,
        ))
    fig.add_vline(x=1.0, line_dash="dash", line_color=SUBTEXT, line_width=1.5,
                  annotation_text="OR=1 (기준)", annotation_position="top right",
                  annotation_font_color=SUBTEXT)
    fig.update_layout(
        title=centered_title("기능 카테고리별 오즈비 (OR) 비교"),
        xaxis_title="오즈비 (OR)",
        yaxis_title="기능 카테고리",
        height=max(400, len(combined["feature_category"].unique()) * 35 + 150),
        hovermode="closest",
        margin=dict(l=10, r=10, t=80, b=40),
    )
    apply_dark_theme(fig, centered_legend=True)
    return fig


def render(combined: pd.DataFrame, or_results: dict[str, pd.DataFrame]) -> None:
    st.markdown("""
    <div class="info-box">
    오즈비(OR)는 해당 기능이 리뷰에 언급될 때 긍정 평가와 얼마나 연관되는지 나타냅니다.<br>
    <b>OR > 1</b>이면 긍정과 더 연관, <b>OR &lt; 1</b>이면 부정과 더 연관됩니다.
    </div>
    """, unsafe_allow_html=True)

    if combined.empty:
        st.warning("회귀 분석 결과가 없습니다. 리뷰 데이터가 충분한지 확인해주세요.")
        return

    app_names = get_ordered_app_names(combined)

    # ── 도트 플롯 ──────────────────────────────────────────────────────────
    fig = _or_dot_plot(combined, app_names)
    st.plotly_chart(fig, use_container_width=True)

    sig_all = combined[combined["p_value"] < 0.05] if "p_value" in combined.columns else combined
    items = []
    for app_name in app_names:
        sub = combined[combined["app_name"] == app_name]
        sig = sub[sub["p_value"] < 0.05] if "p_value" in sub.columns else sub
        if sig.empty:
            items.append((app_name, app_color(app_name, app_names),
                          "통계적으로 유의한 기능 없음 (p≥0.05)."))
            continue
        top = sig.nlargest(1, "OR").iloc[0]
        bot = sig.nsmallest(1, "OR").iloc[0]
        items.append((
            app_name, app_color(app_name, app_names),
            f"긍정 연관 1위 → <b>{top['feature_category']}</b> (OR={top['OR']:.2f}): "
            f"언급 시 긍정 평점 {top['OR']:.1f}배. "
            f"부정 연관 1위 → <b>{bot['feature_category']}</b> (OR={bot['OR']:.2f}): "
            f"불만 리뷰에서 자주 등장."
        ))

    render_insight_box(
        "기능 카테고리별 오즈비 (OR) 비교",
        "각 기능이 긍정/부정 리뷰와 얼마나 연관되는지 통계적으로 측정합니다.",
        f"전체 {len(combined)}개 기능-앱 조합 중 {len(sig_all)}개가 유의(p<0.05). "
        "OR>1 기능을 강화하고, OR<1 기능을 개선하세요.",
        items,
    )

    # ── OR 상세 테이블 ─────────────────────────────────────────────────────
    st.markdown("#### 기능별 오즈비 상세 테이블")
    display_cols = ["feature_category", "app_name", "OR", "ci_lower", "ci_upper", "p_value"]
    if "delta_or" in combined.columns:
        display_cols.append("delta_or")
    if "priority_score" in combined.columns:
        display_cols.append("priority_score")
    existing = [c for c in display_cols if c in combined.columns]
    table_df = combined[existing].copy()
    app_order = {n: i for i, n in enumerate(app_names)}
    table_df["_order"] = table_df["app_name"].map(app_order).fillna(99)
    table_df = table_df.sort_values(["_order", "OR"], ascending=[True, False]).drop(columns="_order")
    if "p_value" in table_df.columns:
        table_df["유의성"] = table_df["p_value"].apply(_significance_label)
    col_rename = {
        "feature_category": "기능 카테고리", "app_name": "앱",
        "OR": "오즈비", "ci_lower": "95% CI 하한", "ci_upper": "95% CI 상한",
        "p_value": "p-value", "delta_or": "ΔOR", "priority_score": "우선순위 점수",
    }
    st.dataframe(table_df.rename(columns=col_rename), use_container_width=True, height=420)

    # ── ΔOR ───────────────────────────────────────────────────────────────
    if "delta_or" in combined.columns and combined["delta_or"].notna().any():
        st.markdown("#### ΔOR 해석")
        st.markdown("""
        <div class="info-box">
        <b>ΔOR = 비교 앱 OR − 기준 앱 OR</b><br>
        • ΔOR <b>음수</b>: 기준 앱 대비 해당 기능의 긍정 연관성이 낮습니다.<br>
        • ΔOR <b>양수</b>: 기준 앱 대비 우위에 있습니다.
        </div>
        """, unsafe_allow_html=True)

        delta_df = combined[["feature_category", "app_name", "delta_or"]].dropna().copy()
        delta_pivot = delta_df.pivot(index="feature_category", columns="app_name", values="delta_or")
        pivot_cols = [n for n in app_names if n in delta_pivot.columns]
        delta_pivot = delta_pivot[pivot_cols]
        try:
            st.dataframe(
                delta_pivot.style.background_gradient(cmap="RdYlGn", axis=None),
                use_container_width=True,
            )
        except Exception:
            st.dataframe(delta_pivot, use_container_width=True)

        if not delta_df.empty and len(app_names) >= 2:
            base_app = app_names[0]
            items = []
            for app_name in app_names[1:]:
                sub = delta_df[delta_df["app_name"] == app_name]
                if sub.empty:
                    continue
                best  = sub.loc[sub["delta_or"].idxmax()]
                worst = sub.loc[sub["delta_or"].idxmin()]
                items.append((
                    app_name, app_color(app_name, app_names),
                    f"vs {base_app} — "
                    f"최대 우위: <b>{best['feature_category']}</b> (ΔOR=+{best['delta_or']:.2f}), "
                    f"최대 열위: <b>{worst['feature_category']}</b> (ΔOR={worst['delta_or']:.2f}). "
                    f"열위 기능은 우선 개선이 필요합니다."
                ))
            render_insight_box(
                "ΔOR 분석",
                f"기준 앱({base_app}) 대비 각 앱의 기능별 경쟁력 차이를 수치화합니다.",
                "음수 ΔOR이 개선 과제, 양수가 강점. 절대값이 클수록 시급한 영역이에요.",
                items,
            )

    # ── 원본 다운로드 ──────────────────────────────────────────────────────
    with st.expander("📥 원본 회귀 결과 다운로드"):
        for app_name, df_or in or_results.items():
            csv = df_or.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label=f"{app_name} OR 결과 CSV",
                data=csv,
                file_name=f"or_result_{app_name}.csv",
                mime="text/csv",
            )
