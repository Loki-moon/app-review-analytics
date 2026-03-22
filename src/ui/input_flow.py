"""
입력 플로우 UI 컴포넌트
- 상단 컨트롤 바 (기간 + 플랫폼 토글)
- 플랫폼 선택 (32-3)
- 앱 슬롯 + 검색 (32-4)
- 기간 선택 + 빠른 버튼 (32-5)
"""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from config.settings import MAX_APPS, PLATFORMS
from src.scraper import get_scraper



# ─────────────────────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────────────────────

_PERIOD_MAP = [
    ("1개월", 30),
    ("3개월", 90),
    ("6개월", 180),
    ("12개월", 365),
    ("18개월", 545),
    ("24개월", 730),
    ("30개월", 910),
    ("36개월", 1095),
]

# 화면에 표시할 플랫폼 순서 + 짧은 라벨
_CTRL_PLATFORMS = [
    ("Google Play Store", "Google Play", "#22C55E"),
    ("Apple App Store", "App Store", "#22C55E"),
    ("Samsung Galaxy Store", "Galaxy Store", "#FB7185"),
    ("One Store", "One Store", "#FB7185"),
]


# ─────────────────────────────────────────────────────────────────────────────
# 상단 컨트롤 바
# ─────────────────────────────────────────────────────────────────────────────

def render_controls_bar() -> None:
    """기간 선택 + 플랫폼 토글 바 렌더링."""
    today = date.today()

    notice = st.session_state.pop("_platform_notice", None)
    if notice:
        st.toast(notice, icon="⚠️")

    # pending period 먼저 적용 (위젯 렌더 이전에 반드시 실행)
    if "pending_start" in st.session_state:
        _ps = st.session_state.pop("pending_start")
        _pe = st.session_state.pop("pending_end")
        st.session_state["start_date"] = _ps
        st.session_state["end_date"]   = _pe
        # date_start/date_end 키는 위젯이 직접 관리 — value= 충돌 방지를 위해 제거 후 재초기화
        st.session_state.pop("date_start", None)
        st.session_state.pop("date_end",   None)
        st.session_state["date_start"] = _ps
        st.session_state["date_end"]   = _pe

    start_date: date = st.session_state.get("start_date", today - timedelta(days=30))
    end_date: date   = st.session_state.get("end_date", today)

    # 위젯 키 미초기화 시 기본값 설정 (value= 파라미터 없이 key= 만 사용하기 위함)
    if "date_start" not in st.session_state:
        st.session_state["date_start"] = start_date
    if "date_end" not in st.session_state:
        st.session_state["date_end"] = end_date
    selected_platforms: list[str] = st.session_state.get("selected_platforms", ["Google Play Store"])

    st.markdown("""
    <div style="
    padding:16px 22px;
    margin-bottom:22px;
    max-width:100%;
    margin-left:auto;
    margin-right:auto;
    border:1px solid rgba(255,255,255,0.05);
    border-radius:10px;
    background:rgba(255,255,255,0.02);
    color:rgba(210,210,210,0.75);
    font-size:0.88rem;
    font-weight:300;
    line-height:1.65;
    letter-spacing:0.02em;
    text-align:center;
    ">

    본 대시보드는 학술 연구를 위해 개발중인 대시보드입니다.
    연구 결과와 논문이 공식적으로 공개되기 전까지 임의 배포를 금지합니다.

    <div style="
    width:70%;
    margin:10px auto 12px auto;
    border-top:1px solid rgba(255,255,255,0.15);
    "></div>

    <span style="
    color:rgba(200,200,200,0.55);
    font-size:0.82rem;
    font-style:italic;
    ">
    This dashboard was developed for academic research purposes.
    Unauthorized distribution is prohibited until the paper is officially published.
    </span>

    <div style="
    margin-top:16px;
    font-size:0.78rem;
    letter-spacing:0.08em;
    color:rgba(180,180,180,0.6);
    ">
    ― Loki Moon ―
    </div>

    <div style="
    font-size:0.72rem;
    color:rgba(160,160,160,0.45);
    margin-top:2px;
    ">
    wata0414@gmail.com
    </div>

    </div>
    """, unsafe_allow_html=True)


    col_left, col_right = st.columns([7, 5])

    with col_left:
        st.markdown("##### 분석 기간")
        # 날짜 입력 행
        dc1, dc2, dc3 = st.columns([5, 1, 5])
        with dc1:
            new_start = st.date_input(
                "시작일",
                max_value=today, key="date_start",
                label_visibility="collapsed",
            )
        with dc2:
            st.markdown(
                '<p style="text-align:center;margin:0;padding-top:6px;font-size:1rem;">–</p>',
                unsafe_allow_html=True,
            )
        with dc3:
            new_end = st.date_input(
                "종료일",
                max_value=today, key="date_end",
                label_visibility="collapsed",
            )

        # 날짜 직접 변경 감지
        if new_start != start_date or new_end != end_date:
            st.session_state["start_date"] = new_start
            st.session_state["end_date"]   = new_end
            st.rerun()

        # 기간 빠른 선택 버튼
        current_days = max((end_date - start_date).days, 0)
        pcols = st.columns(len(_PERIOD_MAP))
        for i, (label, days) in enumerate(_PERIOD_MAP):
            with pcols[i]:
                is_active = abs(current_days - days) <= 2
                if st.button(
                    label,
                    key=f"ctrl_period_{days}",
                    type="primary" if is_active else "secondary",
                ):
                    # pending 방식: 다음 rerun 시작 전에 적용됨 (Fix 3)
                    st.session_state["pending_start"] = today - timedelta(days=days)
                    st.session_state["pending_end"]   = today
                    st.rerun()

    with col_right:
        st.markdown("##### 앱 마켓 플랫폼 설정")
        new_platforms = list(selected_platforms)
        changed = False

        st.markdown('<div class="platform-toggle-group">', unsafe_allow_html=True)
        tcols = st.columns(len(_CTRL_PLATFORMS))
        for i, (key, short_label, label_color) in enumerate(_CTRL_PLATFORMS):
            with tcols[i]:
                is_on = key in selected_platforms
                toggled = st.toggle(short_label, value=is_on, key=f"ctrl_plat_{i}")
                if toggled != is_on:
                    meta = PLATFORMS.get(key, {})

                    if toggled and not meta.get("supported", False):
                        st.session_state["_platform_notice"] = (
                            meta.get("note") or f"{short_label}는 현재 제한적으로 지원됩니다."
                        )

                    if toggled and key not in new_platforms:
                        new_platforms.append(key)
                    elif not toggled and key in new_platforms:
                        new_platforms.remove(key)

                    changed = True
        st.markdown('</div>', unsafe_allow_html=True)
        if changed:
            st.session_state["selected_platforms"] = new_platforms
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# 플랫폼 선택 (PRD 32-3)
# ─────────────────────────────────────────────────────────────────────────────

