"""
Tab 2: Keyword Cloud

- 전체 / 긍정(4점+) / 보통(3점) / 부정(2점-) 워드클라우드
- 상위 빈도 단어 표
- 앱별 토글
"""
from __future__ import annotations

import io
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from wordcloud import WordCloud

from config.settings import WORDCLOUD_MAX_WORDS, TOP_KEYWORDS_N, ASSETS_DIR
from src.visualization._common import (
    BG as _BG,
    get_ordered_app_names, app_color, render_insight_box, render_skeleton,
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
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


_BG = "#0E1116"

_SECTION_COLORMAPS = {
    "🔵 전체 키워드":         "cool",
    "🟢 긍정 키워드 (4~5점)": "summer",
    "🟡 보통 키워드 (3점)":   "autumn",
    "🔴 부정 키워드 (1~2점)": "hot",
}




def _make_wordcloud(token_counter: Counter, title: str, bg_color: str = _BG,
                    colormap: str = "cool") -> bytes | None:
    if not token_counter:
        return None

    font_path = _get_font_path()
    wc_kwargs = dict(
        max_words=WORDCLOUD_MAX_WORDS,
        background_color=bg_color,
        width=600,
        height=320,
        colormap=colormap,
        prefer_horizontal=0.9,
    )
    if font_path:
        wc_kwargs["font_path"] = font_path
    wc = WordCloud(**wc_kwargs)
    wc.generate_from_frequencies(token_counter)

    fig, ax = plt.subplots(figsize=(7, 3.5), facecolor=bg_color)
    ax.set_facecolor(bg_color)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=13, fontweight="bold", pad=10, color="#E2E8F0")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor=bg_color)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _tokens_to_counter(token_lists: list[list[str]]) -> Counter:
    c: Counter = Counter()
    for tl in token_lists:
        c.update(tl)
    return c


