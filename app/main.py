"""
App Review Intelligence Lab — Streamlit 메인 앱 (PRD 1-32 통합)
"""
from __future__ import annotations

import sys
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import DATA_RAW_DIR, DEFAULT_REVIEW_COUNT, MAX_APPS, PLATFORMS
from src.scraper import get_scraper
from src.analysis.pipeline import run_pipeline
from src.analysis.validation import run_all_validations
from src.ui.css import get_css
from src.ui.input_flow import render_app_search, render_controls_bar
from src.visualization import (
    tab_review, tab_keyword, tab_odds, tab_priority, tab_validation,
    single_view, compare_view,
)
from src.visualization._common import get_icon_color

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="App Review Intelligence Lab",
    page_icon="🦜",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 세션 상태 초기화 ──────────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "page": "input",
    "selected_platforms": ["Google Play Store", "Apple App Store"],
    "selected_apps": [],
    "start_date": date.today() - timedelta(days=365),
    "end_date": date.today(),
    "raw_df": pd.DataFrame(),
    "pipeline_result": {},
    "validation_result": {},
    "errors": [],
    "analysis_done": False,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── CSS 주입 ──────────────────────────────────────────────────────────────────
st.markdown(get_css(), unsafe_allow_html=True)

_APP_COLORS = ["#4F8EF7", "#F7844F", "#4FD6A5", "#C84FF7", "#F7D84F"]

# 결과 탭 목록
_RESULT_TABS = [
    ("📊", "분석 Summary"),
    ("📋", "리뷰 상세 분석"),
    ("☁️", "키워드 탐색"),
    ("📈", "오즈비 분석"),
    ("🔬", "통계 검증"),
]

# 플랫폼 이름 → scraper key 매핑
_PLATFORM_KEY_MAP: dict[str, str] = {
    name: meta["key"] for name, meta in PLATFORMS.items()
}


# ─────────────────────────────────────────────────────────────────────────────
# JS 플로팅 버튼 — 위치 고정
# ─────────────────────────────────────────────────────────────────────────────

def _inject_float_btn_js():
    components.html("""
    <script>
    (function() {
        function fix() {
            var doc = window.parent.document;
            var btns = doc.querySelectorAll('.stButton > button');
            for (var b of btns) {
                if (b.dataset.floatFixed) continue;
                var txt = (b.innerText || '').trim();
                if (txt.includes('분석 시작하기')) {
                    var wrap = b.closest('.element-container');
                    if (wrap) {
                        wrap.style.cssText = [
                            'position:fixed',
                            'bottom:24px',
                            'right:24px',
                            'z-index:9998',
                            'width:auto',
                            'min-width:180px',
                            'max-width:320px'
                        ].join('!important;') + '!important';
                    }
                    b.style.cssText = [
                        'background:#3430B8',
                        'border:1px solid #2B2796',
                        'box-shadow:0 12px 30px rgba(0,0,0,0.45)',
                        'color:#FFFFFF',
                        'font-size:0.92rem',
                        'padding:0.65rem 1.4rem',
                        'border-radius:12px'
                    ].join('!important;') + '!important';
                    b.dataset.floatFixed = '1';
                    break;
                }
            }
        }
        setTimeout(fix, 200);
        new MutationObserver(function() { setTimeout(fix, 60); })
            .observe(window.parent.document.body, {childList: true, subtree: false});
    })();
    </script>
    """, height=0)


def _show_browser_alert(msg: str):
    """네이티브 브라우저 alert 표시"""
    safe = msg.replace('"', '\\"')
    components.html(f'<script>window.parent.alert("{safe}");</script>', height=0)


# ─────────────────────────────────────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────────────────────────────────────