def render_platform_select() -> list[str]:
    st.markdown('<div id="section-platform"></div>', unsafe_allow_html=True)
    st.markdown("#### 분석 플랫폼 선택")
    st.caption("최소 1개 이상 선택해주세요. Google Play Store만 실시간 수집을 지원합니다.")

    selected = []
    cols = st.columns(len(PLATFORMS))
    for i, (label, meta) in enumerate(PLATFORMS.items()):
        with cols[i]:
            checked = st.checkbox(
                label,
                value=(label in st.session_state.get("selected_platforms", ["Google Play Store"])),
                key=f"platform_{meta['key']}",
            )
            if checked:
                selected.append(label)
            if meta["supported"]:
                st.markdown('<span class="badge badge-platform-ok">지원</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="badge badge-platform-na">제한적</span>', unsafe_allow_html=True)

    st.session_state["selected_platforms"] = selected
    return selected


# ─────────────────────────────────────────────────────────────────────────────
# 기간 선택 UI (PRD 32-5)
# ─────────────────────────────────────────────────────────────────────────────

def render_date_range() -> tuple[date, date, bool]:
    """기간 선택 + 빠른 선택 버튼"""
    st.markdown('<div id="section-date"></div>', unsafe_allow_html=True)
    st.markdown("#### 리뷰 수집 기간")

    today = date.today()

    quick_map = {"1개월": 30, "3개월": 90, "6개월": 180, "9개월": 210, "12개월": 365, "18개월": 545, "24개월": 730, "30개월": 910, "36개월": 1095}
    qc = st.columns(len(quick_map))
    for i, (label, days) in enumerate(quick_map.items()):
        with qc[i]:
            if st.button(label, key=f"quick_{days}"):
                st.session_state["start_date"] = today - timedelta(days=days)
                st.session_state["end_date"] = today
                st.session_state.pop("date_start", None)
                st.session_state.pop("date_end",   None)
                st.rerun()

    # 위젯 키 미초기화 시 기본값 설정
    if "date_start" not in st.session_state:
        st.session_state["date_start"] = st.session_state.get("start_date", today - timedelta(days=365))
    if "date_end" not in st.session_state:
        st.session_state["date_end"] = st.session_state.get("end_date", today)

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input(
            "시작일",
            max_value=today,
            key="date_start",
        )
    with col2:
        end = st.date_input(
            "종료일",
            max_value=today,
            key="date_end",
        )

    valid = True
    if end < start:
        st.error("종료일은 시작일보다 이후여야 합니다.")
        valid = False
    elif (end - start).days > 365 * 3:
        st.warning("수집 기간이 3년을 초과합니다. 성능 저하가 발생할 수 있어요.")

    st.session_state["start_date"] = start
    st.session_state["end_date"] = end
    return start, end, valid


