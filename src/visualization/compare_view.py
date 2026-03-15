"""
비교 분석 뷰 (PRD 비교 뷰, 2개 이상 앱)

섹션 순서:
1. 리뷰 분포 & 추이 차트 (평점분포 + 월별/일별)
2. VS 헤더 + 앱별 KPI + 앱별 Insight
3. 4종 워드클라우드 + 키워드 표(최대 100개, 8행) + Insight
4. 기능별 OR 비교 차트 + 상세 테이블 + Insight
5. ΔOR 경쟁 우위/열위 차트 + 상세 테이블 + Insight (데이터 부족 안내)
6. 기능 개선 우선순위 매트릭스 + 상세 테이블 + 종합 Insight (데이터 부족 안내)
"""
from __future__ import annotations

import io
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from wordcloud import WordCloud

from config.settings import ASSETS_DIR, WORDCLOUD_MAX_WORDS
from src.analysis.delta_or import get_priority_matrix_df
from src.visualization.tab_priority import _build_scatter
from src.visualization._common import (
    BG, GRID, LINE, TEXT, SUBTEXT,
    apply_dark_theme, centered_title,
    get_ordered_app_names, app_color, app_emoji, render_insight_box,
    APP_COLOR_EMOJIS,
)

_BUNDLED_FONT = ASSETS_DIR / "fonts" / "NanumGothic.ttf"

# 키워드 표 최대 표시 수
_KW_TABLE_MAX = 100
# 키워드 표 기본 노출 행 수
_KW_TABLE_ROWS = 8

# OR 분석 최소 권장 리뷰 수
_MIN_REVIEWS_FOR_OR = 50
_MIN_REVIEWS_STABLE = 100


# ── Font helper ───────────────────────────────────────────────────────────────

def _get_font_path() -> str | None:
    import os
    candidates = [
        str(_BUNDLED_FONT),
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/nanum/NanumGothic.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/System/Library/Fonts/AppleGothic.ttf",
        "/Library/Fonts/AppleGothic.ttf",
        "/opt/homebrew/share/fonts/nanum/NanumGothic.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


# ── Wordcloud helper ──────────────────────────────────────────────────────────

def _make_wordcloud(tokens: list[list[str]], colormap: str = "cool") -> bytes | None:
    counter: Counter = Counter(t for tl in tokens for t in tl)
    if not counter:
        return None
    font_path = _get_font_path()
    kwargs = dict(
        max_words=WORDCLOUD_MAX_WORDS,
        background_color=BG, width=600, height=300,
        colormap=colormap, prefer_horizontal=0.9,
    )
    if font_path:
        kwargs["font_path"] = font_path
    wc = WordCloud(**kwargs)
    wc.generate_from_frequencies(counter)
    fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG)
    ax.set_facecolor(BG)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── 섹션 1: 평점 분포 + 리뷰 추이 ────────────────────────────────────────────

def _score_dist_chart(raw_df: pd.DataFrame, app_names: list[str]) -> go.Figure:
    fig = go.Figure()
    for app_name in app_names:
        app_df = raw_df[raw_df["app_name"] == app_name]
        if "score" not in app_df.columns:
            continue
        score_counts = app_df["score"].value_counts().sort_index()
        color = app_color(app_name, app_names)
        fig.add_trace(go.Bar(
            name=app_name,
            x=score_counts.index.tolist(),
            y=score_counts.values.tolist(),
            marker_color=color,
            hovertemplate=f"<b>{app_name}</b><br>평점: %{{x}}점<br>리뷰 수: %{{y:,}}건<extra></extra>",
        ))
    fig.update_layout(
        title=centered_title("평점별 리뷰 분포"),
        xaxis_title="평점", yaxis_title="리뷰 수",
        barmode="group", height=300,
        margin=dict(l=10, r=10, t=60, b=40),
    )
    apply_dark_theme(fig, centered_legend=True)
    return fig


def _review_trend_chart(raw_df: pd.DataFrame, app_names: list[str], use_daily: bool) -> go.Figure:
    fig = go.Figure()
    date_col = "review_date" if "review_date" in raw_df.columns else "date"
    for app_name in app_names:
        app_df = raw_df[raw_df["app_name"] == app_name].copy()
        if date_col not in app_df.columns:
            continue
        app_df[date_col] = pd.to_datetime(app_df[date_col], errors="coerce")
        app_df = app_df.dropna(subset=[date_col])
        fmt = "%Y-%m-%d" if use_daily else "%Y-%m"
        app_df["period"] = app_df[date_col].dt.strftime(fmt)
        trend = app_df.groupby("period").size().reset_index(name="count").sort_values("period")
        color = app_color(app_name, app_names)
        fig.add_trace(go.Scatter(
            name=app_name,
            x=trend["period"].tolist(),
            y=trend["count"].tolist(),
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(color=color, size=6),
            hovertemplate=f"<b>{app_name}</b><br>기간: %{{x}}<br>리뷰 수: %{{y:,}}건<extra></extra>",
        ))
    label = "일별" if use_daily else "월별"
    fig.update_layout(
        title=centered_title(f"{label} 리뷰 수 추이"),
        xaxis_title="기간", yaxis_title="리뷰 수",
        height=300,
        margin=dict(l=10, r=10, t=60, b=40),
    )
    apply_dark_theme(fig, centered_legend=True)
    return fig


