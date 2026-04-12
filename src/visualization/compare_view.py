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
from src.visualization.tab_priority import _build_scatter, _build_center_zoom, _AREA_STYLE, _AREA_ORDER
from src.visualization._common import (
    BG, GRID, LINE, TEXT, SUBTEXT,
    apply_dark_theme, centered_title,
    get_ordered_app_names, app_color, render_insight_box,
    app_icon_html,
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

    st.markdown(f"""
    <div class="info-box" style="background:#131820;border-left:4px solid #4F8EF7;border-radius:6px;padding:0.7rem 1rem;margin-bottom:0.7rem;font-size:0.82rem;color:#94A3B8;">
    <b style="color:#93C5FD;">이 차트들은 무엇을 보여주나요?</b><br>
    &bull; <b>평점별 리뷰 분포 (좌)</b>: 각 앱의 1~5점 리뷰가 어떻게 분포하는지 비교합니다.
    5점 리뷰가 압도적으로 많은 앱은 충성 사용자층이 두텁거나 긍정 리뷰 유도 정책이 있을 수 있으므로 분포 전체를 함께 살펴야 합니다.
    1~2점 비율이 높은 앱은 즉각적인 UX·기능 개선이 필요합니다.<br>
    &bull; <b>{'일별' if use_daily else '월별'} 리뷰 수 추이 (우)</b>: 리뷰 수의 시간 흐름을 파악합니다.
    특정 시점에 급증한 리뷰는 앱 업데이트, 마케팅 캠페인, 또는 장애 이벤트와 연결된 경우가 많습니다.
    비교 앱 간 수집 기간·수량 격차가 클 경우 OR 분석 결과의 신뢰도 차이가 발생할 수 있습니다.
    </div>
    """, unsafe_allow_html=True)

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

    # 평균 평점 비교 (점수 기준 정렬)
    avg_scores = {}
    for an in app_names:
        sub = raw_df[raw_df["app_name"] == an]
        avg_scores[an] = sub["score"].mean() if "score" in sub.columns and len(sub) > 0 else 0.0
    best_rated = max(avg_scores, key=avg_scores.get)
    worst_rated = min(avg_scores, key=avg_scores.get)

    # 부정 비율 경고 앱
    high_neg_apps = [
        an for an in app_names
        if "score" in raw_df.columns and
        (raw_df[raw_df["app_name"] == an]["score"] <= 2).sum() / max(totals[an], 1) > 0.3
    ]

    summary_parts = [
        f"리뷰 수 1위: <b>{most_reviewed}</b>({totals[most_reviewed]:,}건) — OR 분석 신뢰도 가장 높음.",
        f"평균 평점 1위: <b>{best_rated}</b>({avg_scores[best_rated]:.2f}점) / "
        f"최저: <b>{worst_rated}</b>({avg_scores[worst_rated]:.2f}점).",
    ]
    if high_neg_apps:
        summary_parts.append(
            f"부정 비율 30% 초과 앱: <b>{'  /  '.join(high_neg_apps)}</b> — 즉각적인 개선 검토 필요."
        )
    else:
        summary_parts.append("전체적으로 부정 비율이 30% 미만 — 기본 데이터 품질은 양호합니다.")

    render_insight_box(
        "리뷰 분포 개요",
        "수집된 리뷰의 평점 분포와 시간 추이를 파악해 데이터 품질과 앱별 사용자 반응의 전반적 수준을 점검합니다.",
        "리뷰 수가 적거나 특정 평점에 편중된 앱은 이후 OR·ΔOR 분석 결과의 신뢰도가 낮을 수 있으니 "
        "표본 크기를 함께 고려하세요.",
        items,
        summary=" ".join(summary_parts),
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
        icon_img = app_icon_html(app_name, size=22, color=color)
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
                f'<b style="font-size:1rem;color:{color};">{icon_img} {app_name}</b></div>',
                unsafe_allow_html=True,
            )
            # KPI 데이터
            plat_part = f" ({plat_str})" if plat_str else ""
            avg_label = "양호" if avg_score >= 4.0 else ("중립" if avg_score >= 3.0 else "개선 필요")
            st.markdown(
                f'<div style="font-size:0.83rem;color:#CBD5E1;line-height:2.0;'
                f'padding:0.5rem 0.75rem;background:#131820;border-radius:6px;'
                f'border-left:3px solid {color};margin-bottom:8px;">'
                f'<span style="font-size:0.72rem;color:{SUBTEXT};">{date_str}</span><br>'
                f'- 리뷰 수 : <b>{total:,} 건</b>{plat_part}<br>'
                f'- 평균 평점 : <b>{avg_score:.2f} ⭐</b>'
                f' <span style="font-size:0.72rem;color:{SUBTEXT};">({avg_label})</span><br>'
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


# ── 섹션 2-B: 긍정/부정 비율 도넛 차트 ──────────────────────────────────────

def _render_sentiment_donut(raw_df: pd.DataFrame, app_names: list[str]) -> None:
    """앱별 긍정/부정/보통 비율 도넛 차트 (분석 Summary에 노출)"""
    if raw_df.empty or "score" not in raw_df.columns:
        return

    st.markdown("#### 긍정/부정 비율")
    cols = st.columns(max(1, len(app_names)))
    for i, app_name in enumerate(app_names):
        sub = raw_df[raw_df["app_name"] == app_name]
        if sub.empty:
            continue
        pos = int((sub["score"] >= 4).sum())
        neu = int((sub["score"] == 3).sum())
        neg = int((sub["score"] <= 2).sum())
        total = pos + neu + neg
        color = app_color(app_name, app_names)

        with cols[i]:
            fig = go.Figure(go.Pie(
                labels=["긍정(4~5점)", "보통(3점)", "부정(1~2점)"],
                values=[pos, neu, neg],
                hole=0.52,
                marker_colors=["#10B981", "#F59E0B", "#EF4444"],
                hovertemplate="<b>%{label}</b><br>%{value:,}건 (%{percent})<extra></extra>",
                textinfo="percent",
                textfont=dict(size=11),
            ))
            neg_pct = neg / total * 100 if total > 0 else 0
            badge = "⚠️ 주의" if neg_pct > 65 else "✅ 양호"
            fig.update_layout(
                title=dict(
                    text=f"<b style='color:{color};'>{app_name}</b>  {badge}",
                    font=dict(color=TEXT, size=12),
                    x=0.5, xanchor="center",
                ),
                height=260,
                plot_bgcolor=BG, paper_bgcolor=BG,
                font=dict(color=TEXT),
                legend=dict(bgcolor="#131820", bordercolor=LINE, font=dict(color=TEXT, size=10)),
                margin=dict(l=10, r=10, t=50, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)


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
                f"{app_icon_html(an, size=14, color=app_color(an, app_names))}<b style='color:{app_color(an, app_names)};'>{an}</b>: <b>{w}</b>"
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

def _or_dot_plot(
    combined: pd.DataFrame,
    app_names: list[str],
    use_log: bool = False,
    title: str = "기능 카테고리별 오즈비(OR) 비교",
    all_app_names: list[str] | None = None,
) -> go.Figure:
    """오즈비 도트 플롯.

    Parameters
    ----------
    combined : 플롯할 데이터 (app_name 필터 이미 적용된 상태여도 됨)
    app_names : 이 플롯에 표시할 앱 이름 목록
    use_log : 로그 스케일 여부
    title : 차트 제목
    all_app_names : 전체 앱 목록 (색상 일관성 유지용). None이면 app_names 사용
    """
    if all_app_names is None:
        all_app_names = app_names

    fig = go.Figure()

    # 로그 스케일 시 OR=0 방지 (log(0)=-inf)
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

        # 유의/비유의 분리
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
                    f"<b>{app_name}</b><br>기능: %{{y}}<br>OR: %{{x:.3f}}<br>"
                    "95% CI: [%{customdata[0]:.3f}, %{customdata[1]:.3f}]<br>"
                    "p-value: %{customdata[2]:.4f}<extra></extra>"
                ),
                customdata=sig_df[["ci_lower", "ci_upper", "p_value"]].values,
            ))

        # ── 비유의 (p≥0.05): 점선 CI + 빈 마커 ──────────────────────────────
        if not nsig_df.empty:
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
                    f"<b>{app_name}</b> (n.s.)<br>기능: %{{y}}<br>OR: %{{x:.3f}}<br>"
                    "95% CI: [%{customdata[0]:.3f}, %{customdata[1]:.3f}]<br>"
                    "p-value: %{customdata[2]:.4f}<extra></extra>"
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
        margin=dict(l=240, r=10, t=70, b=80),
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


