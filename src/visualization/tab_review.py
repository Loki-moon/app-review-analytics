"""
Tab 1: Review Explorer

- 앱별 리뷰 목록 (최신순, 25개씩 더보기)
- 검색창, 평점 필터, 앱 필터
- Export 섹션 (PRD 30번): 앱별 개별 / 전체 통합 / 필터 적용 CSV 다운로드
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st


PAGE_SIZE = 25

# PRD 30번 Export 포함 컬럼
EXPORT_COLS = [
    "platform", "app_name", "app_id", "review_id", "review_date",
    "score", "content", "review_created_version", "thumbs_up_count",
    "reply_content", "replied_at", "collected_at",
]


def _to_csv(df: pd.DataFrame) -> bytes:
    """Export 컬럼만 추출하여 UTF-8 BOM CSV 반환"""
    cols = [c for c in EXPORT_COLS if c in df.columns]
    return df[cols].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def _file_name(platform: str, app_id: str, start: date | str, end: date | str) -> str:
    """platform_appid_startdate_enddate.csv"""
    s = str(start).replace("-", "")
    e = str(end).replace("-", "")
    safe_id = str(app_id).replace(".", "_")
    safe_platform = platform.replace(" ", "_").lower()
    return f"{safe_platform}_{safe_id}_{s}_{e}.csv"


def _render_export(
    raw_df: pd.DataFrame,
    filtered_df: pd.DataFrame,
    start_date: date | None,
    end_date: date | None,
) -> None:
    """Export 섹션 렌더링"""
    st.markdown("---")
    st.markdown("### 📥 리뷰 데이터 다운로드")
    st.markdown("""
    <div class="info-box">
    다운로드된 파일은 Excel 또는 Google Sheets에서 바로 열 수 있어요.<br>
    한글이 깨지는 경우 파일을 열 때 UTF-8 인코딩을 선택해주세요.
    </div>
    """, unsafe_allow_html=True)

    sd = str(start_date) if start_date else "unknown"
    ed = str(end_date)   if end_date   else "unknown"

    # ── 앱별 개별 다운로드 ─────────────────────────────────────────────────────
    st.markdown("**앱별 개별 다운로드**")
    app_names = raw_df["app_name"].unique().tolist() if not raw_df.empty else []

    for app_name in app_names:
        app_df = raw_df[raw_df["app_name"] == app_name]
        count  = len(app_df)

        platform = app_df["platform"].iloc[0] if "platform" in app_df.columns and len(app_df) > 0 else "google_play"
        app_id   = app_df["app_id"].iloc[0]   if "app_id"   in app_df.columns and len(app_df) > 0 else app_name
        fname    = _file_name(platform, app_id, sd, ed)

        col_btn, col_info = st.columns([4, 1])
        with col_btn:
            st.download_button(
                label=f"⬇️ {app_name} 전체 다운로드 ({count:,}건)",
                data=_to_csv(app_df),
                file_name=fname,
                mime="text/csv",
                key=f"export_app_{app_name}",
            )
        with col_info:
            st.caption(f"{count:,}건")

    # ── 전체 통합 다운로드 ─────────────────────────────────────────────────────
    st.markdown("**전체 앱 통합 다운로드**")
    total_count = len(raw_df)
    col_all, col_all_info = st.columns([4, 1])
    with col_all:
        st.download_button(
            label=f"⬇️ 전체 데이터 다운로드 ({total_count:,}건)",
            data=_to_csv(raw_df),
            file_name=f"all_apps_{sd.replace('-','')}.{ed.replace('-','')}.csv",
            mime="text/csv",
            key="export_all",
        )
    with col_all_info:
        st.caption(f"{total_count:,}건")

    # ── 현재 필터 적용 데이터 다운로드 ────────────────────────────────────────
    filtered_count = len(filtered_df)
    col_filt, col_filt_info = st.columns([4, 1])
    with col_filt:
        st.download_button(
            label=f"⬇️ 현재 필터 적용 데이터 다운로드 ({filtered_count:,}건)",
            data=_to_csv(filtered_df),
            file_name=f"filtered_{sd.replace('-','')}.{ed.replace('-','')}.csv",
            mime="text/csv",
            key="export_filtered",
        )
    with col_filt_info:
        st.caption(f"{filtered_count:,}건")


def render(
    df: pd.DataFrame,
    start_date: date | None = None,
    end_date: date | None = None,
) -> None:
    st.markdown("""
    <div class="info-box">
    수집된 원본 리뷰를 탐색합니다. 검색어나 필터로 원하는 리뷰를 빠르게 확인하세요.
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.warning("표시할 리뷰 데이터가 없습니다.")
        return

    # ── 필터 영역 ──────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([3, 2, 2])

    with col1:
        search_query = st.text_input("🔍 리뷰 검색", placeholder="키워드를 입력하세요")

    app_options = ["전체"] + sorted(df["app_name"].unique().tolist())
    with col2:
        selected_app = st.selectbox("📱 앱 필터", app_options)

    score_options = ["전체", "5점", "4점", "3점", "2점", "1점"]
    with col3:
        selected_score = st.selectbox("⭐ 평점 필터", score_options)

    # ── 필터 적용 ──────────────────────────────────────────────────────────────
    filtered = df.copy()

    if search_query:
        mask = filtered["content"].fillna("").str.contains(search_query, case=False, na=False)
        filtered = filtered[mask]

    if selected_app != "전체":
        filtered = filtered[filtered["app_name"] == selected_app]

    if selected_score != "전체":
        score_val = int(selected_score[0])
        filtered = filtered[filtered["score"] == score_val]

    # 최신일 기준 정렬
    if "review_date" in filtered.columns:
        filtered = filtered.sort_values("review_date", ascending=False)

    st.markdown(f"**총 {len(filtered):,}개** 리뷰")

    # ── 더보기 pagination ───────────────────────────────────────────────────────
    page_key = "review_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    # 필터가 바뀌면 페이지 리셋
    filter_sig = f"{search_query}|{selected_app}|{selected_score}"
    sig_key = "review_filter_sig"
    if st.session_state.get(sig_key) != filter_sig:
        st.session_state[page_key] = 1
        st.session_state[sig_key] = filter_sig

    page = st.session_state[page_key]
    show_count = PAGE_SIZE * page
    display_df = filtered.head(show_count)

    # 노출 컬럼 선택
    display_cols = []
    for col in ["app_name", "platform", "score", "review_date", "content", "review_created_version", "thumbs_up_count"]:
        if col in display_df.columns:
            display_cols.append(col)

    col_rename = {
        "app_name": "앱",
        "platform": "플랫폼",
        "score": "평점",
        "review_date": "작성일",
        "content": "리뷰 내용",
        "review_created_version": "버전",
        "thumbs_up_count": "👍",
    }

    st.dataframe(
        display_df[display_cols].rename(columns=col_rename),
        use_container_width=True,
        height=520,
        column_config={
            "리뷰 내용": st.column_config.TextColumn(width="large"),
            "평점": st.column_config.NumberColumn(format="⭐ %d"),
        },
    )

    if show_count < len(filtered):
        remaining = len(filtered) - show_count
        if st.button(f"더보기 ({remaining:,}개 남음)", key="review_more_btn"):
            st.session_state[page_key] += 1
            st.rerun()

    # ── Export 섹션 (PRD 30번) ─────────────────────────────────────────────────
    _render_export(df, filtered, start_date, end_date)
