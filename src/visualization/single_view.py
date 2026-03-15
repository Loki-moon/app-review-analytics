"""
단일 앱 분석 뷰 (PRD 단일 뷰)

- KPI 카드 (총 리뷰 수, 평균 평점, 긍정/부정 비율)
- 기능 카테고리 패널 (OR 기반 바 차트)
- 워드클라우드 (긍정/부정)
- 감성 타임라인
- 연관어 분석
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

from config.settings import ASSETS_DIR, WORDCLOUD_MAX_WORDS, APP_COLORS
from config.keywords import FEATURE_CATEGORIES
from src.visualization._common import (
    BG as _BG, GRID as _GRID, LINE as _LINE, TEXT as _TEXT, SUBTEXT as _SUBTEXT,
    apply_dark_theme, centered_title,
    render_insight_box,
)


_BUNDLED_FONT = ASSETS_DIR / "fonts" / "NanumGothic.ttf"


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


def _make_wordcloud(tokens: list[list[str]], bg: str = _BG, colormap: str = "Blues") -> bytes | None:
    counter: Counter = Counter(t for tl in tokens for t in tl)
    if not counter:
        return None
    font_path = _get_font_path()
    kwargs = dict(
        max_words=WORDCLOUD_MAX_WORDS,
        background_color=bg,
        width=700,
        height=350,
        colormap=colormap,
        prefer_horizontal=0.9,
    )
    if font_path:
        kwargs["font_path"] = font_path
    wc = WordCloud(**kwargs)
    wc.generate_from_frequencies(counter)
    fig, ax = plt.subplots(figsize=(9, 4.5), facecolor=bg)
    ax.set_facecolor(bg)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor=bg)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _sentiment_timeline(df: pd.DataFrame, app_name: str) -> go.Figure:
    """월별 평균 평점 타임라인"""
    df2 = df.copy()
    df2["review_date"] = pd.to_datetime(df2["review_date"], errors="coerce")
    df2 = df2.dropna(subset=["review_date"])
    df2["ym"] = df2["review_date"].dt.to_period("M").astype(str)

    monthly = (
        df2.groupby("ym")
        .agg(avg_score=("score", "mean"), count=("score", "count"))
        .reset_index()
        .sort_values("ym")
    )
    if monthly.empty:
        return go.Figure()

    color = APP_COLORS[0]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly["ym"],
        y=monthly["avg_score"],
        mode="lines+markers",
        name="평균 평점",
        line=dict(color=color, width=2.5),
        marker=dict(size=7),
        hovertemplate="월: %{x}<br>평균 평점: %{y:.2f}<br>리뷰 수: %{customdata}<extra></extra>",
        customdata=monthly["count"],
    ))
    fig.add_hline(y=3.0, line_dash="dot", line_color=_SUBTEXT,
                  annotation_text="중립(3점)", annotation_position="right",
                  annotation_font_color=_SUBTEXT)
    fig.update_layout(
        title=centered_title(f"{app_name} — 월별 평균 평점 추이"),
        xaxis_title="월",
        yaxis_title="평균 평점",
        height=320,
        margin=dict(l=10, r=10, t=60, b=40),
        hovermode="x unified",
    )
    apply_dark_theme(fig)
    fig.update_yaxes(range=[1, 5.2])
    return fig, monthly


def _category_bar(or_df: pd.DataFrame, app_name: str) -> go.Figure:
    """기능 카테고리별 OR 수평 바 차트"""
    if or_df.empty:
        return go.Figure()

    df_s = or_df.sort_values("OR", ascending=True)
    colors = ["#FF6B8A" if v < 1 else "#4F6AF5" for v in df_s["OR"]]

    fig = go.Figure(go.Bar(
        x=df_s["OR"],
        y=df_s["feature_category"],
        orientation="h",
        marker_color=colors,
        hovertemplate="기능: %{y}<br>OR: %{x:.3f}<extra></extra>",
    ))
    fig.add_vline(x=1.0, line_dash="dash", line_color=_SUBTEXT,
                  annotation_text="OR=1 (기준)", annotation_position="top right",
                  annotation_font_color=_SUBTEXT)
    fig.update_layout(
        title=centered_title(f"{app_name} — 기능 카테고리별 오즈비(OR)"),
        xaxis_title="오즈비 (OR)",
        height=max(300, len(df_s) * 30 + 100),
        margin=dict(l=10, r=10, t=60, b=40),
    )
    apply_dark_theme(fig)
    return fig


def _associated_words(df: pd.DataFrame) -> pd.DataFrame:
    """기능 카테고리별 상위 연관어"""
    rows = []
    for cat, keywords in FEATURE_CATEGORIES.items():
        kw_set = set(keywords)
        sub = df[df["tokens"].apply(lambda tl: any(k in tl for k in kw_set) if isinstance(tl, list) else False)]
        if sub.empty:
            continue
        counter: Counter = Counter(t for tl in sub["tokens"] if isinstance(tl, list) for t in tl if t not in kw_set)
        top = counter.most_common(5)
        rows.append({
            "기능 카테고리": cat,
            "연관어 Top5": "  /  ".join(f"{w}({c})" for w, c in top),
        })
    return pd.DataFrame(rows)


def render(
    raw_df: pd.DataFrame,
    processed_df: pd.DataFrame,
    or_results: dict[str, pd.DataFrame],
    combined_or: pd.DataFrame,
) -> None:
    if raw_df.empty:
        st.warning("분석 결과가 없습니다.")
        return

    app_name = raw_df["app_name"].iloc[0]
    df = raw_df.copy()

    # tokens 복원
    if "tokens" in processed_df.columns:
        def to_list(v):
            if isinstance(v, list):
                return v
            if isinstance(v, str):
                return v.split() if v else []
            return []
        proc = processed_df.copy()
        proc["tokens"] = proc["tokens"].apply(to_list)
    else:
        proc = processed_df.copy()
        proc["tokens"] = [[] for _ in range(len(proc))]

    # ── KPI 카드 ─────────────────────────────────────────────────────────────
    total = len(df)
    avg_score = df["score"].mean() if "score" in df.columns else 0
    pos_pct = (df["score"] >= 4).sum() / total * 100 if total > 0 else 0
    neg_pct = (df["score"] <= 2).sum() / total * 100 if total > 0 else 0
    n_android = len(df[df["platform"] == "Google Play Store"]) if "platform" in df.columns else 0
    n_ios     = len(df[df["platform"] == "Apple App Store"])   if "platform" in df.columns else 0
    if n_android and n_ios:
        review_label = f"{total:,}건 (Android {n_android:,} / iOS {n_ios:,})"
    else:
        review_label = f"{total:,}건"

    st.markdown(f"### {app_name} 분석 결과")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 리뷰 수", review_label)
    k2.metric("평균 평점", f"{avg_score:.2f} ⭐")
    k3.metric("긍정 리뷰", f"{pos_pct:.1f}%")
    k4.metric("부정 리뷰", f"{neg_pct:.1f}%")

    st.divider()

    # ── 감성 타임라인 ────────────────────────────────────────────────────────
    st.markdown("#### 월별 평균 평점 추이")
    timeline_result = _sentiment_timeline(df, app_name)
    if isinstance(timeline_result, tuple):
        timeline_fig, monthly_df = timeline_result
    else:
        timeline_fig, monthly_df = timeline_result, pd.DataFrame()

    if timeline_fig.data:
        st.plotly_chart(timeline_fig, use_container_width=True)
        if not monthly_df.empty:
            best_m = monthly_df.loc[monthly_df["avg_score"].idxmax()]
            worst_m = monthly_df.loc[monthly_df["avg_score"].idxmin()]
            trend = "상승" if monthly_df.iloc[-1]["avg_score"] > monthly_df.iloc[0]["avg_score"] else (
                "하락" if monthly_df.iloc[-1]["avg_score"] < monthly_df.iloc[0]["avg_score"] else "횡보")
            level = "높은 편" if avg_score >= 4 else ("보통" if avg_score >= 3 else "낮은 편")
            render_insight_box(
                f"{app_name} — 월별 평균 평점 추이",
                "월별 평균 평점 변화를 추적해 앱 품질 트렌드를 파악합니다.",
                "평점이 낮아지는 달에 어떤 업데이트나 이슈가 있었는지 확인해보세요.",
                [(app_name, APP_COLORS[0],
                  f"최고 평점: <b>{best_m['avg_score']:.2f}점</b> ({best_m['ym']}, {int(best_m['count'])}건) "
                  f"/ 최저 평점: <b>{worst_m['avg_score']:.2f}점</b> ({worst_m['ym']}, {int(worst_m['count'])}건). "
                  f"전체 {len(monthly_df)}개월 기간 동안 평점이 <b>{trend}</b> 추세. "
                  f"평균 {avg_score:.2f}점 → {level}.")],
            )
    else:
        st.caption("날짜 정보가 없어 타임라인을 표시할 수 없습니다.")

    # ── 워드클라우드 ─────────────────────────────────────────────────────────
    st.markdown("#### 키워드 워드클라우드")
    wc_col1, wc_col2 = st.columns(2)
    pos_tokens = proc[proc["score"] >= 4]["tokens"].tolist() if "score" in proc.columns else []
    neg_tokens = proc[proc["score"] <= 2]["tokens"].tolist() if "score" in proc.columns else []

    with wc_col1:
        st.markdown("**긍정 리뷰 (4~5점)**")
        pos_img = _make_wordcloud(pos_tokens, bg=_BG, colormap="Blues")
        if pos_img:
            st.image(pos_img, use_container_width=True)
        else:
            st.caption("긍정 리뷰 데이터가 없습니다.")
    with wc_col2:
        st.markdown("**부정 리뷰 (1~2점)**")
        neg_img = _make_wordcloud(neg_tokens, bg=_BG, colormap="Reds")
        if neg_img:
            st.image(neg_img, use_container_width=True)
        else:
            st.caption("부정 리뷰 데이터가 없습니다.")

    # 워드클라우드 해석
    pos_cnt = Counter(t for tl in pos_tokens for t in tl)
    neg_cnt = Counter(t for tl in neg_tokens for t in tl)
    pos_top = " · ".join(f"<b>{w}</b>" for w, _ in pos_cnt.most_common(3))
    neg_top = " · ".join(f"<b>{w}</b>" for w, _ in neg_cnt.most_common(3))
    wc_items = []
    if pos_top:
        wc_items.append((f"{app_name} 긍정", APP_COLORS[0],
                         f"상위 키워드: {pos_top} — 사용자들이 만족한 핵심 포인트입니다."))
    if neg_top:
        wc_items.append((f"{app_name} 부정", "#FF6B8A",
                         f"상위 키워드: {neg_top} — 사용자들이 불만족한 주요 원인입니다."))
    if wc_items:
        render_insight_box(
            "키워드 워드클라우드",
            "긍정/부정 리뷰에서 자주 등장하는 단어로 사용자 감성을 파악합니다.",
            "큰 글씨로 자주 등장할수록 많은 사람이 그 주제를 언급했다는 뜻이에요.",
            wc_items,
        )

    # ── 기능 카테고리 OR ─────────────────────────────────────────────────────
    or_df = or_results.get(app_name, pd.DataFrame())
    if not or_df.empty:
        st.markdown("#### 기능 카테고리별 오즈비 (OR)")
        st.markdown("""
        <div class="info-box">
        OR > 1 (파란색): 해당 기능이 언급될 때 긍정 평가와 더 연관됩니다.<br>
        OR &lt; 1 (빨간색): 해당 기능이 언급될 때 부정 평가와 더 연관됩니다.
        </div>
        """, unsafe_allow_html=True)
        cat_fig = _category_bar(or_df, app_name)
        st.plotly_chart(cat_fig, use_container_width=True)

        # OR 해석
        sig = or_df[or_df["p_value"] < 0.05] if "p_value" in or_df.columns else or_df
        if not sig.empty:
            best  = sig.nlargest(1, "OR").iloc[0]
            worst = sig.nsmallest(1, "OR").iloc[0]
            render_insight_box(
                f"{app_name} — 기능 카테고리별 오즈비(OR)",
                "각 기능이 긍정/부정 리뷰와 얼마나 연관되는지 오즈비로 측정합니다.",
                "OR이 클수록 그 기능을 언급할 때 좋은 평점이 달리는 경우가 많다는 뜻이에요.",
                [(app_name, APP_COLORS[0],
                  f"긍정 연관 1위: <b>{best['feature_category']}</b> (OR={best['OR']:.2f}) "
                  f"— 이 기능 언급 시 긍정 평점이 {best['OR']:.1f}배. "
                  f"부정 연관 1위: <b>{worst['feature_category']}</b> (OR={worst['OR']:.2f}) "
                  f"— 사용자 불만이 집중되는 영역, 개선 시급.")],
            )

    # ── 연관어 분석 ──────────────────────────────────────────────────────────
    if "tokens" in proc.columns:
        st.markdown("#### 기능별 연관어 Top5")
        assoc_df = _associated_words(proc)
        if not assoc_df.empty:
            st.dataframe(assoc_df, use_container_width=True, hide_index=True)
        else:
            st.caption("연관어 데이터가 없습니다.")