def _render_or_section(
    combined_or: pd.DataFrame,
    app_names: list[str],
    raw_df: pd.DataFrame,
    or_results: dict[str, pd.DataFrame] | None = None,
) -> None:
    # or_results에 있지만 combined_or에 없는 앱 데이터 보완
    combined_or = combined_or.copy() if not combined_or.empty else pd.DataFrame()
    if or_results:
        for _app, _df in or_results.items():
            if _df.empty:
                continue
            already = (not combined_or.empty and "app_name" in combined_or.columns
                       and _app in combined_or["app_name"].values)
            if not already:
                extra = _df.copy()
                extra["app_name"] = _app
                combined_or = pd.concat([combined_or, extra], ignore_index=True) if not combined_or.empty else extra

    or_names = [n for n in app_names if not combined_or.empty and n in combined_or["app_name"].values]
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

    with st.expander("📐 분석 방법론 — OR 계산 방식 안내", expanded=True):
        st.markdown("""
        #### 왜 두 가지 분석 방법을 사용하나요?

        | 언급 리뷰 수 | 적용 방법 | 이유 |
        |---|---|---|
        | **10건 이상** | 로지스틱 회귀 (Logistic Regression) | 충분한 표본 → 통제변수(리뷰 길이·업데이트 여부) 포함, 다변량 추정 |
        | **2~9건** | 피셔 정확검정 (Fisher's Exact Test) | 소표본 → 로지스틱 회귀 수렴 불가, 역학 연구 표준 방법으로 대체 |

        앱 리뷰에서는 특정 기능을 직접 언급하는 리뷰 수가 적은 경우가 흔합니다.
        이때 로지스틱 회귀는 모델 수렴 실패 또는 완전 분리 문제(언급 리뷰가 모두 긍정/부정)로
        결과를 내지 못합니다. **피셔 정확검정**은 2×2 분할표 기반으로 소표본에서도
        정확한 OR·p-value를 계산하며, Haldane-Anscombe 보정(빈 셀 +0.5)을 적용합니다.

        > ⚠️ 피셔 검정 OR은 통제변수가 미포함되므로 로지스틱 회귀 OR과 직접 수치 비교 시 유의해야 합니다.
        > 상세 테이블의 **분석방법** 컬럼에서 각 카테고리의 적용 방법을 확인할 수 있습니다.
        """)

    use_log = suggest_log  # 극단값 존재 시 기본으로 로그 스케일 적용
    if suggest_log:
        use_log = st.checkbox(
            f"📐 로그 스케일 적용 (OR 최대값 {max_or:.1f} — 값 범위가 커서 자동 활성화)",
            value=True,
            key="or_log_scale",
        )

    # ── 공통 feature_category 계산 ─────────────────────────────────────────
    per_app_cats = [
        set(combined_or[combined_or["app_name"] == an]["feature_category"].unique())
        for an in or_names
    ]
    common_cats: set[str] = per_app_cats[0].intersection(*per_app_cats[1:]) if len(per_app_cats) > 1 else per_app_cats[0]

    # ── 앱별 개별 도트 플롯 (1×1 배열) ────────────────────────────────────
    st.markdown("##### 앱별 오즈비 (OR) 비교")
    st.caption(
        f"각 앱의 기능별 OR을 독립적으로 표시합니다. "
        f"아래 '공통 기능 비교' 차트에서 {len(or_names)}개 앱을 한눈에 비교할 수 있습니다."
    )
    for app_name in or_names:
        app_df = combined_or[combined_or["app_name"] == app_name]
        if app_df.empty:
            st.warning(f"{app_name}: OR 데이터 없음")
            continue
        st.plotly_chart(
            _or_dot_plot(
                app_df, [app_name], use_log=use_log,
                title=f"{app_name} — 기능별 오즈비 (OR)",
                all_app_names=or_names,
            ),
            use_container_width=True,
            key=f"cv_or_plot_{app_name}",
        )

    # ── 공통 기능 통합 비교 도트 플롯 ─────────────────────────────────────
    if len(or_names) >= 2:
        st.markdown("##### 공통 기능 오즈비 비교 (전 앱)")
        if common_cats:
            common_df = combined_or[combined_or["feature_category"].isin(common_cats)]
            st.caption(
                f"모든 앱({', '.join(or_names)})에 공통으로 등장하는 "
                f"{len(common_cats)}개 기능의 OR을 한 차트에서 비교합니다."
            )
            st.plotly_chart(
                _or_dot_plot(
                    common_df, or_names, use_log=use_log,
                    title="공통 기능 카테고리별 오즈비 (OR) 비교",
                    all_app_names=or_names,
                ),
                use_container_width=True,
                key="cv_or_plot_common",
            )
        else:
            st.info("분석 앱 간 공통으로 등장한 기능 카테고리가 없습니다.")

    # ── OR 상세 테이블 (앱별 탭) ──────────────────────────────────────────
    st.markdown("##### 오즈비 상세 테이블")
    disp_cols = ["feature_category", "OR", "ci_lower", "ci_upper", "p_value"]

    def _sig(p: float) -> str:
        return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "n.s."

    col_rename = {
        "feature_category": "기능 카테고리",
        "OR": "오즈비", "ci_lower": "95% CI 하한", "ci_upper": "95% CI 상한",
        "p_value": "p-value",
    }
    tabs = st.tabs(or_names)
    for tab, app_name in zip(tabs, or_names):
        with tab:
            app_df = combined_or[combined_or["app_name"] == app_name]
            if app_df.empty:
                st.warning(f"{app_name}: 데이터 없음")
                continue
            existing = [c for c in disp_cols if c in app_df.columns]
            tdf = app_df[existing].copy().sort_values("OR", ascending=False)
            if "p_value" in tdf.columns:
                tdf["유의성"] = tdf["p_value"].apply(_sig)
            st.dataframe(tdf.rename(columns=col_rename), use_container_width=True, height=360)

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
                f"{app_icon_html(an, size=14, color=app_color(an, or_names))}<b style='color:{app_color(an, or_names)};'>{an}</b> 긍정 1위: <b>{top_or['feature_category']}</b> (OR={top_or['OR']:.2f})"
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

