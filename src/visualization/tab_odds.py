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
    get_ordered_app_names, app_color, render_insight_box, render_skeleton,
)


def _significance_label(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


def _or_dot_plot(
    combined: pd.DataFrame,
    app_names: list[str],
    use_log: bool = False,
    title: str = "기능 카테고리별 오즈비 (OR) 비교",
    all_app_names: list[str] | None = None,
) -> go.Figure:
    """오즈비 도트 플롯.

    Parameters
    ----------
    combined : 플롯할 데이터 (app_name 필터 이미 적용된 상태여도 됨)
    app_names : 이 플롯에 표시할 앱 이름 목록 (색상 인덱스 기준)
    use_log : 로그 스케일 여부
    title : 차트 제목
    all_app_names : 전체 앱 목록 (색상 일관성 유지용). None이면 app_names 사용
    """
    if all_app_names is None:
        all_app_names = app_names

    fig = go.Figure()

    plot_combined = combined.copy()
    if use_log:
        plot_combined["OR"]       = plot_combined["OR"].clip(lower=0.01)
        plot_combined["ci_lower"] = plot_combined["ci_lower"].clip(lower=0.01)
        plot_combined["ci_upper"] = plot_combined["ci_upper"].clip(lower=0.01)

    # p-value 기준 카테고리 정렬 (유의한 것 상단)
    if "p_value" in plot_combined.columns:
        cat_pval = plot_combined.groupby("feature_category")["p_value"].min()
        sorted_cats = cat_pval.sort_values(ascending=False).index.tolist()
    else:
        cat_pval = pd.Series(dtype=float)
        sorted_cats = plot_combined["feature_category"].unique().tolist()

    for app_name in app_names:
        app_df = plot_combined[plot_combined["app_name"] == app_name].copy()
        if app_df.empty:
            continue
        color = app_color(app_name, all_app_names)

        if "p_value" in app_df.columns:
            sig_df  = app_df[app_df["p_value"] < 0.05]
            nsig_df = app_df[app_df["p_value"] >= 0.05]
        else:
            sig_df, nsig_df = app_df, pd.DataFrame(columns=app_df.columns)

        # ── 유의 (p<0.05): 실선 오차막대 + 채운 마커 ─────────────────────────
        if not sig_df.empty:
            fig.add_trace(go.Scatter(
                x=sig_df["OR"],
                y=sig_df["feature_category"],
                mode="markers",
                name=app_name,
                showlegend=True,
                marker=dict(color=color, size=10, symbol="circle", opacity=1.0),
                error_x=dict(
                    type="data", symmetric=False,
                    array=(sig_df["ci_upper"] - sig_df["OR"]).tolist(),
                    arrayminus=(sig_df["OR"] - sig_df["ci_lower"]).tolist(),
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
                customdata=sig_df[["ci_lower", "ci_upper", "p_value"]].values,
            ))

        # ── 비유의 (p≥0.05): 점선 CI + 빈 마커 ──────────────────────────────
        if not nsig_df.empty:
            # 점선 CI 구간 (None으로 세그먼트 분리)
            xs, ys = [], []
            for _, row in nsig_df.iterrows():
                xs.extend([row["ci_lower"], row["ci_upper"], None])
                ys.extend([row["feature_category"], row["feature_category"], None])
            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode="lines",
                line=dict(color=color, dash="dot", width=1.5),
                opacity=0.45,
                showlegend=False,
                hoverinfo="skip",
            ))
            # 빈 원형 마커
            fig.add_trace(go.Scatter(
                x=nsig_df["OR"],
                y=nsig_df["feature_category"],
                mode="markers",
                name=app_name,
                showlegend=False,
                marker=dict(
                    color="rgba(0,0,0,0)",
                    line=dict(color=color, width=1.5),
                    size=9, symbol="circle-open", opacity=0.5,
                ),
                hovertemplate=(
                    f"<b>{app_name}</b> (n.s.)<br>"
                    "기능: %{y}<br>"
                    "OR: %{x:.3f}<br>"
                    "95% CI: [%{customdata[0]:.3f}, %{customdata[1]:.3f}]<br>"
                    "p-value: %{customdata[2]:.4f}"
                    "<extra></extra>"
                ),
                customdata=nsig_df[["ci_lower", "ci_upper", "p_value"]].values,
            ))

    fig.add_vline(x=1.0, line_dash="dash", line_color=SUBTEXT, line_width=1.5,
                  annotation_text="OR=1 (기준)", annotation_position="top right",
                  annotation_font_color=SUBTEXT)

    n_cats = len(plot_combined["feature_category"].unique())
    fig.update_layout(
        title=centered_title(title),
        xaxis_title="오즈비 (OR, 로그 스케일)" if use_log else "오즈비 (OR)",
        yaxis_title="",
        height=max(400, n_cats * 38 + 150),
        hovermode="closest",
        margin=dict(l=240, r=10, t=80, b=80),
    )
    apply_dark_theme(fig, centered_legend=False)

    # Y축: tick label 숨기고 annotation으로 대체 (p-value 색상 구분)
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=sorted_cats,
        showticklabels=False,
        zeroline=False,
    )
    for cat in sorted_cats:
        pval = cat_pval.get(cat) if len(cat_pval) > 0 else None
        if pval is not None:
            star = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else "n.s."
            p_str = "p<0.001" if pval < 0.001 else f"p={pval:.3f}"
            label = f"{cat}  ({p_str} {star})"
            font_color = TEXT if pval < 0.05 else SUBTEXT
        else:
            label = cat
            font_color = TEXT
        fig.add_annotation(
            x=-0.01, xref="paper", xanchor="right",
            y=cat, yref="y",
            text=label,
            showarrow=False,
            font=dict(size=10, color=font_color),
            align="right",
        )

    fig.update_layout(legend=dict(
        bgcolor="#131820", bordercolor=LINE, font=dict(color=TEXT),
        orientation="h", yanchor="top", y=-0.08,
        xanchor="center", x=0.5,
    ))
    if use_log:
        fig.update_xaxes(type="log")
    return fig