def render(df: pd.DataFrame) -> None:
    st.markdown("""
    <div class="info-box">
    <b>☁️ 키워드 탐색 — 리뷰 텍스트에서 자주 등장하는 단어를 시각화합니다.</b><br><br>
    <b>읽는 법:</b><br>
    · 워드클라우드에서 <b>단어가 클수록</b> 해당 리뷰 구간에서 더 자주 등장한 단어입니다<br>
    · <b>🔵 전체</b>: 모든 리뷰의 관심사 / <b>🟢 긍정</b>: 만족 요인 / <b>🔴 부정</b>: 불만 원인 — 이 세 구간을 비교하면 가장 많은 인사이트를 얻을 수 있습니다<br>
    · <b>공통 키워드 보기</b>: 여러 앱 모두에서 등장하는 단어만 필터링해 공통 이슈를 확인<br><br>
    <b>활용 팁:</b> 긍정 키워드에 "빠른", "편리"가 자주 보이면 속도·편의성이 강점이고,
    부정 키워드에 "오류", "안됨"이 많으면 기능 안정성이 핵심 개선 과제입니다.
    </div>
    """, unsafe_allow_html=True)

    if df.empty or "tokens" not in df.columns:
        st.markdown("""
        <div class="info-box" style="border-left:4px solid #F59E0B;">
        ⚠️ <b>키워드 데이터가 없습니다.</b><br>
        분석이 완료된 후에 표시됩니다. 리뷰 수가 너무 적거나 형태소 분석에 실패했을 수 있어요.<br>
        리뷰를 10건 이상 수집한 후 다시 분석해주세요.
        </div>
        """, unsafe_allow_html=True)
        return

    # tokens 컬럼이 문자열로 저장된 경우 리스트로 복원
    def to_list(v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return v.split() if v else []
        return []

    df = df.copy()
    df["tokens"] = df["tokens"].apply(to_list)

    # ── 앱 선택 토글 ───────────────────────────────────────────────────────────
    app_names = get_ordered_app_names(df)
    app_options = ["전체"] + app_names
    selected_app = st.selectbox("📱 앱 선택", app_options, key="kw_app_select")

    view_df = df if selected_app == "전체" else df[df["app_name"] == selected_app]

    # ── 공통 키워드만 보기 옵션 (전체 선택 시만 활성) ────────────────────────
    common_only = False
    if selected_app == "전체" and len(app_names) >= 2:
        common_only = st.checkbox(
            "공통 키워드만 보기 (모든 앱에서 공통으로 등장한 키워드)",
            help="여러 앱이 공통으로 언급하는 키워드는 업계 전반의 공통 이슈 또는 사용자들이 공통으로 중요하게 여기는 기능입니다.",
        )

    if common_only:
        # 앱별 상위 키워드 교집합
        per_app_kw: list[set[str]] = []
        for an in app_names:
            sub = df[df["app_name"] == an]["tokens"]
            c = _tokens_to_counter(sub.tolist())
            per_app_kw.append(set(kw for kw, _ in c.most_common(TOP_KEYWORDS_N)))
        common_set = set.intersection(*per_app_kw) if per_app_kw else set()
        view_df = view_df.copy()
        view_df["tokens"] = view_df["tokens"].apply(lambda tl: [t for t in tl if t in common_set])

    # ── 평점 구간 분리 ─────────────────────────────────────────────────────────
    all_tokens  = view_df["tokens"].tolist()
    pos_tokens  = view_df[view_df["score"] >= 4]["tokens"].tolist()
    mid_tokens  = view_df[view_df["score"] == 3]["tokens"].tolist()
    neg_tokens  = view_df[view_df["score"] <= 2]["tokens"].tolist()

    sections = [
        ("🔵 전체 키워드",          all_tokens),
        ("🟢 긍정 키워드 (4~5점)",  pos_tokens),
        ("🟡 보통 키워드 (3점)",    mid_tokens),
        ("🔴 부정 키워드 (1~2점)",  neg_tokens),
    ]

    # 2×2 그리드로 렌더링
    _purpose = {
        "🔵 전체 키워드":         "전체 리뷰에서 가장 많이 언급된 키워드를 파악합니다.",
        "🟢 긍정 키워드 (4~5점)": "4~5점 긍정 평가 리뷰에서 자주 등장한 단어를 파악합니다.",
        "🟡 보통 키워드 (3점)":   "3점 중립 리뷰에서 자주 등장한 단어를 파악합니다.",
        "🔴 부정 키워드 (1~2점)": "1~2점 부정 평가 리뷰에서 자주 등장한 단어를 파악합니다.",
    }
    _effect = {
        "🔵 전체 키워드":         "전반적인 사용자 관심사를 한눈에 볼 수 있어요.",
        "🟢 긍정 키워드 (4~5점)": "사용자가 칭찬하는 포인트를 알 수 있어요.",
        "🟡 보통 키워드 (3점)":   "개선 여지가 있는 중간 평가 영역을 파악할 수 있어요.",
        "🔴 부정 키워드 (1~2점)": "사용자가 불만족하는 핵심 원인을 알 수 있어요.",
    }
    # determine display name for the single selected app (or "전체")
    display_name = selected_app

    for row in range(2):
        left_col, right_col = st.columns(2)
        for col_idx, col in enumerate([left_col, right_col]):
            title, token_lists = sections[row * 2 + col_idx]
            cmap = _SECTION_COLORMAPS.get(title, "cool")
            with col:
                st.markdown(f"#### {title}")
                counter = _tokens_to_counter(token_lists)

                if not counter:
                    empty_msg = {
                        "🔵 전체 키워드":         "전체 리뷰 토큰이 없습니다.",
                        "🟢 긍정 키워드 (4~5점)": "4~5점 리뷰가 없거나 분석 가능한 키워드가 없습니다.",
                        "🟡 보통 키워드 (3점)":   "3점 리뷰가 없거나 분석 가능한 키워드가 없습니다.",
                        "🔴 부정 키워드 (1~2점)": "1~2점 리뷰가 없거나 분석 가능한 키워드가 없습니다. 리뷰 수집 기간을 늘려보세요.",
                    }
                    st.caption(empty_msg.get(title, "해당 구간의 리뷰가 없습니다."))
                    continue

                img_bytes = _make_wordcloud(counter, title="", bg_color=_BG, colormap=cmap)
                if img_bytes:
                    st.image(img_bytes, use_container_width=True)

                top5 = counter.most_common(5)
                if top5:
                    top_words = " · ".join(f"<b>{w}</b>({c:,}회)" for w, c in top5[:3])
                    total_tokens = sum(counter.values())
                    top3_pct = sum(c for _, c in top5[:3]) / total_tokens * 100 if total_tokens > 0 else 0
                    unique_words = len(counter)
                    item_color = app_color(selected_app, app_names) if selected_app != "전체" else "#4F8EF7"

                    _interp_guide = {
                        "🔵 전체 키워드":         "가장 빈번한 단어가 이 앱 사용자들의 핵심 관심사입니다. 기능 키워드(결제·송금·인증 등)가 상위에 보이면 OR 분석 결과와 교차 검토하세요.",
                        "🟢 긍정 키워드 (4~5점)": "만족한 사용자가 자주 쓴 단어 = 이 앱의 강점 시그널입니다. 마케팅 메시지나 강점 유지 전략에 활용하세요.",
                        "🟡 보통 키워드 (3점)":   "중립 리뷰의 키워드는 '아쉽지만 쓸 만하다'는 감정을 담고 있습니다. 이 단어들이 개선되면 긍정으로 전환될 가능성이 높습니다.",
                        "🔴 부정 키워드 (1~2점)": "불만족 사용자가 반복 언급한 단어 = 시급한 개선 과제입니다. 이 키워드들은 OR 분석의 부정 연관 기능과 함께 확인하세요.",
                    }
                    render_insight_box(
                        title,
                        _purpose.get(title, ""),
                        _effect.get(title, ""),
                        [(display_name, item_color,
                          f"상위 3개: {top_words} — 전체 {total_tokens:,}개 토큰 중 {top3_pct:.0f}% 차지 (고유 단어 {unique_words:,}개). "
                          + _interp_guide.get(title, "자주 등장하는 단어일수록 사용자 관심이 집중된 주제입니다."))],
                    )

                with st.expander("상위 키워드 표 보기", expanded=True):
                    top_df = pd.DataFrame(counter.most_common(TOP_KEYWORDS_N), columns=["키워드", "빈도"])
                    st.dataframe(top_df, use_container_width=True, height=220)

        if row < 1:
            st.divider()
