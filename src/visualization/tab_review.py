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

# ── PO/PM 대응 필요사항 — 카테고리 태그 + 다크모드 색상 ──────────────────────

# tag → (badge_label, text_color, bg_color)
_TAG_META: dict[str, tuple[str, str, str]] = {
    "bug":      ("🔴 버그수정",    "#FCA5A5", "rgba(239,68,68,0.16)"),
    "auth":     ("🟣 인증개선",    "#D8B4FE", "rgba(168,85,247,0.15)"),
    "perf":     ("🟡 성능개선",    "#FDE68A", "rgba(251,191,36,0.12)"),
    "payment":  ("🟠 결제점검",    "#FDBA74", "rgba(249,115,22,0.15)"),
    "ux":       ("🔵 UX개선",      "#A5B4FC", "rgba(99,102,241,0.15)"),
    "update":   ("🩵 버전검증",    "#67E8F9", "rgba(6,182,212,0.14)"),
    "notif":    ("🔔 알림개선",    "#5EEAD4", "rgba(20,184,166,0.13)"),
    "security": ("🔐 보안점검",    "#FCA5A5", "rgba(220,38,38,0.18)"),
    "feature":  ("💡 기능요청",    "#C4B5FD", "rgba(139,92,246,0.13)"),
    "positive": ("✅ 긍정유지",    "#6EE7B7", "rgba(16,185,129,0.13)"),
    "cs":       ("📢 CS대응",      "#FDBA74", "rgba(249,115,22,0.14)"),
    "improve":  ("🔶 개선검토",    "#FCD34D", "rgba(245,158,11,0.12)"),
    "neutral":  ("⬜ 중립모니터",  "#CBD5E1", "rgba(100,116,139,0.10)"),
    "great":    ("🌟 강점활용",    "#86EFAC", "rgba(16,185,129,0.15)"),
}

# (keywords, tag, action_text)
_ACTION_RULES: list[tuple[list[str], str, str]] = [
    # 오류/버그
    (["오류", "버그", "에러", "error", "crash", "강제종료", "팅김", "먹통", "안됨", "안되",
      "작동 안", "실행 안", "열리지 않", "안 열", "튕"],
     "bug", "버그 수정 필요 — QA팀에 재현 케이스 전달 및 긴급 패치 검토"),
    # 로그인/인증
    (["로그인", "인증", "비밀번호", "본인인증", "otp", "인증번호"],
     "auth", "인증 플로우 개선 필요 — 로그인 UX 및 오류 메시지 점검"),
    # 속도/성능
    (["느림", "느려", "로딩", "버벅", "렉", "지연", "오래 걸", "한참"],
     "perf", "성능 개선 필요 — 로딩 지연 구간 프로파일링 후 개선"),
    # 결제/이체/금융
    (["결제", "이체", "송금", "출금", "입금", "거래", "카드 등록", "카드 오류"],
     "payment", "결제/이체 플로우 점검 필요 — 오류 로그 분석 및 재현 테스트"),
    # UI/UX/디자인
    (["불편", "복잡", "어렵", "ui", "ux", "인터페이스", "화면", "디자인", "직관", "헷갈"],
     "ux", "UI/UX 개선 필요 — 사용자 흐름 재검토 및 사용성 테스트"),
    # 업데이트 후 문제
    (["업데이트", "업뎃", "최신 버전", "버전 올리고"],
     "update", "최신 버전 회귀 이슈 확인 — 업데이트 전후 기능 비교 테스트"),
    # 알림/푸시
    (["알림", "푸시", "notification", "push"],
     "notif", "알림 설정 로직 점검 — 알림 수신 조건 및 권한 처리 확인"),
    # 개인정보/보안
    (["개인정보", "보안", "해킹", "유출", "정보 노출"],
     "security", "보안 점검 필요 — 개인정보 처리 방침 및 데이터 보호 로직 검토"),
    # 기능 요청
    (["추가해", "추가해줘", "기능 넣", "있으면 좋겠", "원해요", "요청", "개선해"],
     "feature", "신규 기능 요청 — 백로그 등록 후 사용자 수요 우선순위 검토"),
    # 긍정 키워드
    (["좋아", "완벽", "편리", "최고", "만족", "훌륭", "유용"],
     "positive", "긍정 피드백 — 해당 기능 강점으로 마케팅 활용 및 유지 전략 수립"),
]

_DEFAULT_ACTIONS: dict[int, tuple[str, str]] = {
    1: ("cs",      "전반적 불만 — CS팀 에스컬레이션 및 주요 불만 유형 분류"),
    2: ("improve", "개선 필요 — 반복 불만 패턴 파악 후 개선 로드맵에 반영"),
    3: ("neutral", "중립 — 사용자 여정 중 마찰 구간 파악 및 소소한 UX 개선 검토"),
    4: ("positive","긍정 — 강점 기능 유지 및 리텐션 캠페인 활용 검토"),
    5: ("great",   "매우 긍정 — 앱스토어 리뷰 응원 댓글 작성 및 추천 사례 수집"),
}