def _app_or_table(df: pd.DataFrame, app_name: str) -> None:
    """단일 앱의 OR 상세 테이블 렌더링."""
    display_cols = ["feature_category", "OR", "ci_lower", "ci_upper", "p_value", "n_reviews", "method"]
    existing = [c for c in display_cols if c in df.columns]
    table_df = df[existing].copy().sort_values("OR", ascending=False)
    if "p_value" in table_df.columns:
        table_df["유의성"] = table_df["p_value"].apply(_significance_label)
    col_rename = {
        "feature_category": "기능 카테고리",
        "OR": "오즈비", "ci_lower": "95% CI 하한", "ci_upper": "95% CI 상한",
        "p_value": "p-value", "n_reviews": "리뷰 수", "method": "분석방법",
    }
    # method 값 한글화
    if "method" in table_df.columns:
        table_df["method"] = table_df["method"].map({"logit": "로지스틱회귀", "fisher": "피셔검정"}).fillna(table_df["method"])
    st.dataframe(table_df.rename(columns=col_rename), use_container_width=True, height=360)


def render(combined: pd.DataFrame, or_results: dict[str, pd.DataFrame]) -> None:
    st.markdown("""
    <div class="info-box">
    오즈비(OR)는 해당 기능이 리뷰에 언급될 때 긍정 평가와 얼마나 연관되는지 나타냅니다.<br>
    <b>OR > 1</b>이면 긍정과 더 연관, <b>OR &lt; 1</b>이면 부정과 더 연관됩니다.
    </div>
    """, unsafe_allow_html=True)

    # 분석 방법론 설명 (expander)
    with st.expander("📐 분석 방법론 — OR 계산 방식 안내", expanded=True):
        st.markdown("""
        #### 왜 두 가지 분석 방법을 사용하나요?

        오즈비(OR)를 계산할 때, **기능 키워드가 리뷰에 얼마나 자주 언급되었는지**에 따라
        적합한 통계 기법이 달라집니다.

        | 언급 리뷰 수 | 적용 방법 | 이유 |
        |---|---|---|
        | **10건 이상** | 로지스틱 회귀 (Logistic Regression) | 충분한 표본 → 통제변수(리뷰 길이·업데이트 여부) 포함, 다변량 추정 가능 |
        | **2~9건** | 피셔 정확검정 (Fisher's Exact Test) | 소표본 → 로지스틱 회귀는 수렴 불가, 역학 연구 표준 방법으로 대체 |

        #### 피셔 정확검정을 사용하는 이유

        앱 리뷰 분석에서는 **특정 기능(예: 교통카드, 만보기 등)을 직접 언급하는 리뷰가 적은 경우**가
        흔합니다. 특히 비교 대상 앱이 주력 기능이 아닌 영역에서는 언급 수가 2~5건에 그치기도 합니다.

        이 경우 로지스틱 회귀는 다음 이유로 사용할 수 없습니다:
        - 모델 수렴 실패 (최대 우도 추정 불안정)
        - 완전 분리 문제 (Perfect Separation) — 언급된 리뷰가 모두 긍정 또는 모두 부정인 경우

        **피셔 정확검정**은 2×2 분할표(언급 여부 × 긍부정)를 기반으로 소표본에서도
        정확한 p-value와 OR을 계산할 수 있으며, 역학(epidemiology) 및 의학 연구에서
        소표본 상관관계 분석의 표준 방법으로 널리 사용됩니다.
        신뢰구간은 **Haldane-Anscombe 보정**(빈 셀에 0.5 추가)을 적용해 0건 셀도 안정적으로 처리합니다.

        > ⚠️ 피셔 정확검정으로 계산된 OR은 통제변수가 포함되지 않으므로,
        > 언급 수가 10건 이상인 카테고리의 OR과 직접 수치 비교 시 유의해야 합니다.
        > 상세 테이블의 **분석방법** 컬럼에서 각 카테고리의 적용 방법을 확인할 수 있습니다.
        """)


    if combined.empty and not or_results:
        render_skeleton("오즈비 분석 결과를 불러오는 중입니다", show_chart=True, chart_height=240)
        return

    # or_results에 있는 앱 데이터가 combined에 없으면 보완 (1개 앱만 있는 경우 등)
    combined = combined.copy() if not combined.empty else pd.DataFrame()
    for app_name, app_df in or_results.items():
        if app_df.empty:
            continue
        already_in = (not combined.empty and "app_name" in combined.columns
                      and app_name in combined["app_name"].values)
        if not already_in:
            extra = app_df.copy()
            extra["app_name"] = app_name
            combined = pd.concat([combined, extra], ignore_index=True) if not combined.empty else extra

    if combined.empty:
        render_skeleton("오즈비 분석 결과를 불러오는 중입니다", show_chart=True, chart_height=240)
        return

    # app_names: or_results 기준 (회귀 성공 앱 전체) + combined에만 있는 앱 보완
    or_app_names = list(or_results.keys())
    combined_app_names = get_ordered_app_names(combined)
    seen: set[str] = set(or_app_names)
    app_names = or_app_names + [a for a in combined_app_names if a not in seen]

    # 누락 OR 탐지
    all_cats = combined["feature_category"].unique()
    missing_info: dict[str, list[str]] = {}
    for an in app_names:
        present = set(combined[combined["app_name"] == an]["feature_category"].unique())
        missing = sorted(set(all_cats) - present)
        if missing:
            missing_info[an] = missing

    # 로그 스케일 권장 여부
    max_or = combined["OR"].max() if "OR" in combined.columns else 0
    suggest_log = max_or > 5

    extra_html = ""
    if missing_info:
        rows = " | ".join(
            f"<b>{an}</b>: {', '.join(cats[:3])}{'…' if len(cats) > 3 else ''} ({len(cats)}개 미표시)"
            for an, cats in missing_info.items()
        )
        extra_html += (
            f'<br>⚠️ <b>일부 기능의 OR이 특정 앱에서 누락됨</b> — {rows}.<br>'
            f'&nbsp;&nbsp;원인: 해당 앱 리뷰에서 기능 키워드가 충분히 등장하지 않아 '
            f'로지스틱 회귀분석이 수렴하지 못했거나 관련 리뷰 자체가 없는 경우입니다.'
        )
    if suggest_log:
        extra_html += (
            f'<br>📐 <b>OR 최대값({max_or:.1f})이 크게 나타남</b> — '
            f'로그 스케일 적용 시 모든 기능의 차이를 동시에 비교할 수 있습니다.'
        )
    if extra_html:
        st.markdown(
            f'<div class="info-box">{extra_html.lstrip("<br>")}</div>',
            unsafe_allow_html=True,
        )

    use_log = False
    if suggest_log:
        use_log = st.checkbox(
            f"📐 로그 스케일 적용 (OR 최대값 {max_or:.1f} — 값 범위가 커서 자동 활성화)",
            value=True,
            key="odds_or_log_scale",
        )

    # ── 공통 feature_category 계산 ─────────────────────────────────────────
    per_app_cats = [
        set(combined[combined["app_name"] == an]["feature_category"].unique())
        for an in app_names
    ]
    common_cats: set[str] = per_app_cats[0].intersection(*per_app_cats[1:]) if len(per_app_cats) > 1 else per_app_cats[0]

    # ── 앱별 개별 도트 플롯 (1×1 배열) ────────────────────────────────────
    st.markdown("### 앱별 오즈비 (OR) 비교")
    st.caption(
        f"각 앱의 기능별 OR을 독립적으로 표시합니다. "
        f"아래 '공통 기능 비교' 차트에서 {len(app_names)}개 앱을 함께 비교할 수 있습니다."
    )
    for app_name in app_names:
        app_df = combined[combined["app_name"] == app_name]
        if app_df.empty:
            st.warning(f"{app_name}: OR 데이터 없음")
            continue
        fig = _or_dot_plot(
            app_df,
            [app_name],
            use_log=use_log,
            title=f"{app_name} — 기능별 오즈비 (OR)",
            all_app_names=app_names,
        )
        st.plotly_chart(fig, use_container_width=True, key=f"or_plot_{app_name}")

    # ── 공통 기능 통합 비교 도트 플롯 ─────────────────────────────────────
    if len(app_names) >= 2:
        st.markdown("### 공통 기능 오즈비 비교 (전 앱)")
        if common_cats:
            common_df = combined[combined["feature_category"].isin(common_cats)]
            st.caption(
                f"모든 앱({', '.join(app_names)})에 공통으로 등장하는 "
                f"{len(common_cats)}개 기능의 OR을 한 차트에서 비교합니다."
            )
            fig_common = _or_dot_plot(
                common_df,
                app_names,
                use_log=use_log,
                title="공통 기능 카테고리별 오즈비 (OR) 비교",
                all_app_names=app_names,
            )
            st.plotly_chart(fig_common, use_container_width=True, key="or_plot_common")
        else:
            st.info("분석 앱 간 공통으로 등장한 기능 카테고리가 없습니다.")

    # ── Insight ────────────────────────────────────────────────────────────
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
            f"유의 기능 <b>{len(sig)}개</b> | "
            f"긍정 연관 1위 → <b>{top['feature_category']}</b> (OR={top['OR']:.2f}): "
            f"언급 시 긍정 평점 {top['OR']:.1f}배. "
            f"부정 연관 1위 → <b>{bot['feature_category']}</b> (OR={bot['OR']:.2f}): "
            f"불만 리뷰와 강하게 연관."
        ))

    render_insight_box(
        "기능 카테고리별 오즈비 (OR) 비교 Insight",
        "각 기능이 긍정/부정 리뷰와 얼마나 연관되는지 통계적으로 측정합니다.",
        f"전체 {len(combined)}개 기능-앱 조합 중 {len(sig_all)}개가 유의(p<0.05). "
        "OR>1 기능을 강화하고, OR<1 기능을 개선하세요.",
        items,
    )

    # ── OR 상세 테이블 (앱별) ──────────────────────────────────────────────
    st.markdown("### 오즈비 상세 테이블")
    tabs = st.tabs(app_names)
    for tab, app_name in zip(tabs, app_names):
        with tab:
            app_df = combined[combined["app_name"] == app_name]
            if app_df.empty:
                st.warning(f"{app_name}: 데이터 없음")
            else:
                _app_or_table(app_df, app_name)

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
    with st.expander("📥 원본 회귀 결과 다운로드", expanded=True):
        for app_name, df_or in or_results.items():
            csv = df_or.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label=f"{app_name} OR 결과 CSV",
                data=csv,
                file_name=f"or_result_{app_name}.csv",
                mime="text/csv",
            )