# ─────────────────────────────────────────────────────────────────────────────
# 앱 검색 + 슬롯 UI (PRD 32-4)
# ─────────────────────────────────────────────────────────────────────────────

def render_app_slots():
    """5개 고정 슬롯 항상 표시"""
    selected_apps = st.session_state.get("selected_apps", [])
    st.markdown("#### 선택된 앱")

    slot_cols = st.columns(5)
    for i in range(MAX_APPS):
        with slot_cols[i]:
            if i < len(selected_apps):
                app = selected_apps[i]
                icon_html = (
                    f'<img src="{app.icon_url}" width="36" style="border-radius:6px;margin-bottom:4px;" />'
                    if app.icon_url else "📱"
                )
                st.markdown(f"""
                <div class="slot-filled">
                    {icon_html}
                    <div class="slot-app-name">{app.app_name[:12]}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("✕", key=f"slot_remove_{i}", help="제거"):
                    st.session_state["selected_apps"].pop(i)
                    st.rerun()
            else:
                st.markdown(f"""
                <div class="slot-empty">
                    <span class="slot-number">{i+1}</span>
                </div>
                """, unsafe_allow_html=True)


# 추천 검색어
_QUICK_SEARCHES = ["카카오페이", "네이버페이", "배달의민족", "쿠팡이츠", "OK캐쉬백", "캐시워크", "당근마켓", "넷플릭스", "올리브영", "무신사", "토스", "쿠팡"]





_SUPPORTED_SEARCH_PLATFORMS = {
    "Google Play Store": "google_play",
    "Apple App Store":   "app_store",
}


def _app_fingerprint(a) -> str:
    return a.app_id if a.app_id else f"__name__{a.app_name}__{a.platform}"


def _name_similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _pair_results(gp_list, as_list, threshold: float = 0.30):
    """GP 결과와 AS 결과를 이름 유사도로 1:1 매칭"""
    used: set[int] = set()
    pairs = []
    for gp in gp_list:
        best_i, best_score = None, 0.0
        for i, a in enumerate(as_list):
            if i in used:
                continue
            score = _name_similarity(gp.app_name, a.app_name)
            if score > best_score:
                best_score, best_i = score, i
        ios = None
        if best_i is not None and best_score >= threshold:
            ios = as_list[best_i]
            used.add(best_i)
        pairs.append((gp, ios))
    return pairs


def _app_info_block(app) -> None:
    """아이콘 + 앱 정보 한 줄 블록"""
    c_ic, c_tx = st.columns([1, 5])
    with c_ic:
        if app.icon_url:
            st.image(app.icon_url, width=36)
        else:
            st.markdown("📱")
    with c_tx:
        rating_str = f"⭐ {app.rating:.1f}" if app.rating else ""
        plat_badge = "Play" if "Google" in app.platform else "App Store"
        st.markdown(f"""
        <div style="padding:1px 0">
          <b style="font-size:0.88rem">{app.app_name[:22]}</b>
          <span style="font-size:0.66rem;background:#3A3A3A;color:#C4B5FD;
            border-radius:4px;padding:1px 5px;margin-left:4px;">{plat_badge}</span><br>
          <span style="font-size:0.74rem;color:var(--text-sub)">
            {app.developer[:20]} &nbsp;|&nbsp; {rating_str}<br>
            <code style="font-size:0.67rem">{app.app_id}</code>
          </span>
        </div>
        """, unsafe_allow_html=True)


def render_app_search(selected_platforms: list[str]):
    """앱 검색 + 결과 카드 (플랫폼별 구분)"""
    st.markdown('<div id="section-search"></div>', unsafe_allow_html=True)

    # 중복 선택 alert
    if st.session_state.pop("_dup_alert", False):
        import streamlit.components.v1 as components
        components.html(
            "<script>window.parent.alert('이미 선택된 앱입니다.');</script>",
            height=0,
        )

    selected_apps = st.session_state.get("selected_apps", [])
    confirmed_fps = {_app_fingerprint(a) for a in selected_apps}
    # MAX_APPS는 고유 앱 이름 기준 (GP+AS 쌍은 1개로 계산)
    unique_app_count = len({a.app_name for a in selected_apps})
    full = unique_app_count >= MAX_APPS

    st.markdown("##### 앱 검색")

    # 검색 가능한 플랫폼이 하나도 없으면 안내
    searchable = [p for p in selected_platforms if p in _SUPPORTED_SEARCH_PLATFORMS]
    if not searchable:
        st.markdown(
            '<div class="warn-box">Google Play Store 또는 App Store를 선택하면 앱을 검색할 수 있어요.</div>',
            unsafe_allow_html=True,
        )
        return

    # 첫 진입 시 기본 검색어 설정
    if "search_results" not in st.session_state:
        st.session_state["search_query_override"] = "카카오 파스타"

        # 검색 안내 문구
    st.markdown("""
    <div style="margin-bottom:6px;">
    아래 입력창에 분석하려는 앱의 이름을 입력하고 <b>Enter</b>를 눌러주세요. 마켓에 출시된 모든 APP을 선택할 수 있습니다.
    </div>
    """, unsafe_allow_html=True)

    # 검색창 스타일
    st.markdown("""
    <style>
    div[data-testid="stTextInput"] > div > div > input {
        background-color: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.16) !important;
        border-radius: 12px !important;
        color: #F3F4F6 !important;
        box-shadow: none !important;
    }

    div[data-testid="stTextInput"] > div > div {
        background-color: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.16) !important;
        border-radius: 12px !important;
    }

    div[data-testid="stTextInput"] > div > div:focus-within {
        border: 1px solid rgba(99, 102, 241, 0.85) !important;
        box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.18) !important;
    }

    div[data-testid="stTextInput"] input::placeholder {
        color: rgba(156, 163, 175, 0.9) !important;
    }

    div[data-testid="stCaptionContainer"] {
        margin-top: 0rem !important;
        margin-bottom: 0rem !important;
    }

    div[data-testid="stCaptionContainer"] p {
        margin-top: 0px !important;
        margin-bottom: 2px !important;
        line-height: 0.75 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.caption("⚠️ (주의-1) Android와 iOS의 연관 검색 로직이 상이하기 때문에 연관된 앱의 OS가 다른 앱이 설정될 수 있습니다.")
    st.caption("⚠️ (주의-2) 애버랜드와 같은 앱은 Android는 한글 애버랜드, iOS는 영어 everland입니다. OS 통합 확인이 불가능합니다.")

    query = st.text_input(
        "",
        placeholder="이곳에 분석할 앱의 이름을 직접 입력한 뒤, Enter 버튼을 눌러주세요.",
        key="search_input",
        disabled=full,
    )

    # 빠른 검색 버튼
    qcols = st.columns(len(_QUICK_SEARCHES))
    for i, label in enumerate(_QUICK_SEARCHES):
        with qcols[i]:
            if st.button(label, key=f"qk_{i}", disabled=full):
                st.session_state["search_query_override"] = label

    query = st.session_state.pop("search_query_override", query) or query

    if full:
        st.caption(f"이미 {MAX_APPS}개 앱을 선택했습니다.")
        return

    # 검색 실행 — 선택된 지원 플랫폼별로 수행
    search_key = f"{query}|{'|'.join(sorted(searchable))}"
    if query and search_key != st.session_state.get("_last_search_key", ""):
        st.session_state["_last_search_key"] = search_key
        st.session_state["_last_search_query"] = query
        combined: list = []
        with st.spinner("앱을 검색하고 있어요..."):
            for platform_name in searchable:
                plat_key = _SUPPORTED_SEARCH_PLATFORMS[platform_name]
                try:
                    scraper = get_scraper(plat_key)
                    results = scraper.search_apps(query, n=5)
                    combined.extend(results)
                except Exception as e:
                    st.warning(f"[{platform_name}] 검색 중 오류: {e}")
        st.session_state["search_results"] = combined

    # 검색 결과 카드
    results = st.session_state.get("search_results", [])
    if not results:
        return

    st.markdown("""
    <div style="margin-top:28px;"></div>
    """, unsafe_allow_html=True)

    st.markdown(f"**'{st.session_state.get('_last_search_query', '')}' 검색 결과**")

    gp_results = [r for r in results if r.platform == "Google Play Store"]
    as_results = [r for r in results if r.platform == "Apple App Store"]
    both = bool(gp_results and as_results)

    if both:
        # ── 페어 카드 (GP 좌 / AS 우) ──────────────────────────────────────
        pairs = _pair_results(gp_results, as_results)
        for gp_app, ios_app in pairs:
            import dataclasses
            gp_fp  = _app_fingerprint(gp_app)
            ios_fp = _app_fingerprint(ios_app) if ios_app else None
            already = gp_fp in confirmed_fps

            c_gp, c_div, c_as, c_btn = st.columns([5, 0.05, 5, 2])
            with c_gp:
                _app_info_block(gp_app)
            with c_div:
                st.markdown('<div style="border-left:1px solid #333;height:100%;min-height:56px;"></div>',
                            unsafe_allow_html=True)
            with c_as:
                if ios_app:
                    _app_info_block(ios_app)
                else:
                    st.caption("App Store 매칭 결과 없음")

            _akey = f"GP_{gp_app.app_id or gp_app.app_name}"
            with c_btn:
                if already:
                    st.button("✅ 선택됨", key=f"done_{_akey}", disabled=True)
                elif unique_app_count < MAX_APPS:
                    if st.button("분석할 앱으로 선택하기", key=f"sel_{_akey}"):
                        apps_added = st.session_state["selected_apps"]
                        if gp_fp not in confirmed_fps:
                            apps_added.append(gp_app)
                        # AS: 같은 app_name으로 통일해 파이프라인에서 리뷰 합산
                        if ios_app and ios_fp and ios_fp not in confirmed_fps:
                            apps_added.append(
                                dataclasses.replace(ios_app, app_name=gp_app.app_name)
                            )
                        st.rerun()
                else:
                    st.button("선택 불가", key=f"full_{_akey}", disabled=True)
            st.divider()
    else:
        # ── 단일 플랫폼 카드 (기존) ────────────────────────────────────────
        for app in results:
            fp = _app_fingerprint(app)
            is_selected = fp in confirmed_fps
            c_icon, c_info, c_btn = st.columns([1, 7, 2])
            with c_icon:
                if app.icon_url:
                    st.image(app.icon_url, width=44)
                else:
                    st.markdown("📱")
            with c_info:
                rating_str = f"⭐ {app.rating:.1f}" if app.rating else ""
                st.markdown(f"""
                <div style="padding:2px 0">
                  <b style="font-size:0.92rem">{app.app_name}</b>
                  <span style="font-size:0.72rem;background:#3A3A3A;color:#C4B5FD;
                    border-radius:4px;padding:1px 6px;margin-left:6px;">{app.platform}</span><br>
                  <span style="font-size:0.78rem;color:var(--text-sub)">
                    {app.developer} &nbsp;|&nbsp; {rating_str} &nbsp;|&nbsp;
                    <code style="font-size:0.7rem">{app.app_id}</code>
                  </span>
                </div>
                """, unsafe_allow_html=True)
            _akey = f"{app.platform}_{app.app_id or app.app_name}"
            with c_btn:
                if is_selected:
                    st.button("✅ 선택됨", key=f"done_{_akey}", disabled=True)
                elif not app.app_id:
                    manual_id = st.text_input(
                        "패키지 ID 직접 입력",
                        placeholder="com.example.app",
                        key=f"manual_{_akey}",
                        label_visibility="collapsed",
                    )
                    if st.button("추가", key=f"manual_add_{_akey}") and manual_id.strip():
                        import dataclasses
                        fixed = dataclasses.replace(app, app_id=manual_id.strip())
                        if _app_fingerprint(fixed) in confirmed_fps:
                            st.session_state["_dup_alert"] = True
                        else:
                            st.session_state["selected_apps"].append(fixed)
                        st.rerun()
                elif unique_app_count < MAX_APPS:
                    if st.button("분석할 앱으로 선택하기", key=f"sel_{_akey}"):
                        if fp in confirmed_fps:
                            st.session_state["_dup_alert"] = True
                        else:
                            st.session_state["selected_apps"].append(app)
                        st.rerun()
                else:
                    st.button("선택 불가", key=f"full_{_akey}", disabled=True)
            st.divider()