def _render_distribution_section(raw_df: pd.DataFrame, app_names: list[str]) -> None:
    start_date = st.session_state.get("start_date")
    end_date   = st.session_state.get("end_date")
    days_span  = (end_date - start_date).days if start_date and end_date else 30
    use_daily  = days_span < 30

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(_score_dist_chart(raw_df, app_names), use_container_width=True)
    with col2:
        st.plotly_chart(_review_trend_chart(raw_df, app_names, use_daily), use_container_width=True)

    # Insight
    items = []
    for app_name in app_names:
        app_df = raw_df[raw_df["app_name"] == app_name]
        total = len(app_df)
        if total == 0:
            items.append((app_name, app_color(app_name, app_names), "수집된 리뷰가 없습니다."))
            continue
        if "score" not in app_df.columns:
            items.append((app_name, app_color(app_name, app_names), f"총 {total:,}건 (평점 정보 없음)."))
            continue
        neg_n  = int((app_df["score"] <= 2).sum())
        pos_n  = int((app_df["score"] >= 4).sum())
        neg_pct = neg_n / total * 100
        pos_pct = pos_n / total * 100
        # 가장 많이 수집된 월
        if "date" in app_df.columns:
            dates = pd.to_datetime(app_df["date"], errors="coerce").dropna()
            if not dates.empty:
                peak_month = dates.dt.strftime("%Y-%m").value_counts().idxmax()
                peak_cnt   = dates.dt.strftime("%Y-%m").value_counts().max()
                peak_str   = f" 피크: {peak_month}({peak_cnt:,}건)."
            else:
                peak_str = ""
        else:
            peak_str = ""
        items.append((
            app_name, app_color(app_name, app_names),
            f"총 <b>{total:,}건</b> — 긍정 <b style='color:#4FD6A5;'>{pos_pct:.0f}%</b>({pos_n:,}) / "
            f"부정 <b style='color:#FF6B8A;'>{neg_pct:.0f}%</b>({neg_n:,}).{peak_str}",
        ))

    # 종합
    totals = {an: len(raw_df[raw_df["app_name"] == an]) for an in app_names}
    most_reviewed = max(totals, key=totals.get)
    summary = (
        f"가장 많은 리뷰를 보유한 앱: <b>{most_reviewed}</b>({totals[most_reviewed]:,}건). "
        + ("부정 비율이 높은 앱들로 개선 여지가 큽니다." if any(
            (raw_df[raw_df["app_name"] == an]["score"] <= 2).sum() / max(len(raw_df[raw_df["app_name"] == an]), 1) > 0.5
            for an in app_names
        ) else "전반적인 데이터 수집이 완료되었습니다.")
    )
    render_insight_box(
        "리뷰 분포 개요",
        "수집된 리뷰의 평점 분포와 시간 추이를 파악합니다.",
        "데이터 편향 여부와 특정 시점의 이상 급증을 확인할 수 있어요.",
        items,
        summary=summary,
    )


# ── 섹션 2: VS 헤더 + 앱별 KPI ───────────────────────────────────────────────