_DELTA_CLIP_THRESHOLD = 5.0   # |ΔOR| > 이 값이면 x축 클리핑


def _hex_rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB hex color to rgba(r,g,b,alpha) string."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _delta_or_chart(combined: pd.DataFrame, app_names: list[str]) -> go.Figure:
    df_d = combined.dropna(subset=["delta_or"]).copy()
    fig = go.Figure()

    # 극단값 탐지 → x축 클리핑 범위 결정
    abs_max = df_d["delta_or"].abs().max() if not df_d.empty else 1.0
    clip = (
        float(df_d["delta_or"].abs().quantile(0.90)) * 1.2
        if abs_max > _DELTA_CLIP_THRESHOLD
        else abs_max
    )
    clip = max(clip, 0.5)
    do_clip = abs_max > _DELTA_CLIP_THRESHOLD

    for app_name in app_names:
        sub = df_d[df_d["app_name"] == app_name].sort_values("delta_or")
        if sub.empty:
            continue
        color = app_color(app_name, app_names)

        # 클리핑된 값: 실제값 표시는 hover 및 텍스트로, 막대 길이는 clip으로 제한
        x_display = sub["delta_or"].clip(-clip, clip)
        clipped_mask = sub["delta_or"].abs() > clip

        texts = [
            f"{'▶' if v > clip else '◀'} {sub['delta_or'].iloc[i]:.2f}"
            if clipped_mask.iloc[i]
            else f"{v:.2f}"
            for i, v in enumerate(x_display)
        ]

        bar_colors = [
            _hex_rgba(color, 0.45) if v < 0 else _hex_rgba(color, 0.90)
            for v in sub["delta_or"]
        ]
        fig.add_trace(go.Bar(
            x=x_display,
            y=sub["feature_category"],
            orientation="h",
            name=app_name,
            text=texts,
            textposition="outside",
            textfont=dict(size=9, color=TEXT),
            marker=dict(
                color=bar_colors,
                line=dict(color=color, width=0.8),
            ),
            hovertemplate=(
                f"<b>{app_name}</b><br>기능: %{{y}}<br>"
                "실제 ΔOR: %{customdata:.3f}<extra></extra>"
            ),
            customdata=sub["delta_or"],
        ))

    fig.add_vline(x=0, line_dash="dash", line_color=SUBTEXT, line_width=1.5)

    n_cats = len(df_d["feature_category"].unique())
    clip_note = f" (극단값 클리핑: ±{clip:.1f})" if do_clip else ""
    fig.update_layout(
        title=centered_title("ΔOR — 기준 앱 대비 경쟁 우위/열위"),
        xaxis_title=f"ΔOR (양수 = 기준앱 우위, 음수 = 기준앱 열위){clip_note}",
        height=max(400, n_cats * 32 + 150),
        margin=dict(l=10, r=80, t=70, b=80),
        barmode="group",
        bargap=0.3,
        bargroupgap=0.1,
    )
    apply_dark_theme(fig, centered_legend=False)
    fig.update_layout(showlegend=False)
    if do_clip:
        fig.update_xaxes(range=[-clip * 1.5, clip * 1.5])
    return fig