def _suggest_action(score: int, content: str) -> tuple[str, str]:
    """Returns (tag_key, display_text) for coloring + content."""
    text = str(content).lower()
    for keywords, tag, action in _ACTION_RULES:
        if any(kw in text for kw in keywords):
            badge = _TAG_META[tag][0]
            return tag, f"{badge}  {action}"
    tag, action = _DEFAULT_ACTIONS.get(score, ("neutral", "내용 검토 후 팀 내 공유"))
    badge = _TAG_META[tag][0]
    return tag, f"{badge}  {action}"


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
    수집된 원본 리뷰를 탐색합니다. 검색어나 필터로 원하는 리뷰를 빠르게 확인하세요.<br>
    리뷰 내용을 기반으로 서비스 제품 PO/PM이 개선해야하는 항목을 안내합니다.
    </div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.warning("표시할 리뷰 데이터가 없습니다.")
        return

    # ── PO/PM 태그 필터 옵션 (정적) ───────────────────────────────────────────
    _TAG_DISPLAY: dict[str, str] = {meta[0]: key for key, meta in _TAG_META.items()}
    pm_options = ["전체"] + list(_TAG_DISPLAY.keys())

    # ── 버전 옵션 ──────────────────────────────────────────────────────────────
    has_version = "review_created_version" in df.columns
    if has_version:
        def _ver_key(v: str):
            try:
                return tuple(int(x) for x in str(v).split("."))
            except Exception:
                return (0, 0, 0)
        raw_versions = df["review_created_version"].dropna().astype(str).unique().tolist()
        versions = sorted(raw_versions, key=_ver_key, reverse=True)
        version_options = ["전체"] + versions
    else:
        version_options = ["전체"]

    # ── 필터 UI — 2행 ─────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        search_query = st.text_input("🔍 리뷰 검색", placeholder="키워드를 입력하세요")
    with col2:
        app_options = ["전체"] + sorted(df["app_name"].unique().tolist())
        selected_app = st.selectbox("📱 앱 필터", app_options)
    with col3:
        selected_score = st.selectbox("⭐ 평점 필터", ["전체", "5점", "4점", "3점", "2점", "1점"])

    col4, col5, col6 = st.columns([3, 2, 2])
    with col4:
        selected_pm_display = st.selectbox("🏷️ PO/PM 대응 필터", pm_options)
    with col5:
        selected_version = st.selectbox("📦 버전 필터", version_options)
    with col6:
        pass  # 여백

    # ── 기본 필터 적용 ─────────────────────────────────────────────────────────
    filtered = df.copy()

    if search_query:
        mask = filtered["content"].fillna("").str.contains(search_query, case=False, na=False)
        filtered = filtered[mask]

    if selected_app != "전체":
        filtered = filtered[filtered["app_name"] == selected_app]

    if selected_score != "전체":
        score_val = int(selected_score[0])
        filtered = filtered[filtered["score"] == score_val]

    if selected_version != "전체" and has_version:
        filtered = filtered[
            filtered["review_created_version"].astype(str) == selected_version
        ]

    # ── PO/PM 액션 전체 연산 (필터링 전) ─────────────────────────────────────
    action_results = filtered.apply(
        lambda r: _suggest_action(int(r.get("score", 3)), r.get("content", "")),
        axis=1,
    )
    filtered = filtered.copy()
    filtered["_tag"]   = [res[0] for res in action_results]
    filtered["action"] = [res[1] for res in action_results]

    # ── PO/PM 태그 필터 적용 ──────────────────────────────────────────────────
    if selected_pm_display != "전체":
        pm_tag = _TAG_DISPLAY.get(selected_pm_display)
        if pm_tag:
            filtered = filtered[filtered["_tag"] == pm_tag]

    # ── 최신일 기준 정렬 ──────────────────────────────────────────────────────
    if "review_date" in filtered.columns:
        filtered = filtered.sort_values("review_date", ascending=False)

    st.markdown(f"**총 {len(filtered):,}개** 리뷰")

    # ── 더보기 pagination ─────────────────────────────────────────────────────
    page_key = "review_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    filter_sig = f"{search_query}|{selected_app}|{selected_score}|{selected_version}|{selected_pm_display}"
    sig_key = "review_filter_sig"
    if st.session_state.get(sig_key) != filter_sig:
        st.session_state[page_key] = 1
        st.session_state[sig_key] = filter_sig

    page = st.session_state[page_key]
    show_count = PAGE_SIZE * page
    display_df = filtered.head(show_count).copy()

    # ── 노출 컬럼 선택 ────────────────────────────────────────────────────────
    display_cols = [
        c for c in
        ["app_name", "platform", "score", "review_date", "content",
         "action", "review_created_version", "thumbs_up_count"]
        if c in display_df.columns
    ]

    col_rename = {
        "app_name": "앱",
        "platform": "플랫폼",
        "score": "평점",
        "review_date": "작성일",
        "content": "리뷰 내용",
        "action": "PO/PM 대응 필요사항",
        "review_created_version": "버전",
        "thumbs_up_count": "👍",
    }

    tags = display_df["_tag"].reset_index(drop=True)
    col_df = display_df[display_cols].rename(columns=col_rename).reset_index(drop=True)

    def _style_action_col(_):
        styles = []
        for tag in tags:
            _, text_color, _ = _TAG_META.get(tag, ("", "#94A3B8", "transparent"))
            styles.append(f"color:{text_color};font-weight:600;")
        return styles

    styled = col_df.style.apply(_style_action_col, subset=["PO/PM 대응 필요사항"], axis=0)

    st.dataframe(
        styled,
        use_container_width=True,
        height=520,
        column_config={
            "리뷰 내용": st.column_config.TextColumn(width="large"),
            "PO/PM 대응 필요사항": st.column_config.TextColumn(width="large"),
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