def _render_vs_kpi_section(raw_df: pd.DataFrame, app_names: list[str]) -> None:
    n = len(app_names)
    start_date = st.session_state.get("start_date")
    end_date   = st.session_state.get("end_date")
    date_str   = ""
    if start_date and end_date:
        days = (end_date - start_date).days
        date_str = f"{start_date.strftime('%y.%m.%d')}~{end_date.strftime('%y.%m.%d')} / {days}일"

    # 컬럼 레이아웃: 앱=5, VS=1, 앱=5 ...
    col_widths = []
    for i in range(n):
        col_widths.append(5)
        if i < n - 1:
            col_widths.append(1)
    vs_cols = st.columns(col_widths)

    for i, app_name in enumerate(app_names):
        color = app_color(app_name, app_names)
        emoji = APP_COLOR_EMOJIS.get(color, "⬜")
        app_df = raw_df[raw_df["app_name"] == app_name] if "app_name" in raw_df.columns else raw_df.iloc[0:0]
        total  = len(app_df)

        n_android = len(app_df[app_df["platform"] == "Google Play Store"]) if "platform" in app_df.columns else 0
        n_ios     = len(app_df[app_df["platform"] == "Apple App Store"])   if "platform" in app_df.columns else 0
        plat_str  = f"Android : {n_android:,} / iOS {n_ios:,}" if n_android + n_ios > 0 else ""

        avg_score = app_df["score"].mean() if "score" in app_df.columns and total > 0 else 0.0
        pos_n  = int((app_df["score"] >= 4).sum()) if "score" in app_df.columns else 0
        neg_n  = int((app_df["score"] <= 2).sum()) if "score" in app_df.columns else 0
        pos_pct = pos_n / total * 100 if total > 0 else 0.0
        neg_pct = neg_n / total * 100 if total > 0 else 0.0

        with vs_cols[i * 2]:
            # 앱 이름 박스
            st.markdown(
                f'<div style="text-align:center;padding:10px;border-radius:8px;'
                f'background:{color}22;border:2px solid {color};margin-bottom:10px;">'
                f'<b style="font-size:1rem;color:{color};">{emoji} {app_name}</b></div>',
                unsafe_allow_html=True,
            )
            # KPI 데이터
            date_part = f" ({date_str})" if date_str else ""
            plat_part = f" ({plat_str})" if plat_str else ""
            st.markdown(
                f'<div style="font-size:0.83rem;color:#CBD5E1;line-height:2.0;'
                f'padding:0.5rem 0.75rem;background:#131820;border-radius:6px;'
                f'border-left:3px solid {color};margin-bottom:8px;">'
                f'<span style="font-size:0.72rem;color:{SUBTEXT};">{date_str}</span><br>'
                f'- 리뷰 수 : <b>{total:,} 건</b>{plat_part}<br>'
                f'- 평균 평점 : <b>{avg_score:.2f} ⭐</b><br>'
                f'- 긍정 리뷰 : <b style="color:#4FD6A5;">{pos_pct:.0f}%</b>'
                f' <span style="color:#94A3B8;">({pos_n:,}건)</span><br>'
                f'- 부정 리뷰 : <b style="color:#FF6B8A;">{neg_pct:.0f}%</b>'
                f' <span style="color:#94A3B8;">({neg_n:,}건)</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # 앱별 Insight (score-level interpretation)
            if total == 0:
                insight_text = "수집된 리뷰가 없어 분석이 불가합니다."
            elif avg_score >= 4.0:
                insight_text = (
                    f"평균 {avg_score:.2f}점으로 전반적으로 긍정적 반응. "
                    f"긍정 비율 {pos_pct:.0f}%로 핵심 강점 유지가 중요합니다."
                )
            elif avg_score >= 3.0:
                insight_text = (
                    f"평균 {avg_score:.2f}점 — 중간 수준. "
                    f"부정 비율 {neg_pct:.0f}%({neg_n:,}건)의 불만 원인 파악이 필요합니다."
                )
            else:
                insight_text = (
                    f"평균 {avg_score:.2f}점 — 낮은 만족도 주의. "
                    f"부정 리뷰가 {neg_pct:.0f}%({neg_n:,}건)로 즉각적인 개선이 필요합니다."
                )
            st.markdown(
                f'<div style="font-size:0.8rem;background:#0F1E14;border-left:3px solid {color};'
                f'border-radius:4px;padding:0.45rem 0.75rem;color:#CBD5E1;">'
                f'<span style="color:{color};font-weight:700;">💡 Insight</span><br>{insight_text}'
                f'</div>',
                unsafe_allow_html=True,
            )

        if i < n - 1:
            with vs_cols[i * 2 + 1]:
                st.markdown(
                    '<div style="text-align:center;padding:40px 0;font-size:1.2rem;'
                    'font-weight:bold;color:#475569;">VS</div>',
                    unsafe_allow_html=True,
                )


# ── 섹션 3: 4종 워드클라우드 ─────────────────────────────────────────────────

_WC_SECTIONS = [
    ("전체 키워드",         None, None, "cool",   "all"),
    ("긍정 키워드 (4~5점)", 4,    6,    "summer", "pos"),
    ("보통 키워드 (3점)",   3,    4,    "autumn", "mid"),
    ("부정 키워드 (1~2점)", 1,    3,    "hot",    "neg"),
]

_WC_PURPOSE = {
    "all": "전체 리뷰에서 가장 많이 언급된 키워드를 파악합니다.",
    "pos": "4~5점 긍정 평가 리뷰에서 자주 등장한 단어를 파악합니다.",
    "mid": "3점 중립 리뷰에서 자주 등장한 단어를 파악합니다.",
    "neg": "1~2점 부정 평가 리뷰에서 자주 등장한 단어를 파악합니다.",
}
_WC_EFFECT = {
    "all": "전반적인 사용자 관심사를 한눈에 볼 수 있어요.",
    "pos": "사용자가 칭찬하는 포인트를 알 수 있어요.",
    "mid": "개선 여지가 있는 중간 평가 영역을 파악할 수 있어요.",
    "neg": "사용자가 불만족하는 핵심 원인을 알 수 있어요.",
}

# 키워드 표 expander 이름 매핑
_WC_TABLE_LABEL = {
    "all": "전체 키워드 표 보기",
    "pos": "긍정 키워드 표 보기",
    "mid": "보통 키워드 표 보기",
    "neg": "부정 키워드 표 보기",
}


def _render_wc_sections(proc: pd.DataFrame, app_names: list[str]) -> None:
    for section_title, score_min, score_max, cmap, key in _WC_SECTIONS:
        st.markdown(f"##### {section_title}")
        wc_cols = st.columns(len(app_names))
        counters: dict[str, Counter] = {}

        for i, app_name in enumerate(app_names):
            sub = proc[proc["app_name"] == app_name] if "app_name" in proc.columns else proc
            if score_min is not None and "score" in sub.columns:
                sub = sub[(sub["score"] >= score_min) & (sub["score"] < score_max)]
            tok_lists = sub["tokens"].tolist() if "tokens" in sub.columns else []
            counters[app_name] = Counter(t for tl in tok_lists for t in tl)
            with wc_cols[i]:
                color = app_color(app_name, app_names)
                st.markdown(
                    f'<div style="font-size:0.80rem;font-weight:700;color:{color};">'
                    f'{app_name}</div>',
                    unsafe_allow_html=True,
                )
                img = _make_wordcloud(tok_lists, colormap=cmap)
                if img:
                    st.image(img, use_container_width=True)
                else:
                    st.caption("데이터 없음")

        # 키워드 표 (section별 이름, 최대 100개, 8행 높이)
        table_h = _KW_TABLE_ROWS * 35 + 38
        with st.expander(f"📊 {_WC_TABLE_LABEL[key]}", expanded=True):
            tcols = st.columns(len(app_names))
            for i, app_name in enumerate(app_names):
                with tcols[i]:
                    cnt = counters[app_name]
                    if cnt:
                        top_df = pd.DataFrame(
                            cnt.most_common(_KW_TABLE_MAX), columns=["키워드", "빈도"]
                        )
                        st.caption(app_name)
                        st.dataframe(top_df, use_container_width=True, height=table_h)
                    else:
                        st.caption(f"{app_name}: 데이터 없음")

        # Insight items
        items = []
        for app_name in app_names:
            cnt = counters[app_name]
            if not cnt:
                items.append((
                    app_name, app_color(app_name, app_names),
                    f"해당 구간({section_title})의 리뷰 데이터가 없습니다. "
                    "리뷰 수집 기간을 늘리거나 더 많은 리뷰가 있는 앱을 선택해주세요.",
                ))
                continue
            top3 = cnt.most_common(3)
            total = sum(cnt.values())
            top3_pct = sum(c for _, c in top3) / total * 100 if total > 0 else 0
            words = " · ".join(f"<b>{w}</b>({c:,})" for w, c in top3)
            items.append((
                app_name, app_color(app_name, app_names),
                f"상위 3개 키워드: {words} — 전체 {total:,}개 중 {top3_pct:.0f}% 차지.",
            ))

        # 종합해석: 앱 간 top 키워드 비교
        all_tops = {an: counters[an].most_common(1)[0][0] for an in app_names if counters[an]}
        if len(all_tops) >= 2:
            top_str = " / ".join(
                f"{app_emoji(an, app_names)}{an}: <b>{w}</b>"
                for an, w in all_tops.items()
            )
            # 공통 top5 키워드 여부 파악
            sets = [set(w for w, _ in counters[an].most_common(5)) for an in app_names if counters[an]]
            common = set.intersection(*sets) if sets else set()
            common_str = f" 공통 상위 키워드: {', '.join(list(common)[:3])}." if common else ""
            summary = f"각 앱 1위 키워드 — {top_str}.{common_str}"
        else:
            summary = None

        render_insight_box(
            section_title,
            _WC_PURPOSE[key],
            _WC_EFFECT[key],
            items,
            summary=summary,
        )
        st.divider()


# ── 섹션 4: OR 비교 ───────────────────────────────────────────────────────────

def _or_dot_plot(combined: pd.DataFrame, app_names: list[str], use_log: bool = False) -> go.Figure:
    fig = go.Figure()

    # 로그 스케일 시 OR=0 방지 (log(0)=-inf)
    plot_combined = combined.copy()
    if use_log:
        plot_combined["OR"]       = plot_combined["OR"].clip(lower=0.01)
        plot_combined["ci_lower"] = plot_combined["ci_lower"].clip(lower=0.01)
        plot_combined["ci_upper"] = plot_combined["ci_upper"].clip(lower=0.01)

    for app_name in app_names:
        app_df = plot_combined[plot_combined["app_name"] == app_name].copy()
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
                f"<b>{app_name}</b><br>기능: %{{y}}<br>OR: %{{x:.3f}}<br>"
                "95% CI: [%{customdata[0]:.3f}, %{customdata[1]:.3f}]<br>"
                "p-value: %{customdata[2]:.4f}<extra></extra>"
            ),
            customdata=app_df[["ci_lower", "ci_upper", "p_value"]].values,
        ))

    vline_x = 1.0
    fig.add_vline(x=vline_x, line_dash="dash", line_color=SUBTEXT, line_width=1.5,
                  annotation_text="OR=1 (기준)", annotation_position="top right",
                  annotation_font_color=SUBTEXT)

    n_cats = len(combined["feature_category"].unique())
    fig.update_layout(
        title=centered_title("기능 카테고리별 오즈비(OR) 비교"),
        xaxis_title="오즈비 (OR, 로그 스케일)" if use_log else "오즈비 (OR)",
        yaxis_title="기능 카테고리",
        height=max(400, n_cats * 35 + 150),
        hovermode="closest",
        # 범례를 차트 하단으로 이동 → 타이틀과 겹침 해소
        margin=dict(l=10, r=10, t=70, b=80),
    )
    apply_dark_theme(fig, centered_legend=False)
    fig.update_layout(legend=dict(
        bgcolor="#131820", bordercolor=LINE, font=dict(color=TEXT),
        orientation="h", yanchor="top", y=-0.08,
        xanchor="center", x=0.5,
    ))
    if use_log:
        fig.update_xaxes(type="log")
    return fig