def _render_delta_section(combined_or: pd.DataFrame, app_names: list[str], raw_df: pd.DataFrame) -> None:
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

    # 기준앱 = 사용자가 첫 번째로 선택한 앱 (app_names는 선택 순서 유지)
    base_app = app_names[0]
    comp_apps = [an for an in app_names if an != base_app]

    st.caption(f"기준 앱: **{base_app}** | ΔOR = 비교 앱 OR − {base_app} OR")
    delta_fig = _delta_or_chart(combined_or, app_names)
    if delta_fig.data:
        st.plotly_chart(delta_fig, use_container_width=True)
        # 커스텀 아이콘 범례
        legend_parts = []
        for an in app_names:
            color = app_color(an, app_names)
            icon = app_icon_html(an, size=18, color=color)
            legend_parts.append(
                f'<span style="display:inline-flex;align-items:center;gap:5px;margin:0 12px;">'
                f'{icon}<span style="color:{color};font-size:0.82rem;">{an}</span></span>'
            )
        st.markdown(
            f'<div style="text-align:center;margin-top:-8px;margin-bottom:8px;">{"".join(legend_parts)}</div>',
            unsafe_allow_html=True,
        )

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

    # Insight — 비교 앱들만 표시
    items = []
    for app_name in comp_apps:
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
    for an in comp_apps:
        sub_d = df_d[df_d["app_name"] == an]
        if not sub_d.empty:
            worst_d = sub_d.loc[sub_d["delta_or"].idxmin()]
            urgent_list.append(
                f"{app_icon_html(an, size=14, color=app_color(an, app_names))}<b style='color:{app_color(an, app_names)};'>{an}</b>: <b>{worst_d['feature_category']}</b> (ΔOR={worst_d['delta_or']:.2f})"
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

        # ── 사분면 분류 헬퍼 ──────────────────────────────────────────────────
        y_mid = matrix_df["priority_score_max"].median()

        def _area(delta_or: float, score: float) -> str:
            if delta_or < 0 and score >= y_mid:  return "경쟁 열위 · 개선 시급"
            if delta_or >= 0 and score >= y_mid: return "경쟁 우위 유지"
            if delta_or < 0 and score < y_mid:   return "산업 공통 문제"
            return "현상 유지"

        def _action(area: str) -> str:
            return {
                "경쟁 열위 · 개선 시급": "개선 우선 검토",
                "경쟁 우위 유지":        "강점 유지",
                "산업 공통 문제":        "모니터링",
                "현상 유지":             "현 수준 유지",
            }.get(area, "검토")

        # ── 메인 산점도 ───────────────────────────────────────────────────────
        matrix_fig = _build_scatter(matrix_df, combined_or, base_app=base_app)
        st.plotly_chart(matrix_fig, use_container_width=True)

        # ── 중앙 구간 확대 보조 차트 ──────────────────────────────────────────
        zoom_limit = float(max(
            min(matrix_df["delta_or_mean"].abs().quantile(0.80), 1.5), 0.8
        ))
        fig_zoom = _build_center_zoom(
            matrix_df, combined_or, base_app=base_app, zoom_limit=zoom_limit,
        )
        if fig_zoom is not None:
            st.markdown(
                f'<div style="font-size:0.78rem;color:#64748B;margin-top:-0.5rem;margin-bottom:0.3rem;">'
                f'▼ 중앙 밀집 구간 확대 — |ΔOR| ≤ {zoom_limit:.1f} 범위를 선형 스케일로 표시합니다.'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(fig_zoom, use_container_width=True)

        # ── 전략 우선도 상세 테이블 ───────────────────────────────────────────
        st.markdown(f"#### 기능별 전략 우선도 상세 테이블 ({base_app} 기준)")
        st.markdown(f"""
        <div class="info-box">
        본 표의 <b>전략 우선도</b>는 개선이 필요한 기능과 경쟁 우위 유지 기능을 함께 포함한 종합 우선도입니다.<br>
        <b>ΔOR &gt; 0</b> = {base_app} 경쟁 우위 (→ <span style="color:#4FD6A5">강점 유지</span>) &nbsp;/&nbsp;
        <b>ΔOR &lt; 0</b> = {base_app} 경쟁 열위 (→ <span style="color:#FF8A9A">개선 우선 검토</span>)
        </div>
        """, unsafe_allow_html=True)

        tbl = matrix_df.copy()
        tbl["영역"]      = tbl.apply(lambda r: _area(r["delta_or_mean"], r["priority_score_max"]), axis=1)
        tbl["권장 액션"] = tbl["영역"].map(_action)
        tbl["_area_order"] = tbl["영역"].map(_AREA_ORDER).fillna(9)
        tbl = tbl.sort_values(
            ["_area_order", "priority_score_max"], ascending=[True, False]
        ).reset_index(drop=True)
        tbl.index = tbl.index + 1

        def _badge(text: str, area: str) -> str:
            tc, bg = _AREA_STYLE.get(area, ("#94A3B8", "rgba(100,116,139,0.2)"))
            return (
                f'<span style="background:{bg};color:{tc};padding:2px 9px;'
                f'border-radius:99px;font-size:0.73rem;font-weight:700;'
                f'white-space:nowrap;">{text}</span>'
            )

        right_cols = {f"ΔOR ({base_app} 기준)", f"OR ({base_app})", "전략 우선도 점수"}
        header_cols = ["전략 우선도", "기능 카테고리",
                       f"ΔOR ({base_app} 기준)", f"OR ({base_app})", "전략 우선도 점수", "권장 액션"]

        area_order_list = sorted(_AREA_ORDER.keys(), key=lambda a: _AREA_ORDER[a])

        for area_name in area_order_list:
            area_tbl = tbl[tbl["영역"] == area_name]
            if area_tbl.empty:
                continue

            tc, bg = _AREA_STYLE.get(area_name, ("#94A3B8", "rgba(100,116,139,0.15)"))

            # 영역 타이틀
            st.markdown(
                f'<div style="margin-top:1.4rem;margin-bottom:0.4rem;">'
                f'<span style="background:{bg};color:{tc};padding:4px 14px;'
                f'border-radius:6px 6px 0 0;font-size:0.82rem;font-weight:700;'
                f'letter-spacing:0.03em;">▪ {area_name}</span></div>',
                unsafe_allow_html=True,
            )

            # 컬럼 헤더 (검정 배경)
            header = (
                '<thead><tr>'
                + "".join(
                    f'<th style="position:sticky;top:0;z-index:10;background:#000000;'
                    f'padding:8px 12px;text-align:{"right" if h in right_cols else "left"};'
                    f'font-size:0.78rem;color:#94A3B8;font-weight:600;white-space:nowrap;'
                    f'border-bottom:1px solid rgba(255,255,255,0.12);">{h}</th>'
                    for h in header_cols
                )
                + "</tr></thead>"
            )

            rows = ""
            for seq, (rank, row) in enumerate(area_tbl.iterrows(), start=1):
                action      = row["권장 액션"]
                delta       = row["delta_or_mean"]
                or_v        = row["or_mean"]
                score       = row["priority_score_max"]
                delta_color = "#4FD6A5" if delta >= 0 else "#FF8A9A"
                row_bg      = "rgba(255,255,255,0.025)" if seq % 2 == 0 else "transparent"
                rows += (
                    f'<tr style="background:{row_bg};border-bottom:1px solid rgba(255,255,255,0.04);">'
                    f'<td style="padding:7px 12px;text-align:center;font-size:0.8rem;color:#64748B;">{rank}</td>'
                    f'<td style="padding:7px 12px;font-size:0.82rem;color:#E2E8F0;">{row["feature_category"]}</td>'
                    f'<td style="padding:7px 12px;text-align:right;font-size:0.82rem;'
                    f'color:{delta_color};font-weight:600;">{delta:+.4f}</td>'
                    f'<td style="padding:7px 12px;text-align:right;font-size:0.82rem;color:#CBD5E1;">{or_v:.4f}</td>'
                    f'<td style="padding:7px 12px;text-align:right;font-size:0.82rem;'
                    f'color:#E2E8F0;font-weight:600;">{score:.4f}</td>'
                    f'<td style="padding:7px 10px;">{_badge(action, area_name)}</td>'
                    f'</tr>'
                )

            st.markdown(
                '<div style="overflow-y:auto;border-radius:0 6px 6px 6px;'
                f'border:1px solid {tc}33;margin-bottom:0.5rem;">'
                '<table style="width:100%;border-collapse:collapse;">'
                f'{header}<tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True,
            )

        # ── 사분면별 기능 분류 (Insight용) ────────────────────────────────────
        q1 = tbl[tbl["영역"] == "경쟁 열위 · 개선 시급"]
        q2 = tbl[tbl["영역"] == "경쟁 우위 유지"]
        q3 = tbl[tbl["영역"] == "산업 공통 문제"]
        q4 = tbl[tbl["영역"] == "현상 유지"]

        def _cat_list(sub: pd.DataFrame, n: int = 3) -> str:
            return ", ".join(f"<b>{r['feature_category']}</b>" for _, r in sub.head(n).iterrows()) or "없음"

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
                adv_str = (
                    f"경쟁 우위 기능: <b>{top_adv.iloc[0]['feature_category']}</b> (OR={top_adv.iloc[0]['OR']:.2f})"
                    if not top_adv.empty else ""
                )
                app_items.append((
                    app_name, color,
                    f"대비 앱 — {adv_str if adv_str else '유의미한 경쟁 우위 기능 없음'}. "
                    f"{base_app}의 경쟁 열위 분석에 활용된 비교 앱입니다."
                ))
            else:
                app_items.append((app_name, color, "OR 데이터 부족으로 상세 비교 불가."))

        render_insight_box(
            f"기능별 전략 우선도 매트릭스 ({base_app} 기준)",
            f"기준앱({base_app})의 OR과 경쟁사 평균 OR의 차이(ΔOR)와 취약도를 결합해 "
            f"기능별 전략적 포지션을 4개 사분면으로 분류합니다. "
            f"ΔOR > 0 = {base_app} 경쟁 우위(강점 유지), ΔOR < 0 = 경쟁 열위(개선 검토).",
            f"<b>좌상단(경쟁 열위 · 개선 시급)</b>: {base_app}이 경쟁사보다 약하면서 전략 우선도가 높은 기능 — 즉시 개선 효과 최대. "
            f"<b>우상단(경쟁 우위 유지)</b>: 강점 보유 영역 — 현 수준 유지 및 차별화 포인트 활용. "
            f"<b>좌하단(산업 공통 문제)</b>: 경쟁사도 함께 약한 기능 — 선제 투자 시 차별화 가능. "
            f"<b>우하단(현상 유지)</b>: {base_app}이 강하지만 상대적 우선도 낮음.",
            app_items,
            summary=(
                f"개선 우선 검토(경쟁 열위 · 개선 시급) {len(q1)}개 · "
                f"강점 유지(경쟁 우위 유지) {len(q2)}개 · "
                f"모니터링(산업 공통 문제) {len(q3)}개 · "
                f"현 수준 유지(현상 유지) {len(q4)}개."
            ),
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
    st.markdown(f"""
    <div class="info-box" style="background:#131820;border-left:4px solid #4F8EF7;border-radius:6px;padding:0.75rem 1rem;margin-bottom:0.9rem;font-size:0.82rem;color:#94A3B8;">
    <b style="color:#93C5FD;">비교 분석 구성 안내</b><br>
    이 화면은 <b>{' / '.join(app_names)}</b> {len(app_names)}개 앱을 6단계로 비교합니다.<br>
    &bull; <b>섹션 1 (리뷰 분포)</b>: 수집된 리뷰의 평점 분포와 시간 추이 — 데이터 품질·편향 확인<br>
    &bull; <b>섹션 2 (KPI 비교)</b>: 앱별 총 리뷰 수·평균 평점·긍정/부정 비율 — 전체 건강도 스냅샷<br>
    &bull; <b>섹션 3 (워드클라우드)</b>: 긍정/부정 키워드 비교 — 각 앱의 강점·약점 주제 파악<br>
    &bull; <b>섹션 4 (OR 비교)</b>: 기능별 오즈비 — 어느 앱이 어떤 기능에서 사용자 만족도가 높은가<br>
    &bull; <b>섹션 5 (ΔOR)</b>: 기준 앱 대비 경쟁 우위/열위 기능 — 어디를 먼저 개선해야 하는가<br>
    &bull; <b>섹션 6 (우선순위 매트릭스)</b>: 4분면 전략 포지션 — 개선 효과 최대화 우선순위 결정
    </div>
    """, unsafe_allow_html=True)
    _render_distribution_section(raw_df, app_names)

    # ── 섹션 2: VS 헤더 + 앱별 KPI ──────────────────────────────────────────
    st.divider()
    _render_vs_kpi_section(raw_df, app_names)

    # ── 섹션 2-B: 긍정/부정 비율 도넛 차트 ─────────────────────────────────
    _render_sentiment_donut(raw_df, app_names)

    # ── 섹션 3: 4종 워드클라우드 ────────────────────────────────────────────
    st.divider()
    st.markdown("#### 키워드 워드클라우드 비교")
    _render_wc_sections(proc, app_names)

    # ── 섹션 4: OR 비교 ─────────────────────────────────────────────────────
    st.markdown("#### 기능별 오즈비(OR) 비교")
    _render_or_section(combined_or, app_names, raw_df, or_results)

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