def _render_sidebar():
    apps = st.session_state.selected_apps
    done = st.session_state.analysis_done
    is_result = st.session_state.page == "result"

    with st.sidebar:
        st.markdown(
            '<div style="padding:6px 0 4px;font-size:1.05rem;font-weight:800;color:var(--primary);">'
            'App Review Analysis</div>',
            unsafe_allow_html=True,
        )

        st.divider()

        st.markdown(
            '<div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;'
            'letter-spacing:.08em;color:var(--text-sub);padding:2px 0 4px;">네비게이션</div>',
            unsafe_allow_html=True,
        )

        if st.button("📋 분석 설정", use_container_width=True,
                     type="primary" if not is_result else "secondary"):
            st.session_state.page = "input"
            st.rerun()

        if st.button("📊 분석 결과", use_container_width=True,
                     type="primary" if is_result else "secondary"):
            if not done:
                st.session_state["_alert_no_analysis"] = True
                st.rerun()
            else:
                st.session_state.page = "result"
                st.rerun()

        # 분석 결과 하위 탭 메뉴 — 항상 표시, 미완료 시 alert, 완료 시 해당 탭으로 이동
        for i, (icon, label) in enumerate(_RESULT_TABS):
            if st.button(
                f"  {icon} {label}",
                key=f"nav_sub_{label}",
                use_container_width=True,
                type="secondary",
            ):
                if not done:
                    st.session_state["_alert_no_analysis"] = True
                    st.rerun()
                else:
                    st.session_state.page = "result"
                    st.session_state["_active_tab"] = i
                    st.rerun()

        st.divider()

        if apps:
            # app_name 기준으로 중복 제거 (GP+AS 쌍은 1개로 표시)
            seen: set[str] = set()
            unique_apps: list = []
            for a in apps:
                if a.app_name not in seen:
                    seen.add(a.app_name)
                    unique_apps.append(a)
            n_unique = len(unique_apps)
            st.markdown(
                f'<div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.08em;color:var(--text-sub);padding:2px 0 4px;">'
                f'선택된 앱 ({n_unique}/{MAX_APPS})</div>',
                unsafe_allow_html=True,
            )
            for ui, app in enumerate(unique_apps):
                color = get_icon_color(getattr(app, "icon_url", ""), _APP_COLORS[ui % len(_APP_COLORS)])
                # 어떤 플랫폼이 포함됐는지 확인
                plats = {a.platform for a in apps if a.app_name == app.app_name}
                has_android = "Google Play Store" in plats
                has_ios     = "Apple App Store" in plats
                plat_badge  = ("Android · iOS" if has_android and has_ios
                               else "Android" if has_android else "iOS")
                st.markdown(
                    f'<div style="font-size:0.8rem;padding:4px 0;border-left:3px solid {color};'
                    f'padding-left:7px;margin:1px 0;color:var(--text-main);">'
                    f'{app.app_name}'
                    f'<span style="font-size:0.68rem;color:var(--text-sub);margin-left:4px;">'
                    f'{plat_badge}</span></div>',
                    unsafe_allow_html=True,
                )
            st.divider()

        if done:
            if st.button("🔄 분석 초기화", use_container_width=True):
                for k in ["analysis_done", "pipeline_result", "raw_df",
                          "selected_apps", "errors", "validation_result",
                          "_last_search_query", "search_results"]:
                    st.session_state.pop(k, None)
                st.session_state.page = "input"
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# 헤더 앱 슬롯 (검색 pill 스타일)
# ─────────────────────────────────────────────────────────────────────────────

