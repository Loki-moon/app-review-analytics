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
from src.visualization.tab_thesis_insights import render_single_insights


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
    vr: dict | None = None,
) -> None:
    if raw_df.empty:
        st.warning(
            "분석 결과가 없습니다. "
            "좌측 사이드바에서 앱을 선택하고 날짜 범위를 지정한 뒤 '분석 시작' 버튼을 눌러주세요."
        )
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

    # KPI 설명 info-box
    st.markdown("""
    <div class="info-box" style="background:#131820;border-left:4px solid #4F8EF7;border-radius:6px;padding:0.7rem 1rem;margin-bottom:0.8rem;font-size:0.82rem;color:#94A3B8;">
    <b style="color:#93C5FD;">핵심 지표(KPI) 카드 읽는 법</b><br>
    &bull; <b>총 리뷰 수</b>: 분석 기간 내 수집된 리뷰 건수. 표본이 클수록 OR·감성 분석 결과의 신뢰도가 높아집니다.<br>
    &bull; <b>평균 평점</b>: 1~5점 척도 평균. 4.0 이상은 양호, 3.0~3.9는 중립, 3.0 미만은 개선 필요 수준입니다.<br>
    &bull; <b>긍정 리뷰</b>: 4~5점 리뷰 비율. 높을수록 핵심 강점 유지 전략이 우선됩니다.<br>
    &bull; <b>부정 리뷰</b>: 1~2점 리뷰 비율. 이 값이 30% 초과 시 즉각적인 UX 개선 검토가 필요합니다.
    </div>
    """, unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 리뷰 수", review_label, help="분석 기간 수집 리뷰 건수. 50건 미만이면 OR 분석 신뢰도가 낮을 수 있습니다.")
    k2.metric("평균 평점", f"{avg_score:.2f} ⭐", help="1~5점 척도 평균. 4.0↑양호 / 3.0~3.9 중립 / 3.0↓ 개선 필요")
    k3.metric("긍정 리뷰", f"{pos_pct:.1f}%", help="4~5점 리뷰 비율. 높을수록 사용자 만족도가 높음을 의미합니다.")
    k4.metric("부정 리뷰", f"{neg_pct:.1f}%", help="1~2점 리뷰 비율. 30% 초과 시 개선 우선순위 검토가 필요합니다.")

    st.divider()

    # ── 감성 타임라인 ────────────────────────────────────────────────────────
    st.markdown("#### 월별 평균 평점 추이")
    st.markdown("""
    <div class="info-box" style="background:#131820;border-left:4px solid #4F8EF7;border-radius:6px;padding:0.7rem 1rem;margin-bottom:0.6rem;font-size:0.82rem;color:#94A3B8;">
    <b style="color:#93C5FD;">이 차트는 무엇을 보여주나요?</b><br>
    월별 평균 평점 변화를 시계열로 추적해 앱 품질 트렌드를 파악합니다.
    점선(중립=3.0) 아래로 내려가는 구간이 나타나면 해당 시점 전후의 업데이트·장애 이력을 확인하세요.
    평점이 급락하는 달은 특정 버전 배포나 정책 변경 등 외부 이벤트와 연결된 경우가 많습니다.
    호버 시 해당 월의 리뷰 수도 함께 확인할 수 있어 표본 편향 여부를 검증할 수 있습니다.
    </div>
    """, unsafe_allow_html=True)
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
            # 추가 해석: 최근 3개월 트렌드
            recent_trend_str = ""
            if len(monthly_df) >= 3:
                recent_3 = monthly_df.tail(3)
                r_avg = recent_3["avg_score"].mean()
                r_label = "상승 중" if recent_3.iloc[-1]["avg_score"] > recent_3.iloc[0]["avg_score"] else (
                    "하락 중" if recent_3.iloc[-1]["avg_score"] < recent_3.iloc[0]["avg_score"] else "횡보")
                recent_trend_str = (
                    f" 최근 3개월 평균 <b>{r_avg:.2f}점</b>({r_label}) — "
                    f"전체 평균({avg_score:.2f}점) 대비 "
                    f"{'개선 신호' if r_avg >= avg_score else '악화 신호'}."
                )

            diff_str = ""
            score_diff = best_m['avg_score'] - worst_m['avg_score']
            if score_diff >= 1.0:
                diff_str = f" 최고-최저 격차 {score_diff:.2f}점 — 특정 이벤트(앱 업데이트·장애·정책 변경)의 영향이 큰 편입니다."

            render_insight_box(
                f"{app_name} — 월별 평균 평점 추이",
                "월별 평균 평점 변화를 추적해 앱 품질 트렌드를 파악합니다.",
                "평점이 낮아지는 달에 어떤 업데이트나 이슈가 있었는지 확인하세요. "
                "최근 3개월 트렌드가 전체 평균보다 높다면 개선 효과가 나타나고 있다는 신호입니다.",
                [(app_name, APP_COLORS[0],
                  f"최고 평점: <b>{best_m['avg_score']:.2f}점</b> ({best_m['ym']}, {int(best_m['count'])}건) "
                  f"/ 최저 평점: <b>{worst_m['avg_score']:.2f}점</b> ({worst_m['ym']}, {int(worst_m['count'])}건). "
                  f"{diff_str} "
                  f"전체 {len(monthly_df)}개월 기간 동안 평점이 <b>{trend}</b> 추세(전체 평균 {avg_score:.2f}점 → {level})."
                  f"{recent_trend_str}")],
            )
    else:
        st.markdown("""
        <div class="info-box" style="background:#1a1a2e;border-left:4px solid #F59E0B;border-radius:6px;padding:0.7rem 1rem;font-size:0.82rem;color:#94A3B8;">
        ⚠️ <b style="color:#F59E0B;">날짜 정보가 없어 타임라인을 표시할 수 없습니다.</b><br>
        해결 방법: 수집 데이터에 <code>review_date</code> 컬럼이 포함되어 있는지 확인하세요.
        날짜 형식은 <code>YYYY-MM-DD</code> 또는 <code>YYYY-MM-DD HH:MM:SS</code>를 지원합니다.
        </div>
        """, unsafe_allow_html=True)

    # ── 워드클라우드 ─────────────────────────────────────────────────────────
    st.markdown("#### 키워드 워드클라우드")
    st.markdown("""
    <div class="info-box" style="background:#131820;border-left:4px solid #4F8EF7;border-radius:6px;padding:0.7rem 1rem;margin-bottom:0.6rem;font-size:0.82rem;color:#94A3B8;">
    <b style="color:#93C5FD;">이 차트는 무엇을 보여주나요?</b><br>
    긍정(4~5점)·부정(1~2점) 리뷰에서 자주 등장한 단어를 시각화합니다.
    글자가 클수록 해당 단어가 더 많은 리뷰에서 언급됐다는 뜻입니다.
    <b>긍정 워드클라우드</b>에서는 사용자가 만족하는 핵심 기능을,
    <b>부정 워드클라우드</b>에서는 개선이 시급한 불만 영역을 파악할 수 있습니다.
    두 클라우드에서 동시에 자주 등장하는 단어는 '양면적 인식'을 가진 기능 — 개선 여지가 가장 큰 영역입니다.
    </div>
    """, unsafe_allow_html=True)
    wc_col1, wc_col2 = st.columns(2)
    pos_tokens = proc[proc["score"] >= 4]["tokens"].tolist() if "score" in proc.columns else []
    neg_tokens = proc[proc["score"] <= 2]["tokens"].tolist() if "score" in proc.columns else []

    with wc_col1:
        st.markdown("**긍정 리뷰 (4~5점)** — 사용자가 칭찬한 핵심 포인트")
        pos_img = _make_wordcloud(pos_tokens, bg=_BG, colormap="Blues")
        if pos_img:
            st.image(pos_img, use_container_width=True)
        else:
            st.markdown("""
            <div style="background:#131820;border-left:3px solid #F59E0B;border-radius:4px;padding:0.5rem 0.75rem;font-size:0.80rem;color:#94A3B8;">
            ⚠️ 긍정 리뷰(4~5점) 데이터가 없습니다.<br>
            분석 기간을 늘리거나 해당 앱의 수집 리뷰를 확인해주세요.
            </div>
            """, unsafe_allow_html=True)
    with wc_col2:
        st.markdown("**부정 리뷰 (1~2점)** — 사용자가 불만족한 주요 원인")
        neg_img = _make_wordcloud(neg_tokens, bg=_BG, colormap="Reds")
        if neg_img:
            st.image(neg_img, use_container_width=True)
        else:
            st.markdown("""
            <div style="background:#131820;border-left:3px solid #F59E0B;border-radius:4px;padding:0.5rem 0.75rem;font-size:0.80rem;color:#94A3B8;">
            ⚠️ 부정 리뷰(1~2점) 데이터가 없습니다.<br>
            분석 기간을 늘리거나 해당 앱의 수집 리뷰를 확인해주세요.
            </div>
            """, unsafe_allow_html=True)

    # 워드클라우드 해석
    pos_cnt = Counter(t for tl in pos_tokens for t in tl)
    neg_cnt = Counter(t for tl in neg_tokens for t in tl)
    pos_top3 = pos_cnt.most_common(3)
    neg_top3 = neg_cnt.most_common(3)
    pos_top = " · ".join(f"<b>{w}</b>({c:,}회)" for w, c in pos_top3)
    neg_top = " · ".join(f"<b>{w}</b>({c:,}회)" for w, c in neg_top3)

    # 긍정·부정 중복 키워드 탐지 (양면적 인식 기능)
    pos_set5 = set(w for w, _ in pos_cnt.most_common(5))
    neg_set5 = set(w for w, _ in neg_cnt.most_common(5))
    both = pos_set5 & neg_set5
    both_str = (
        f" ⚡ 긍정·부정 공통 Top5 키워드 발견: <b>{'  /  '.join(both)}</b> — "
        "이 단어들은 만족·불만족 양쪽에서 자주 언급되므로, 품질 편차가 큰 영역일 가능성이 높습니다."
        if both else ""
    )

    wc_items = []
    if pos_top:
        pos_total = sum(c for _, c in pos_cnt.most_common(3))
        wc_items.append((f"{app_name} 긍정", APP_COLORS[0],
                         f"상위 키워드: {pos_top} — "
                         f"이 세 단어가 긍정 리뷰 전체의 {pos_total / max(sum(pos_cnt.values()), 1) * 100:.0f}%의 빈도를 차지합니다. "
                         "이 키워드들이 지속적으로 유지되도록 해당 기능의 품질 관리가 중요합니다."))
    if neg_top:
        neg_total = sum(c for _, c in neg_cnt.most_common(3))
        wc_items.append((f"{app_name} 부정", "#FF6B8A",
                         f"상위 키워드: {neg_top} — "
                         f"이 세 단어가 부정 리뷰 전체의 {neg_total / max(sum(neg_cnt.values()), 1) * 100:.0f}%의 빈도를 차지합니다. "
                         "빈도 1위 키워드부터 개선 로드맵에 반영하면 부정 리뷰를 가장 효과적으로 줄일 수 있습니다."))
    if wc_items:
        render_insight_box(
            "키워드 워드클라우드",
            "긍정/부정 리뷰에서 자주 등장하는 단어로 사용자 감성의 핵심 주제를 파악합니다.",
            "글자가 클수록 많은 리뷰에서 해당 단어가 언급된 것입니다. "
            "긍정·부정 클라우드에 동시에 나타나는 단어는 양면적 인식을 가진 기능 — 개선 효과가 가장 큰 영역입니다.",
            wc_items,
            summary=both_str if both_str else None,
        )

    # ── 기능 카테고리 OR ─────────────────────────────────────────────────────
    or_df = or_results.get(app_name, pd.DataFrame())
    if not or_df.empty:
        st.markdown("#### 기능 카테고리별 오즈비 (OR)")
        st.markdown(f"""
        <div class="info-box" style="background:#131820;border-left:4px solid #4F8EF7;border-radius:6px;padding:0.7rem 1rem;margin-bottom:0.6rem;font-size:0.82rem;color:#94A3B8;">
        <b style="color:#93C5FD;">이 차트는 무엇을 보여주나요?</b><br>
        오즈비(OR, Odds Ratio)는 특정 기능이 언급된 리뷰가 그렇지 않은 리뷰에 비해 긍정 평점을 받을 확률이 몇 배인지를 나타냅니다.<br>
        &bull; <b style="color:#4F6AF5;">OR &gt; 1 (파란색)</b>: 해당 기능을 언급한 리뷰가 미언급 리뷰보다 긍정 평점을 받을 가능성이 높음.
        예) OR=2.5이면 "이 기능이 언급된 리뷰는 미언급 대비 2.5배 긍정 평가로 이어졌다"는 의미입니다.<br>
        &bull; <b style="color:#FF6B8A;">OR &lt; 1 (빨간색)</b>: 해당 기능을 언급할수록 오히려 부정 평점과 연관됨 — 즉각 개선 대상.<br>
        &bull; <b>OR = 1 (점선)</b>: 기능 언급이 평점에 영향을 주지 않는 중립 상태.
        p-value &lt; 0.05인 기능만 통계적으로 유의미하며, 나머지는 참고용으로 해석하세요.
        </div>
        """, unsafe_allow_html=True)
        cat_fig = _category_bar(or_df, app_name)
        st.plotly_chart(cat_fig, use_container_width=True)

        # OR 해석
        sig = or_df[or_df["p_value"] < 0.05] if "p_value" in or_df.columns else or_df
        if not sig.empty:
            best  = sig.nlargest(1, "OR").iloc[0]
            worst = sig.nsmallest(1, "OR").iloc[0]
            sig_pos = sig[sig["OR"] > 1]
            sig_neg = sig[sig["OR"] < 1]

            pos_count_str = f"긍정 연관 기능 <b>{len(sig_pos)}개</b>" if not sig_pos.empty else "긍정 연관 기능 없음"
            neg_count_str = f"부정 연관 기능 <b>{len(sig_neg)}개</b>" if not sig_neg.empty else "부정 연관 기능 없음"

            best_interp = (
                f"OR={best['OR']:.2f}이므로, <b>{best['feature_category']}</b>가 언급된 리뷰는 "
                f"미언급 리뷰 대비 긍정 평가 확률이 <b>{best['OR']:.1f}배</b> 높습니다."
            )
            worst_interp = (
                f"OR={worst['OR']:.2f}이므로, <b>{worst['feature_category']}</b>가 언급된 리뷰는 "
                f"미언급 리뷰 대비 부정 평가 확률이 <b>{1/worst['OR']:.1f}배</b> 높습니다 — 개선 우선순위 1순위."
                if worst['OR'] > 0 and worst['OR'] < 1
                else f"부정 연관 기능: <b>{worst['feature_category']}</b> (OR={worst['OR']:.2f}) — 개선 우선 검토."
            )

            render_insight_box(
                f"{app_name} — 기능 카테고리별 오즈비(OR)",
                "각 기능 카테고리가 긍정/부정 리뷰와 얼마나 연관되는지 로지스틱 회귀 기반 오즈비(OR)로 측정합니다.",
                "OR이 클수록 그 기능 언급 시 긍정 평점이 달릴 확률이 높으며, "
                "OR < 1 기능은 불만과 직결되므로 개선 우선순위가 됩니다. "
                "통계적으로 유의(p<0.05)한 기능만 신뢰할 수 있는 근거로 활용하세요.",
                [(app_name, APP_COLORS[0],
                  f"{pos_count_str} / {neg_count_str} (p&lt;0.05 기준). "
                  f"긍정 1위: {best_interp} "
                  f"부정 1위: {worst_interp}")],
            )
        else:
            st.markdown("""
            <div class="info-box" style="background:#1a1a2e;border-left:4px solid #F59E0B;border-radius:6px;padding:0.7rem 1rem;font-size:0.82rem;color:#94A3B8;">
            ⚠️ <b style="color:#F59E0B;">통계적으로 유의한(p&lt;0.05) 기능이 없습니다.</b><br>
            원인: 리뷰 수가 적거나, 특정 기능 키워드 언급 빈도가 낮을 경우 유의성이 나타나지 않습니다.
            분석 기간을 늘리거나 더 많은 리뷰를 수집하면 유의성이 높아질 수 있습니다.
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="info-box" style="background:#1a1a2e;border-left:4px solid #F59E0B;border-radius:6px;padding:0.7rem 1rem;font-size:0.82rem;color:#94A3B8;">
        ⚠️ <b style="color:#F59E0B;">기능 카테고리별 OR 분석 결과가 없습니다.</b><br>
        OR 분석(로지스틱 회귀)을 위해서는 앱당 최소 <b>50건 이상</b>(안정적 분석은 100건 이상)의
        긍정·부정 리뷰와 각 기능 키워드의 충분한 언급이 필요합니다.
        분석 기간을 늘리거나 리뷰 수집 범위를 확대해주세요.
        </div>
        """, unsafe_allow_html=True)

    # ── 연관어 분석 ──────────────────────────────────────────────────────────
    if "tokens" in proc.columns:
        st.markdown("#### 기능별 연관어 Top5")
        st.markdown("""
        <div class="info-box" style="background:#131820;border-left:4px solid #4F8EF7;border-radius:6px;padding:0.7rem 1rem;margin-bottom:0.6rem;font-size:0.82rem;color:#94A3B8;">
        <b style="color:#93C5FD;">이 표는 무엇을 보여주나요?</b><br>
        각 기능 카테고리(결제, 보안, UI 등)를 언급한 리뷰에서 해당 기능 키워드와 <b>함께 자주 등장하는 단어 Top5</b>를 보여줍니다.<br>
        예) '결제' 카테고리 연관어에 '오류', '실패'가 많다면 → 결제 프로세스 안정성 개선이 필요하다는 신호입니다.<br>
        반대로 '빠르다', '편리하다' 등의 긍정어가 많다면 해당 기능이 강점임을 뜻합니다.<br>
        괄호 안의 숫자는 해당 단어의 등장 빈도(건수)입니다.
        </div>
        """, unsafe_allow_html=True)
        assoc_df = _associated_words(proc)
        if not assoc_df.empty:
            st.dataframe(assoc_df, use_container_width=True, hide_index=True)
        else:
            st.markdown("""
            <div style="background:#131820;border-left:3px solid #F59E0B;border-radius:4px;padding:0.5rem 0.75rem;font-size:0.80rem;color:#94A3B8;">
            ⚠️ 연관어 데이터가 없습니다. 토큰 전처리가 완료된 데이터가 충분히 존재하는지 확인해주세요.
            </div>
            """, unsafe_allow_html=True)

    # ── 논문 Ch.4–5 기반 연구 결과 종합 시사점 ──────────────────────────────
    render_single_insights(combined_or, app_name=app_name, vr=vr or {})
