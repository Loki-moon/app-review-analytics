"""
Tab 4: Feature Priority Matrix

- x축: ΔOR (경쟁 우위/열위)
- y축: 우선순위 점수
- 사분면 레이블
- Hover: 기능명, OR, ΔOR, 우선순위 점수
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.settings import APP_COLORS
from src.analysis.delta_or import get_priority_matrix_df
from src.visualization._common import (
    BG as _BG, GRID as _GRID, LINE as _LINE, TEXT as _TEXT, SUBTEXT as _SUBTEXT,
    apply_dark_theme, centered_title,
    get_ordered_app_names, app_color, render_insight_box,
)

# 다크 배경용 사분면 색상 (반투명)
# X축 기준: 양수 = 기준앱 경쟁 우위, 음수 = 기준앱 경쟁 열위
_QUADRANT_LABELS = {
    "Q1": ("경쟁 열위 & 개선 시급",  "rgba(185,28,28,0.18)",    "#FF8A9A"),   # 좌상 ← 기준앱 약함 + 우선순위 높음
    "Q2": ("경쟁 우위 유지 영역",    "rgba(6,95,70,0.18)",      "#4FD6A5"),   # 우상 ← 기준앱 강함 + 우선순위 높음
    "Q3": ("산업 공통 문제",          "rgba(146,64,14,0.12)",    "#FBB55C"),   # 좌하 ← 경쟁사도 함께 약한 영역
    "Q4": ("현상 유지 영역",          "rgba(30,64,175,0.12)",    "#7BA7F5"),   # 우하 ← 기준앱 강함, 상대적 저우선순위
}




def _build_scatter(
    matrix_df: pd.DataFrame,
    app_or_data: pd.DataFrame,
    base_app: str | None = None,
) -> go.Figure:
    fig = go.Figure()

    x_mid = 0.0
    y_mid = matrix_df["priority_score_max"].median() if not matrix_df.empty else 0.5

    x_range = [matrix_df["delta_or_mean"].min() - 0.5, matrix_df["delta_or_mean"].max() + 0.5]
    y_range = [0, matrix_df["priority_score_max"].max() * 1.2 + 0.1]

    quadrants = [
        (x_range[0], x_mid, y_mid, y_range[1], "Q1"),
        (x_mid, x_range[1], y_mid, y_range[1], "Q2"),
        (x_range[0], x_mid, y_range[0], y_mid, "Q3"),
        (x_mid, x_range[1], y_range[0], y_mid, "Q4"),
    ]
    for (x0, x1, y0, y1, q) in quadrants:
        label, fillcolor, font_color = _QUADRANT_LABELS[q]
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=fillcolor, opacity=1.0, layer="below", line_width=0)
        fig.add_annotation(
            x=(x0 + x1) / 2, y=y1 * 0.95,
            text=f"<b>{label}</b>",
            showarrow=False,
            font=dict(size=11, color=font_color),
            xanchor="center",
        )

    # 기준선
    base_label = f"{base_app} 기준" if base_app else "기준선"
    fig.add_vline(x=0, line_dash="dash", line_color=_SUBTEXT, line_width=1,
                  annotation_text=base_label, annotation_position="top right",
                  annotation_font_color=_SUBTEXT, annotation_font_size=10)
    fig.add_hline(y=y_mid, line_dash="dash", line_color=_SUBTEXT, line_width=1,
                  annotation_text="우선순위 중간값", annotation_position="right",
                  annotation_font_color=_SUBTEXT, annotation_font_size=10)

    # 산점도
    for _, row in matrix_df.iterrows():
        cat = row["feature_category"]
        x_val = row["delta_or_mean"]
        y_val = row["priority_score_max"]
        or_val = row["or_mean"]

        or_detail = ""
        if not app_or_data.empty:
            sub = app_or_data[app_or_data["feature_category"] == cat]
            for _, r2 in sub.iterrows():
                or_detail += f"  {r2['app_name']}: OR={r2['OR']:.3f}<br>"

        delta_label = (
            f"ΔOR ({base_app} 기준): {x_val:+.3f}"
            if base_app
            else f"ΔOR (평균): {x_val:.3f}"
        )
        position_label = (
            "→ 기준앱 경쟁 우위" if x_val > 0 else "→ 기준앱 경쟁 열위"
        ) if base_app else ""

        fig.add_trace(go.Scatter(
            x=[x_val],
            y=[y_val],
            mode="markers+text",
            text=[cat],
            textposition="top center",
            textfont=dict(size=10, color=_TEXT),
            marker=dict(
                size=max(12, min(30, y_val * 40 + 10)),
                color=APP_COLORS[hash(cat) % len(APP_COLORS)],
                line=dict(width=1.5, color="white"),
            ),
            name=cat,
            showlegend=False,
            hovertemplate=(
                f"<b>{cat}</b><br>"
                f"{delta_label}  {position_label}<br>"
                f"우선순위 점수: {y_val:.3f}<br>"
                f"OR (기준앱): {or_val:.3f}<br>"
                f"{or_detail}"
                "<extra></extra>"
            ),
        ))

    x_axis_title = (
        f"← {base_app} 경쟁 열위 &nbsp;&nbsp; | &nbsp;&nbsp; ΔOR &nbsp;&nbsp; | &nbsp;&nbsp; {base_app} 경쟁 우위 →"
        if base_app
        else "ΔOR (← 경쟁 열위 | 경쟁 우위 →)"
    )
    fig.update_layout(
        title=centered_title(
            f"기능 개선 우선순위 매트릭스 ({base_app} 기준)" if base_app else "기능 개선 우선순위 매트릭스"
        ),
        xaxis_title=x_axis_title,
        yaxis_title="우선순위 점수 (높을수록 개선 시급)",
        height=600,
        hovermode="closest",
        margin=dict(l=10, r=10, t=80, b=60),
    )
    apply_dark_theme(fig)
    fig.update_xaxes(range=x_range, zeroline=False)
    fig.update_yaxes(range=y_range, zeroline=False)
    return fig


def render(combined: pd.DataFrame) -> None:
    st.markdown("""
    <div class="info-box">
    기능 개선 우선순위 매트릭스입니다.<br>
    <b>좌상단(경쟁 열위 & 개선 시급)</b>에 위치한 기능일수록 경쟁사 대비 불리하고, 우선적으로 개선이 필요합니다.
    </div>
    """, unsafe_allow_html=True)

    if combined.empty or "delta_or" not in combined.columns:
        st.warning("우선순위 매트릭스를 계산하려면 2개 이상의 앱 분석 결과가 필요합니다.")
        return

    matrix_df = get_priority_matrix_df(combined)

    if matrix_df.empty:
        st.warning("우선순위 매트릭스 데이터가 부족합니다.")
        return

    # ── 차트 ──────────────────────────────────────────────────────────────────
    fig = _build_scatter(matrix_df, combined)
    st.plotly_chart(fig, use_container_width=True)

    # ── 결과해석 ──────────────────────────────────────────────────────────────
    app_names = get_ordered_app_names(combined)
    top3 = matrix_df.nlargest(3, "priority_score_max")
    top_text = " → ".join(
        f"<b>{r['feature_category']}</b>(점수 {r['priority_score_max']:.2f}, ΔOR={r['delta_or_mean']:.2f})"
        for _, r in top3.iterrows()
    )
    q1_features = matrix_df[
        (matrix_df["delta_or_mean"] < 0) &
        (matrix_df["priority_score_max"] >= matrix_df["priority_score_max"].median())
    ]
    render_insight_box(
        "기능 개선 우선순위 매트릭스",
        "기능별 경쟁 열위와 사용자 불만도를 결합해 개선 우선순위를 산출합니다.",
        "좌상단(경쟁 열위 & 개선 시급) 기능부터 개선하면 경쟁력을 가장 빠르게 올릴 수 있어요. "
        "우선순위 점수 = |ΔOR| 60% + 취약도 40%.",
        [
            ("전체 요약", "#4F8EF7",
             f"개선 우선순위 Top 3: {top_text}. "
             f"전체 {len(matrix_df)}개 기능 중 {len(q1_features)}개가 '경쟁 열위 &amp; 개선 시급' 영역에 있습니다."),
        ],
    )

    # ── 우선순위 테이블 ───────────────────────────────────────────────────────
    st.markdown("#### 기능 개선 우선순위 테이블")
    st.markdown("""
    <div class="info-box">
    우선순위 점수 = 0.6 × |ΔOR| + 0.4 × 취약도<br>
    취약도는 OR이 1보다 낮을수록(부정 리뷰와 더 연관될수록) 높아집니다.
    </div>
    """, unsafe_allow_html=True)

    priority_table = combined.sort_values("priority_score", ascending=False)[
        [c for c in ["feature_category", "app_name", "OR", "delta_or", "priority_score", "p_value"]
         if c in combined.columns]
    ].head(30)

    col_rename = {
        "feature_category": "기능 카테고리",
        "app_name": "앱",
        "OR": "오즈비",
        "delta_or": "ΔOR",
        "priority_score": "우선순위 점수",
        "p_value": "p-value",
    }
    st.dataframe(
        priority_table.rename(columns=col_rename),
        use_container_width=True,
        height=400,
    )

    # ── 다운로드 ──────────────────────────────────────────────────────────────
    csv = combined.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 전체 분석 결과 CSV 다운로드",
        data=csv,
        file_name="priority_analysis_result.csv",
        mime="text/csv",
    )