def _render_header_chips():
    apps = st.session_state.selected_apps

    if not apps:
        st.markdown(
            '<div class="header-app-chips">'
            '<span class="app-slot-pill"><span class="pill-icon">🔍</span>'
            '<span class="pill-text">분석할 앱을 추가하세요</span></span>'
            '<span class="vs-chip">VS</span>'
            '<span class="app-slot-pill"><span class="pill-icon">🔍</span>'
            '<span class="pill-text">비교할 앱을 추가하세요</span></span>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # app_name 기준 중복 제거 (GP+AS 쌍 → 1개)
    seen: set[str] = set()
    unique_apps: list = []
    for a in apps:
        if a.app_name not in seen:
            seen.add(a.app_name)
            unique_apps.append(a)

    # ── 비주얼 pill 행 (표시 전용) ────────────────────────────────────────────
    slots: list[str] = []
    for i, app in enumerate(unique_apps):
        if app.icon_url:
            icon_html = (
                f'<img src="{app.icon_url}" width="20" height="20" '
                f'style="border-radius:4px;object-fit:cover;flex-shrink:0;" />'
            )
        else:
            color = _APP_COLORS[i % len(_APP_COLORS)]
            icon_html = f'<span class="pill-icon" style="color:{color};">●</span>'
        name = app.app_name[:16]
        slots.append(
            f'<span class="app-slot-pill filled">'
            f'{icon_html}'
            f'<span class="pill-text">{name}</span>'
            f'</span>'
        )
        if i < len(unique_apps) - 1:
            slots.append('<span class="vs-chip">VS</span>')

    # MAX_APPS는 고유 앱 수 기준
    if len(unique_apps) < MAX_APPS:
        slots.append('<span class="header-add-btn" id="hdr-add-btn">+</span>')

    st.markdown(
        f'<div class="header-app-chips" id="header-chips-wrap">{"".join(slots)}</div>',
        unsafe_allow_html=True,
    )

    # ── 앱 제거 버튼 행 — 입력 설정 페이지에서만 표시 ─────────────────────
    if st.session_state.get("page", "input") == "input":
        st.markdown("""
        <style>
        div[data-testid="stHorizontalBlock"] .chip-rm-btn button {
            padding: 1px 8px !important;
            font-size: 0.72rem !important;
            border-radius: 12px !important;
            height: auto !important;
            min-height: 0 !important;
            line-height: 1.4 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        n = len(unique_apps)
        rm_cols = st.columns([2] * n + [max(1, 10 - n * 2)])
        for i, app in enumerate(unique_apps):
            # 10자 초과 시 말줄임
            label_name = (app.app_name[:9] + "…") if len(app.app_name) > 10 else app.app_name
            with rm_cols[i]:
                with st.container():
                    st.markdown('<div class="chip-rm-btn">', unsafe_allow_html=True)
                    if st.button(f"{label_name} 선택 해제", key=f"hdr_rm_{i}",
                                 help=f"{app.app_name} 선택 해제", type="secondary",
                                 use_container_width=True):
                        # 같은 app_name을 가진 모든 항목(GP+AS) 제거
                        st.session_state.selected_apps = [
                            a for a in st.session_state.selected_apps
                            if a.app_name != app.app_name
                        ]
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

    # + 버튼 툴팁 JS (최대 개수 안내)
    components.html("""
    <script>
    (function() {
        function setup() {
            var doc = window.parent.document;
            var addBtn = doc.getElementById('hdr-add-btn');
            if (addBtn && !addBtn.dataset.jsSetup) {
                addBtn.dataset.jsSetup = '1';
                addBtn.addEventListener('click', function() {
                    var tip = doc.getElementById('hdr-add-tip');
                    if (!tip) {
                        tip = doc.createElement('div');
                        tip.id = 'hdr-add-tip';
                        tip.style.cssText = [
                            'position:fixed','top:46px','z-index:10002',
                            'background:#2A2A2A','color:#EAEAEA','font-size:0.8rem',
                            'padding:6px 14px','border-radius:8px','border:1px solid #3A3A3A',
                            'white-space:nowrap','pointer-events:none','transition:opacity 0.2s'
                        ].join(';');
                        doc.body.appendChild(tip);
                    }
                    var rect = addBtn.getBoundingClientRect();
                    tip.style.left = Math.max(0, rect.left - 40) + 'px';
                    tip.textContent = '최대 5개까지 추가할 수 있어요!';
                    tip.style.opacity = '1';
                    tip.style.display = 'block';
                    clearTimeout(window._addTipTimer);
                    window._addTipTimer = setTimeout(function() {
                        tip.style.opacity = '0';
                        setTimeout(function() { tip.style.display = 'none'; }, 200);
                    }, 3000);
                });
            }
        }
        setTimeout(setup, 150);
        new MutationObserver(function() { setTimeout(setup, 60); })
            .observe(window.parent.document.body, {childList: true, subtree: false});
    })();
    </script>
    """, height=0)


# ─────────────────────────────────────────────────────────────────────────────
# 로딩 UI
# ─────────────────────────────────────────────────────────────────────────────

_LOADING_STAGES = [
    ("🦜", "분석 조회 접수 완료!", "앵무새가 준비 중이에요...", 0),
    ("✈️", "앱 마켓으로 날아가고 있어요", "접속하는 중...", 10),
    ("🔍", "리뷰를 하나씩 확인하고 있어요", "수집 중... 조금만 기다려주세요!", 20),
    ("✨", "거의 완료되었어요!", "데이터를 정리하고 있어요...", 70),
    ("🏠", "돌아오고 있어요", "수집 결과를 가져오는 중...", 85),
    ("🔬", "전처리 중", "형태소 분석 및 불용어 제거 중...", 90),
    ("📊", "분석 완료!", "결과를 불러오는 중...", 99),
]

_STAGE_LABELS = ["접수", "접속", "수집", "정리", "반환", "분석", "완료"]


def _render_loading(placeholder, parrot: str, stage: str, detail: str, pct: int, stage_idx: int = 0):
    pct = min(pct, 100)
    n = len(_STAGE_LABELS)

    # ── 전체 진행 %: 단계 기반 (stage_idx / max_stage * 100) ──────────────────
    overall_pct = round(stage_idx / (n - 1) * 100) if n > 1 else 100
    # 수집 단계(stage 2)처럼 한 단계 내 pct가 긴 경우, 다음 단계 비율까지 부분 반영
    next_stage_pct = round((stage_idx + 1) / (n - 1) * 100) if stage_idx < n - 1 else 100
    stage_share = (pct - _LOADING_STAGES[stage_idx][3]) / max(
        (_LOADING_STAGES[min(stage_idx + 1, n - 1)][3] - _LOADING_STAGES[stage_idx][3]), 1
    )
    overall_pct = round(overall_pct + (next_stage_pct - overall_pct) * max(0, min(1, stage_share)))

    # ── 단조 증가 보장: 이전 최댓값 이하로 내려가지 않음 ──────────────────────
    prev_max = st.session_state.get("_loading_max_pct", 0)
    overall_pct = max(overall_pct, prev_max)
    st.session_state["_loading_max_pct"] = overall_pct

    # stepper track: 완료된 구간 비율
    track_pct = (stage_idx / (n - 1) * 100) if n > 1 else 100

    step_html = ""
    for i, lbl in enumerate(_STAGE_LABELS):
        if i < stage_idx:
            # 완료 — 체크 아이콘
            step_html += (
                f'<div class="loading-step">'
                f'<div class="loading-step-dot dot-done">&#10003;</div>'
                f'<div class="loading-step-lbl lbl-done">{lbl}</div>'
                f'</div>'
            )
        elif i == stage_idx:
            step_html += (
                f'<div class="loading-step">'
                f'<div class="loading-step-dot dot-active"></div>'
                f'<div class="loading-step-lbl lbl-active">{lbl}</div>'
                f'</div>'
            )
        else:
            step_html += (
                f'<div class="loading-step">'
                f'<div class="loading-step-dot dot-pending"></div>'
                f'<div class="loading-step-lbl lbl-pending">{lbl}</div>'
                f'</div>'
            )

    with placeholder.container():
        st.markdown(f"""
        <div class="loading-overlay">
            <div class="loading-modal">
                <div class="loading-overall">
                    <div class="loading-overall-toprow">
                        <span class="loading-overall-title">전체 진행</span>
                        <span class="loading-overall-pct">{overall_pct}%</span>
                    </div>
                    <div class="loading-overall-bar">
                        <div class="loading-overall-bar-fill" style="width:{overall_pct}%;"></div>
                    </div>
                    <div class="loading-stepper">
                        <div class="loading-stepper-track">
                            <div class="loading-stepper-track-fill" style="width:{track_pct:.1f}%;"></div>
                        </div>
                        {step_html}
                    </div>
                </div>
                <span class="loading-parrot">{parrot}</span>
                <div class="loading-stage">{stage}</div>
                <div class="loading-detail">{detail}</div>
                <div class="loading-bar-wrap">
                    <div class="loading-bar-fill" style="width:{pct}%;"></div>
                </div>
                <div class="loading-pct">{pct}%</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 분석 실행
# ─────────────────────────────────────────────────────────────────────────────

def _save_raw(df: pd.DataFrame, platform_key: str, app_id: str) -> None:
    ts = datetime.now().strftime("%Y%m%d")
    path = DATA_RAW_DIR / f"{platform_key}_{app_id}_{ts}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")


def run_analysis():
    apps = st.session_state.selected_apps
    start_date: date = st.session_state.start_date
    end_date: date   = st.session_state.end_date

    # 단조 증가 카운터 초기화
    st.session_state["_loading_max_pct"] = 0

    placeholder = st.empty()
    _render_loading(placeholder, *_LOADING_STAGES[0][:3], _LOADING_STAGES[0][3], stage_idx=0)
    time.sleep(0.6)
    _render_loading(placeholder, *_LOADING_STAGES[1][:3], _LOADING_STAGES[1][3], stage_idx=1)

    all_records = []
    errors: list[str] = []

    # Fix 6: 앱별 플랫폼에 맞는 스크래퍼 사용
    for app_info in apps:
        if not app_info.app_id:
            errors.append(
                f"[{app_info.app_name}] 앱 ID를 확인할 수 없어요. "
                "검색 결과에서 앱을 다시 선택해주세요."
            )
            continue

        # app_info.platform 으로 scraper key 결정
        platform_key = _PLATFORM_KEY_MAP.get(app_info.platform)
        if not platform_key:
            errors.append(f"[{app_info.app_name}] 지원하지 않는 플랫폼: {app_info.platform}")
            continue

        platform_meta = PLATFORMS.get(app_info.platform, {})
        if not platform_meta.get("supported", False):
            note = platform_meta.get("note") or "현재 버전에서는 해당 플랫폼 조회가 제한될 수 있어요."
            errors.append(f"[{app_info.platform} / {app_info.app_name}] {note}")
            continue

        try:
            scraper = get_scraper(platform_key)
        except ValueError as e:
            errors.append(f"[{app_info.platform}] 스크래퍼 로드 실패: {e}")
            continue

        try:
            def _progress(current: int, total: int, _app=app_info, _plat=app_info.platform):
                pct = min(80, 20 + int(current / max(total, 1) * 60))
                _render_loading(
                    placeholder,
                    _LOADING_STAGES[2][0], _LOADING_STAGES[2][1],
                    f"[{_plat}] {_app.app_name}: {current:,}개 수집 중...", pct,
                    stage_idx=2,
                )

            records = scraper.fetch_reviews(
                app_id=app_info.app_id,
                app_name=app_info.app_name,
                start_date=start_date,
                end_date=end_date,
                max_count=DEFAULT_REVIEW_COUNT,
                progress_callback=_progress,
            )
            all_records.extend(records)
            if records:
                _save_raw(pd.DataFrame([asdict(r) for r in records]), platform_key, app_info.app_id)

        except Exception as e:
            errors.append(f"[{app_info.platform} / {app_info.app_name}] 리뷰를 가져오는 중 문제가 발생했어요: {e}")

    if not all_records:
        placeholder.empty()
        st.session_state.pop("analysis_running", None)
        for err in errors:
            st.error(err)
        if not errors:
            st.error("수집된 리뷰가 없습니다. 기간을 조정하거나 다른 앱을 선택해주세요.")
        return

    _render_loading(placeholder, *_LOADING_STAGES[3][:3], _LOADING_STAGES[3][3], stage_idx=3)
    raw_df = pd.DataFrame([asdict(r) for r in all_records])
    st.session_state.raw_df = raw_df

    _render_loading(placeholder, *_LOADING_STAGES[4][:3], _LOADING_STAGES[4][3], stage_idx=4)

    def _pipeline_cb(step: int, total: int, msg: str):
        pct = 90 + int(step / total * 9)
        _render_loading(placeholder, _LOADING_STAGES[5][0], _LOADING_STAGES[5][1], msg, pct, stage_idx=5)

    pipeline_errors: list[str] = []
    try:
        result = run_pipeline(raw_df, progress_callback=_pipeline_cb)
        pipeline_errors = result.get("errors", [])
    except Exception as e:
        pipeline_errors.append(f"분석 파이프라인 오류: {e}")
        result = {}

    _render_loading(placeholder, *_LOADING_STAGES[6][:3], _LOADING_STAGES[6][3], stage_idx=6)
    try:
        vr = run_all_validations(
            raw_df=raw_df,
            processed_df=result.get("processed_df", pd.DataFrame()),
            combined_or=result.get("combined_or", pd.DataFrame()),
        )
        st.session_state.validation_result = vr
    except Exception as e:
        st.session_state.validation_result = {}
        pipeline_errors.append(f"통계 검증 계산 오류: {e}")

    placeholder.empty()
    for err in errors + pipeline_errors:
        st.warning(err)

    st.session_state.pop("analysis_running", None)
    if result:
        st.session_state.pipeline_result = result
        st.session_state.errors = errors + pipeline_errors
        st.session_state.analysis_done = True
        st.session_state.page = "result"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# 입력 페이지
# ─────────────────────────────────────────────────────────────────────────────

def _page_input():
    apps = st.session_state.selected_apps

    if st.session_state.pop("_alert_no_app", False):
        _show_browser_alert("분석할 앱을 1개 이상 선택해주세요")

    if st.session_state.pop("_alert_no_analysis", False):
        _show_browser_alert("먼저, 분석할 앱을 추가해주세요")

    # Fix 7: 입력 페이지 hash
    components.html("<script>window.parent.location.hash='section-search';</script>", height=0)

    render_controls_bar()

    selected_platforms = st.session_state.get("selected_platforms", ["Google Play Store"])
    render_app_search(selected_platforms)

    if st.button("앱 리뷰 분석 시작하기", type="primary", key="analyze_start_btn"):
        if not apps:
            st.session_state["_alert_no_app"] = True
            st.rerun()
        else:
            st.session_state["analysis_running"] = True
            st.rerun()

    _inject_float_btn_js()


# ─────────────────────────────────────────────────────────────────────────────
# 결과 페이지
# ─────────────────────────────────────────────────────────────────────────────

def _page_result():
    result = st.session_state.get("pipeline_result", {})
    raw_df: pd.DataFrame = st.session_state.get("raw_df", pd.DataFrame())

    if st.session_state.pop("_alert_no_analysis", False):
        _show_browser_alert("먼저, 분석할 앱을 추가해주세요")

    # Fix 7: 결과 페이지 hash
    components.html("<script>window.parent.location.hash='section-result';</script>", height=0)

    if raw_df.empty:
        st.warning("분석 결과가 없습니다. 앱을 검색하고 분석을 실행해주세요.")
        return

    processed_df = result.get("processed_df", raw_df)
    or_results   = result.get("or_results", {})
    combined_or  = result.get("combined_or", pd.DataFrame())
    vr           = st.session_state.get("validation_result", {})
    start_date   = st.session_state.get("start_date")
    end_date     = st.session_state.get("end_date")

    n_selected = len(st.session_state.get("selected_apps", []))
    n_apps = raw_df["app_name"].nunique() if not raw_df.empty else 0
    is_compare = (n_selected >= 2) or (n_apps >= 2)

    # 분석 기간 표시
    if start_date and end_date:
        days = (end_date - start_date).days
        st.markdown(
            f'<div style="font-size:0.82rem;color:var(--text-sub);margin-bottom:6px;">'
            f'분석 기간: <b>{start_date.strftime("%y.%m.%d")} ~ {end_date.strftime("%y.%m.%d")}</b>'
            f' ({days}일)</div>',
            unsafe_allow_html=True,
        )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("수집된 리뷰", f"{len(raw_df):,}건")
    k2.metric("분석 앱 수", f"{n_apps}개")
    k3.metric("평균 평점", f"{raw_df['score'].mean():.2f} ⭐" if "score" in raw_df.columns else "-")
    k4.metric("OR 분석 앱", f"{len(or_results)}개")

    st.divider()

    # 사이드바 탭 클릭 시 해당 탭으로 자동 이동
    active_tab = st.session_state.pop("_active_tab", 0)

    view_label = "📊 분석 Summary"
    view_tab, review_tab, kw_tab, or_tab, valid_tab = st.tabs([
        view_label, "📋 리뷰 상세 분석", "☁️ 키워드 탐색", "📈 오즈비 분석", "🔬 통계 검증",
    ])

    if active_tab > 0:
        components.html(f"""
        <script>
        setTimeout(function() {{
            var doc = window.parent.document;
            var tabs = doc.querySelectorAll('[data-testid="stTab"] button, .stTabs [role="tab"]');
            if (!tabs.length) tabs = doc.querySelectorAll('button[data-baseweb="tab"]');
            if (tabs.length > {active_tab}) tabs[{active_tab}].click();
        }}, 300);
        </script>
        """, height=0)

    with view_tab:
        if is_compare:
            compare_view.render(raw_df, processed_df, or_results, combined_or)
        else:
            single_view.render(raw_df, processed_df, or_results, combined_or)

    with review_tab:
        tab_review.render(raw_df, start_date=start_date, end_date=end_date)

    with kw_tab:
        tab_keyword.render(processed_df)

    with or_tab:
        tab_odds.render(combined_or, or_results)

    with valid_tab:
        tab_validation.render(vr, combined_or)


# ─────────────────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────────────────

def main():
    _render_sidebar()

    # 분석 실행 중: 입력 페이지 렌더링 없이 로딩 화면만 표시
    if st.session_state.get("analysis_running"):
        run_analysis()
        return

    _render_header_chips()

    if st.session_state.page == "result" and st.session_state.analysis_done:
        _page_result()
    else:
        _page_input()


if __name__ == "__main__":
    main()