def _render_or_section(combined_or: pd.DataFrame, app_names: list[str], raw_df: pd.DataFrame) -> None:
    or_names = [n for n in app_names if n in combined_or["app_name"].values]
    if not or_names:
        # OR 데이터 없음 — 부족한 이유 안내
        min_reviews = {
            an: len(raw_df[raw_df["app_name"] == an])
            for an in app_names
        }
        st.markdown(
            '<div class="info-box" style="border-left:4px solid #F59E0B;">'
            '⚠️ <b>OR 분석 결과가 없습니다.</b><br>'
            '로지스틱 회귀분석을 위해서는 앱당 최소 <b>50건 이상</b>(안정적 분석은 100건 이상)의 '
            '긍정·부정 리뷰가 필요합니다.<br>'
            + " | ".join(
                f"<b>{an}</b>: {cnt:,}건"
                + (" ✅" if cnt >= _MIN_REVIEWS_FOR_OR else f" (부족 — {_MIN_REVIEWS_FOR_OR - cnt}건 더 필요)")
                for an, cnt in min_reviews.items()
            )
            + '</div>',
            unsafe_allow_html=True,
        )
        return

    # 누락 OR 탐지 — 일부 앱에만 있는 기능
    all_cats = combined_or["feature_category"].unique()
    missing_info: dict[str, list[str]] = {}
    for an in or_names:
        present = set(combined_or[combined_or["app_name"] == an]["feature_category"].unique())
        missing = sorted(set(all_cats) - present)
        if missing:
            missing_info[an] = missing

    # 로그 스케일 권장 여부 (OR > 5 존재 시)
    max_or = combined_or["OR"].max() if "OR" in combined_or.columns else 0
    suggest_log = max_or > 5

    missing_html = ""
    if missing_info:
        rows = " | ".join(
            f"<b>{an}</b>: {', '.join(cats[:3])}{'…' if len(cats) > 3 else ''} ({len(cats)}개 미표시)"
            for an, cats in missing_info.items()
        )
        missing_html = (
            f'<br>⚠️ <b>일부 기능의 OR이 특정 앱에서 누락됨</b> — {rows}.<br>'
            f'&nbsp;&nbsp;원인: 해당 앱 리뷰에서 기능 키워드가 충분히 등장하지 않아 '
            f'로지스틱 회귀분석이 수렴하지 못했거나, 해당 기능 관련 리뷰 언급 자체가 없는 경우입니다.'
        )

    log_hint = (
        f'<br>📐 <b>OR 최대값({max_or:.1f})이 크게 나타남</b> — 아래 로그 스케일 체크 시 '
        f'값이 큰 기능과 작은 기능의 차이를 동시에 비교할 수 있습니다.'
        if suggest_log else ""
    )

    st.markdown(
        f'<div class="info-box">'
        f'<b>OR &gt; 1</b>: 해당 기능 언급 시 긍정 평점 확률 증가 &nbsp;|&nbsp; '
        f'<b>OR &lt; 1</b>: 부정 리뷰와 더 연관 &nbsp;|&nbsp; <b>오차막대</b>: 95% 신뢰구간'
        f'{log_hint}{missing_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    use_log = False
    if suggest_log:
        use_log = st.checkbox(
            f"📐 로그 스케일 적용 (OR 최대값 {max_or:.1f} — 값 범위가 커서 권장)",
            value=False,
            key="or_log_scale",
        )

    st.plotly_chart(_or_dot_plot(combined_or, or_names, use_log=use_log), use_container_width=True)

    # OR 상세 테이블
    st.markdown("##### 오즈비 상세 테이블")
    disp_cols = ["feature_category", "app_name", "OR", "ci_lower", "ci_upper", "p_value"]
    existing  = [c for c in disp_cols if c in combined_or.columns]
    table_df  = combined_or[existing].copy()
    if "p_value" in table_df.columns:
        def _sig(p):
            return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "n.s."
        table_df["유의성"] = table_df["p_value"].apply(_sig)
    col_rename = {
        "feature_category": "기능 카테고리", "app_name": "앱",
        "OR": "오즈비", "ci_lower": "95% CI 하한", "ci_upper": "95% CI 상한",
        "p_value": "p-value",
    }
    st.dataframe(
        table_df.rename(columns=col_rename).sort_values(["앱", "오즈비"] if "앱" in table_df.rename(columns=col_rename).columns else ["app_name", "OR"], ascending=[True, False]),
        use_container_width=True, height=380,
    )

    # Insight
    items = []
    for app_name in or_names:
        sub = combined_or[combined_or["app_name"] == app_name]
        sig = sub[sub["p_value"] < 0.05] if "p_value" in sub.columns else sub
        if sig.empty:
            items.append((app_name, app_color(app_name, app_names),
                          "통계적으로 유의한 기능이 없습니다 (p≥0.05). "
                          "리뷰 수를 늘리거나 분석 기간을 확대하면 유의성이 나타날 수 있습니다."))
            continue
        top = sig.nlargest(1, "OR").iloc[0]
        bot = sig.nsmallest(1, "OR").iloc[0]
        sig_count = len(sig)
        items.append((
            app_name, app_color(app_name, app_names),
            f"유의 기능 <b>{sig_count}개</b> | "
            f"긍정 1위 → <b>{top['feature_category']}</b> (OR={top['OR']:.2f}): "
            f"언급 시 긍정 평점 {top['OR']:.1f}배. "
            f"부정 1위 → <b>{bot['feature_category']}</b> (OR={bot['OR']:.2f}): "
            f"불만 리뷰와 강하게 연관."
        ))

    or_summary_parts = []
    for an in or_names:
        sub_or = combined_or[combined_or["app_name"] == an]
        sig_or = sub_or[sub_or["p_value"] < 0.05] if "p_value" in sub_or.columns else sub_or
        if not sig_or.empty:
            top_or = sig_or.nlargest(1, "OR").iloc[0]
            or_summary_parts.append(
                f"{app_emoji(an, or_names)}{an} 긍정 1위: <b>{top_or['feature_category']}</b> (OR={top_or['OR']:.2f})"
            )
    or_summary = " / ".join(or_summary_parts) if or_summary_parts else "유의한 결과가 없습니다."

    render_insight_box(
        "기능 카테고리별 오즈비(OR) 비교",
        "각 기능이 긍정/부정 리뷰와 얼마나 연관되는지 오즈비(OR)로 측정합니다.",
        "OR이 클수록 그 기능 언급 시 긍정 평점이 달릴 확률이 높습니다. "
        "OR<1 기능은 불만과 연관되므로 개선 우선순위가 됩니다.",
        items,
        summary=or_summary,
    )


# ── 섹션 5: ΔOR 경쟁 우위/열위 ────────────────────────────────────────────────

def _delta_or_chart(combined: pd.DataFrame, app_names: list[str]) -> go.Figure:
    df_d = combined.dropna(subset=["delta_or"]).copy()
    fig = go.Figure()
    for app_name in app_names[1:]:
        sub = df_d[df_d["app_name"] == app_name].sort_values("delta_or")
        if sub.empty:
            continue
        color = app_color(app_name, app_names)
        fig.add_trace(go.Bar(
            x=sub["delta_or"],
            y=sub["feature_category"],
            orientation="h",
            name=app_name,
            marker=dict(
                color=[("#FF6B8A" if v < 0 else color) for v in sub["delta_or"]],
                line=dict(color=color, width=1),
            ),
            hovertemplate=f"<b>{app_name}</b><br>기능: %{{y}}<br>ΔOR: %{{x:.3f}}<extra></extra>",
        ))
    fig.add_vline(x=0, line_dash="dash", line_color=SUBTEXT)
    fig.update_layout(
        title=centered_title("ΔOR — 기준 앱 대비 경쟁 우위/열위"),
        xaxis_title="ΔOR (양수 = 우위, 음수 = 열위)",
        height=max(350, len(df_d["feature_category"].unique()) * 30 + 120),
        margin=dict(l=10, r=10, t=80, b=40),
        barmode="group",
    )
    apply_dark_theme(fig, centered_legend=True)
    return fig


def _render_delta_section(combined_or: pd.DataFrame, app_names: list[str], raw_df: pd.DataFrame) -> None:
    base_app = app_names[0]

    # ΔOR 데이터 없는 경우
    has_delta = "delta_or" in combined_or.columns and combined_or["delta_or"].notna().any()
    if not has_delta:
        total_by_app = {an: len(raw_df[raw_df["app_name"] == an]) for an in app_names}
        has_or = not combined_or.empty and "OR" in combined_or.columns
        or_apps = combined_or["app_name"].unique().tolist() if has_or else []

        if len(or_apps) < 2:
            msg = (
                "ΔOR 분석을 위해서는 <b>2개 이상</b>의 앱에서 OR이 계산되어야 합니다.<br>"
                "현재 OR이 계산된 앱: "
                + (", ".join(f"<b>{a}</b>" for a in or_apps) if or_apps else "없음")
                + "<br>각 앱당 최소 <b>50건</b> 이상의 긍정·부정 리뷰가 필요합니다. "
                "현재 수집 건수: "
                + " / ".join(f"{an} {cnt:,}건" for an, cnt in total_by_app.items())
            )
        else:
            msg = (
                "ΔOR 계산 데이터가 충분하지 않습니다. "
                "안정적인 비교를 위해 앱당 <b>100건 이상</b>의 리뷰를 권장합니다.<br>"
                "현재 수집 건수: "
                + " / ".join(f"{an} {cnt:,}건" for an, cnt in total_by_app.items())
            )

        st.markdown(
            f'<div class="info-box" style="border-left:4px solid #F59E0B;">'
            f'⚠️ <b>ΔOR 분석 결과가 없습니다.</b><br>{msg}</div>',
            unsafe_allow_html=True,
        )
        return

    st.caption(f"기준 앱: **{base_app}** | ΔOR = 비교 앱 OR − {base_app} OR")
    delta_fig = _delta_or_chart(combined_or, app_names)
    if delta_fig.data:
        st.plotly_chart(delta_fig, use_container_width=True)

    # ΔOR 피벗 테이블
    st.markdown("##### ΔOR 상세 테이블")
    df_d = combined_or.dropna(subset=["delta_or"])[["feature_category", "app_name", "delta_or"]].copy()
    try:
        pivot = df_d.pivot(index="feature_category", columns="app_name", values="delta_or")
        pivot_cols = [n for n in app_names if n in pivot.columns]
        pivot = pivot[pivot_cols]
        st.dataframe(
            pivot.style.background_gradient(cmap="RdYlGn", axis=None),
            use_container_width=True,
        )
    except Exception:
        st.dataframe(df_d, use_container_width=True)

    # Insight
    items = []
    for app_name in app_names[1:]:
        sub = df_d[df_d["app_name"] == app_name]
        if sub.empty:
            items.append((app_name, app_color(app_name, app_names),
                          f"vs {base_app} — ΔOR 데이터 없음."))
            continue
        best  = sub.loc[sub["delta_or"].idxmax()]
        worst = sub.loc[sub["delta_or"].idxmin()]
        pos_count = int((sub["delta_or"] > 0).sum())
        neg_count = int((sub["delta_or"] < 0).sum())
        items.append((
            app_name, app_color(app_name, app_names),
            f"vs <b>{base_app}</b> — "
            f"우위 기능 {pos_count}개 / 열위 기능 {neg_count}개. "
            f"최대 우위: <b>{best['feature_category']}</b> (ΔOR=+{best['delta_or']:.2f}) · "
            f"최대 열위: <b>{worst['feature_category']}</b> (ΔOR={worst['delta_or']:.2f}). "
            f"열위 기능 우선 개선 필요."
        ))

    urgent_list = []
    for an in app_names[1:]:
        sub_d = df_d[df_d["app_name"] == an]
        if not sub_d.empty:
            worst_d = sub_d.loc[sub_d["delta_or"].idxmin()]
            urgent_list.append(
                f"{app_emoji(an, app_names)}{an}: <b>{worst_d['feature_category']}</b> (ΔOR={worst_d['delta_or']:.2f})"
            )
    delta_summary = ("우선 개선 과제 — " + " / ".join(urgent_list)) if urgent_list else None

    render_insight_box(
        "ΔOR 경쟁 우위/열위 분석",
        f"기준 앱({base_app}) 대비 각 앱의 기능별 경쟁력 차이를 ΔOR로 측정합니다.",
        "ΔOR 음수 기능부터 개선하면 기준 앱 대비 경쟁력을 가장 빠르게 높일 수 있어요.",
        items,
        summary=delta_summary,
    )


# ── 섹션 6: 우선순위 매트릭스 ────────────────────────────────────────────────

def _render_priority_section(combined_or: pd.DataFrame, app_names: list[str], raw_df: pd.DataFrame) -> None:
    base_app = app_names[0]
    has_priority = "priority_score" in combined_or.columns and combined_or["priority_score"].notna().any()

    if not has_priority:
        total_by_app = {an: len(raw_df[raw_df["app_name"] == an]) for an in app_names}
        short_apps   = [an for an, cnt in total_by_app.items() if cnt < _MIN_REVIEWS_STABLE]
        st.markdown(
            f'<div class="info-box" style="border-left:4px solid #F59E0B;">'
            f'⚠️ <b>우선순위 매트릭스 데이터가 부족합니다.</b><br>'
            f'매트릭스 계산을 위해서는 ΔOR과 취약도(Vulnerability Score)가 모두 필요합니다.<br>'
            f'권장 조건: 앱당 <b>{_MIN_REVIEWS_STABLE}건 이상</b>의 리뷰, 2개 이상 앱의 OR 계산 완료.<br>'
            f'현재 수집 건수: '
            + " / ".join(f"<b>{an}</b> {cnt:,}건" + (" (부족)" if cnt < _MIN_REVIEWS_STABLE else " ✅") for an, cnt in total_by_app.items())
            + (f"<br>특히 <b>{'  /  '.join(short_apps)}</b>의 리뷰 수를 늘려주세요." if short_apps else "")
            + '</div>',
            unsafe_allow_html=True,
        )
        return

    comp_apps = [a for a in app_names if a != base_app]
    comp_label = " · ".join(comp_apps) if comp_apps else "비교 앱"
    st.markdown(
        f'<div class="info-box">'
        f'<b>기준앱: {base_app}</b> 기준으로 경쟁사({comp_label}) 대비 기능별 경쟁 포지션을 분석합니다.<br>'
        f'<b>X축 ΔOR</b>: 양수(+) = {base_app}이 경쟁사보다 해당 기능 긍정 평가 높음 (경쟁 우위) /'
        f' 음수(-) = {base_app}이 경쟁사보다 낮음 (경쟁 열위)<br>'
        f'<b>Y축 우선순위 점수</b> = 0.6 × |ΔOR| + 0.4 × 취약도 &nbsp;|&nbsp; 높을수록 개선 효과 큼<br>'
        f'<b>취약도</b>: {base_app}의 OR이 1 미만일수록 증가 (부정 리뷰와 더 강하게 연관된 기능)'
        f'</div>',
        unsafe_allow_html=True,
    )

    try:
        matrix_df = get_priority_matrix_df(combined_or, base_app=base_app)
        if matrix_df.empty:
            st.info("매트릭스 계산 결과가 없습니다.")
            return

        matrix_fig = _build_scatter(matrix_df, combined_or, base_app=base_app)
        st.plotly_chart(matrix_fig, use_container_width=True)

        # 우선순위 상세 테이블
        st.markdown(f"##### 기능별 우선순위 상세 테이블 ({base_app} 기준)")
        table_cols = {
            "feature_category": "기능 카테고리",
            "delta_or_mean": f"ΔOR ({base_app} 기준)",
            "or_mean": f"OR ({base_app})",
            "priority_score_max": "우선순위 점수",
        }
        if "vulnerability_score" in matrix_df.columns:
            table_cols["vulnerability_score"] = "취약도"
        disp = matrix_df[[c for c in table_cols if c in matrix_df.columns]].copy()
        disp = disp.sort_values("priority_score_max", ascending=False) if "priority_score_max" in disp.columns else disp
        disp.insert(0, "순위", range(1, len(disp) + 1))
        st.dataframe(
            disp.rename(columns=table_cols),
            use_container_width=True, height=360,
        )

        # 사분면별 기능 분류
        q1 = matrix_df[(matrix_df["delta_or_mean"] < 0) & (matrix_df["priority_score_max"] >= matrix_df["priority_score_max"].median())]  # 경쟁 열위 & 개선 시급
        q2 = matrix_df[(matrix_df["delta_or_mean"] >= 0) & (matrix_df["priority_score_max"] >= matrix_df["priority_score_max"].median())]  # 경쟁 우위 유지
        q3 = matrix_df[(matrix_df["delta_or_mean"] < 0) & (matrix_df["priority_score_max"] < matrix_df["priority_score_max"].median())]   # 산업 공통 문제
        q4 = matrix_df[(matrix_df["delta_or_mean"] >= 0) & (matrix_df["priority_score_max"] < matrix_df["priority_score_max"].median())]  # 현상 유지

        def _cat_list(df: pd.DataFrame, n: int = 3) -> str:
            return ", ".join(f"<b>{r['feature_category']}</b>" for _, r in df.head(n).iterrows()) or "없음"

        # 앱별 Insight: 기준앱 + 경쟁앱
        app_items = []
        base_color = app_color(base_app, app_names)
        app_items.append((
            base_app, base_color,
            f"기준앱 기준 전체 <b>{len(matrix_df)}</b>개 기능 평가. "
            f"경쟁 열위 & 개선 시급({len(q1)}개): {_cat_list(q1)}. "
            f"경쟁 우위 유지({len(q2)}개): {_cat_list(q2)}. "
            f"산업 공통 문제({len(q3)}개): {_cat_list(q3)}."
        ))
        for app_name in comp_apps:
            color = app_color(app_name, app_names)
            sub_or = combined_or[combined_or["app_name"] == app_name] if not combined_or.empty else pd.DataFrame()
            if "OR" in sub_or.columns and not sub_or.empty:
                top_adv = sub_or[sub_or.get("delta_or", pd.Series(dtype=float)) > 0].nlargest(1, "OR") if "delta_or" in sub_or.columns else pd.DataFrame()
                adv_str = f"경쟁 우위 기능: <b>{top_adv.iloc[0]['feature_category']}</b> (OR={top_adv.iloc[0]['OR']:.2f})" if not top_adv.empty else ""
                app_items.append((
                    app_name, color,
                    f"대비 앱 — {adv_str if adv_str else '유의미한 경쟁 우위 기능 없음'}. "
                    f"{base_app}의 경쟁 열위 분석에 활용된 비교 앱입니다."
                ))
            else:
                app_items.append((app_name, color, "OR 데이터 부족으로 상세 비교 불가."))

        summary = (
            f"<b>{base_app}</b>의 즉시 개선 영역(경쟁 열위 & 우선순위 높음): {_cat_list(q1, 5)}. "
            f"경쟁 우위 유지 영역: {_cat_list(q2, 3)}. "
            f"산업 공통 문제(경쟁사도 함께 약함): {_cat_list(q3, 3)}. "
            f"좌상단 기능을 우선 개선하면 경쟁력 및 사용자 만족도를 동시에 높일 수 있습니다."
        )

        render_insight_box(
            f"기능 개선 우선순위 매트릭스 ({base_app} 기준)",
            f"기준앱({base_app})의 OR과 경쟁사 평균 OR의 차이(ΔOR)와 취약도를 결합해 "
            f"기능별 개선 우선순위를 산출합니다. ΔOR > 0이면 {base_app} 경쟁 우위, < 0이면 경쟁 열위.",
            f"<b>좌상단(경쟁 열위 & 개선 시급)</b>: {base_app}이 경쟁사보다 약하면서 우선순위가 높은 기능 — 즉시 개선 효과 최대. "
            f"<b>우상단(경쟁 우위 유지)</b>: 강점을 유지하며 현 수준을 고수할 영역. "
            f"<b>좌하단(산업 공통 문제)</b>: 경쟁사도 함께 약한 기능 — 업계 전반적 개선 여지. "
            f"<b>우하단(현상 유지)</b>: {base_app}이 강하지만 상대적 중요도 낮음.",
            app_items,
            summary=summary,
        )

    except Exception as e:
        st.caption(f"우선순위 매트릭스 오류: {e}")


# ── Main render ───────────────────────────────────────────────────────────────

def render(
    raw_df: pd.DataFrame,
    processed_df: pd.DataFrame,
    or_results: dict[str, pd.DataFrame],
    combined_or: pd.DataFrame,
) -> None:
    if raw_df.empty:
        st.warning("비교 분석 데이터가 없습니다.")
        return

    app_names = get_ordered_app_names(raw_df)
    if len(app_names) < 2:
        st.warning("비교 분석에는 최소 2개 앱의 데이터가 필요합니다.")
        return

    def _to_list(v):
        if isinstance(v, list): return v
        if isinstance(v, str):  return v.split() if v else []
        return []

    proc = processed_df.copy()
    proc["tokens"] = (
        proc["tokens"].apply(_to_list) if "tokens" in proc.columns
        else pd.Series([[] for _ in range(len(proc))])
    )

    # ── 섹션 1: 리뷰 분포 개요 ──────────────────────────────────────────────
    st.markdown("### 앱 비교 분석")
    _render_distribution_section(raw_df, app_names)

    # ── 섹션 2: VS 헤더 + 앱별 KPI ──────────────────────────────────────────
    st.divider()
    _render_vs_kpi_section(raw_df, app_names)

    # ── 섹션 3: 4종 워드클라우드 ────────────────────────────────────────────
    st.divider()
    st.markdown("#### 키워드 워드클라우드 비교")
    _render_wc_sections(proc, app_names)

    # ── 섹션 4: OR 비교 ─────────────────────────────────────────────────────
    st.markdown("#### 기능별 오즈비(OR) 비교")
    _render_or_section(combined_or, app_names, raw_df)

    # ── 섹션 5: ΔOR 경쟁 우위/열위 ──────────────────────────────────────────
    st.divider()
    st.markdown("#### ΔOR — 경쟁 우위/열위 분석")
    _render_delta_section(combined_or, app_names, raw_df)

    # ── 섹션 6: 우선순위 매트릭스 ───────────────────────────────────────────
    st.divider()
    st.markdown("#### 기능 개선 우선순위 매트릭스")
    _render_priority_section(combined_or, app_names, raw_df)

    # ── 결과 다운로드 ────────────────────────────────────────────────────────
    st.divider()
    if not combined_or.empty:
        csv = combined_or.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 분석 결과 전체 CSV 다운로드",
            data=csv,
            file_name="compare_analysis_result.csv",
            mime="text/csv",
        )
