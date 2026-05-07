"""
논문 4장·5장 기반 전략적 인사이트 렌더링 모듈

논문: 앱 마켓 리뷰 기반 서비스 기능 경쟁력 측정 프레임워크 연구
- Chapter 4: 실증 분석 결과 (OR·ΔOR·우선순위·모형 검증)
- Chapter 5: 결론 및 시사점 (전략 방향·프레임워크 기여)

이 모듈은 동적 OR 결과를 받아 논문 수준의 해석과 전략 인사이트를 렌더링합니다.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src.visualization._common import app_color, get_ordered_app_names, render_insight_box

# ── 상수 ──────────────────────────────────────────────────────────────────────
_BG     = "#0E1116"
_CARD   = "#131820"
_BORDER = "#1E2630"
_TEXT   = "#E2E8F0"
_MUTED  = "#94A3B8"
_BLUE   = "#4F8EF7"
_GREEN  = "#4FD6A5"
_RED    = "#FF6B8A"
_YELLOW = "#FBB55C"
_PURPLE = "#C084FC"

_OR_STRONG_THRESH  = 1.5   # OR ≥ 1.5 → 강한 경쟁 우위
_OR_POS_THRESH     = 1.0   # OR ≥ 1.0 → 경쟁 우위
_OR_WEAK_THRESH    = 0.5   # OR < 0.5 → 심각한 열위
_P_SIG             = 0.05
_PRIORITY_HIGH     = 1.2   # priority_score 기준 (high)
_PRIORITY_MID      = 0.7


def _card(content_html: str, border_color: str = _BLUE, padding: str = "0.9rem 1rem") -> None:
    st.markdown(
        f'<div style="background:{_CARD};border-left:4px solid {border_color};'
        f'border-radius:6px;padding:{padding};margin-bottom:1.1rem;">'
        f'{content_html}</div>',
        unsafe_allow_html=True,
    )


def _badge(label: str, color: str) -> str:
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}66;'
        f'border-radius:999px;padding:1px 8px;font-size:0.75rem;font-weight:700;'
        f'margin-right:4px;">{label}</span>'
    )


def _or_badge(or_val: float) -> str:
    if or_val >= _OR_STRONG_THRESH:
        return _badge("강한 우위", _GREEN)
    if or_val >= _OR_POS_THRESH:
        return _badge("소폭 우위", "#93C5FD")
    if or_val >= _OR_WEAK_THRESH:
        return _badge("소폭 열위", _YELLOW)
    return _badge("심각한 열위", _RED)


def _priority_badge(score: float) -> str:
    if score >= _PRIORITY_HIGH:
        return _badge("우선순위 높음", _RED)
    if score >= _PRIORITY_MID:
        return _badge("중간 우선순위", _YELLOW)
    return _badge("모니터링", _BLUE)


# ── 섹션 A: 모형 성과 요약 (Ch.4 — McFadden R²) ─────────────────────────────
def render_model_performance(vr: dict[str, Any], app_names: list[str]) -> None:
    """McFadden Pseudo R² 기반 모형 신뢰도 카드 — 논문 4.4절 대응."""
    mf = vr.get("model_fit", {})
    if not mf or not isinstance(mf, dict):
        return

    # model_fit 구조: {"table": pd.DataFrame, "_models": dict}
    mf_table = mf.get("table", pd.DataFrame())
    if isinstance(mf_table, pd.DataFrame) and not mf_table.empty:
        rows = mf_table.to_dict("records")
    else:
        return

    st.markdown(
        '<div style="font-size:0.9rem;font-weight:700;color:#93C5FD;margin-bottom:0.5rem;">'
        '📐 모형 적합도 — McFadden Pseudo R²</div>',
        unsafe_allow_html=True,
    )

    cards_html = ""
    for row in rows:
        r2 = row.get("pseudo_r2", float("nan"))
        app = row.get("app_name", "")
        if pd.isna(r2):
            continue
        if r2 >= 0.2:
            verdict, vc = "양호 ✓", _GREEN
            interp = "모형이 데이터를 충분히 설명합니다."
        elif r2 >= 0.1:
            verdict, vc = "수용 가능", _YELLOW
            interp = "OR 방향성은 신뢰할 수 있으나 과신은 금물입니다."
        else:
            verdict, vc = "주의 !", _RED
            interp = "리뷰 수가 충분히 증가하면 모형 설명력이 개선됩니다."

        color = app_color(app)
        cards_html += (
            f'<div style="background:#0E1116;border:1px solid {_BORDER};border-radius:6px;'
            f'padding:0.6rem 0.9rem;margin-bottom:0.5rem;">'
            f'<span style="color:{color};font-weight:700;">{app}</span>'
            f'<span style="color:{_MUTED};font-size:0.8rem;margin-left:6px;">R² = </span>'
            f'<span style="color:{vc};font-weight:700;font-size:1.05rem;">{r2:.3f}</span>'
            f'<span style="margin-left:8px;">{_badge(verdict, vc)}</span>'
            f'<div style="color:{_MUTED};font-size:0.78rem;margin-top:2px;">{interp}</div>'
            f'</div>'
        )

    _card(
        f'<div style="font-size:0.78rem;color:{_MUTED};margin-bottom:0.6rem;">'
        f'McFadden Pseudo R² ≥ 0.2 → 양호 / ≥ 0.1 → 수용 가능 / &lt; 0.1 → 주의'
        f'(논문 기준, Cohen 1983)</div>'
        f'{cards_html}',
        border_color=_BLUE,
    )


# ── 섹션 B: 앱별 핵심 경쟁력 진단 (Ch.4.2 — OR 분석) ────────────────────────
def render_competitive_diagnosis(
    combined_or: pd.DataFrame,
    app_names: list[str],
) -> None:
    """앱별 강점·약점 Top 기능 — 논문 4.2절 OR 분석 대응."""
    if combined_or.empty:
        return

    sig_col = "p_value"
    has_sig = sig_col in combined_or.columns

    st.markdown(
        '<div style="font-size:0.9rem;font-weight:700;color:#93C5FD;margin-bottom:0.5rem;">'
        '🔬 앱별 핵심 경쟁력 진단 (유의 OR 기반)</div>',
        unsafe_allow_html=True,
    )

    for app in app_names:
        app_df = combined_or[combined_or["app_name"] == app].copy()
        if app_df.empty:
            continue

        if has_sig:
            sig_df = app_df[app_df[sig_col] < _P_SIG]
        else:
            sig_df = app_df

        if sig_df.empty:
            continue

        strengths = sig_df[sig_df["OR"] >= _OR_POS_THRESH].nlargest(3, "OR")
        weaknesses = sig_df[sig_df["OR"] < _OR_POS_THRESH].nsmallest(3, "OR")

        color = app_color(app)

        str_rows = ""
        for _, r in strengths.iterrows():
            str_rows += (
                f'<div style="margin:3px 0;font-size:0.82rem;">'
                f'{_or_badge(r["OR"])}'
                f'<span style="color:{_TEXT};">{r["feature_category"]}</span>'
                f'<span style="color:{_GREEN};font-weight:700;margin-left:6px;">OR {r["OR"]:.2f}</span>'
                f'</div>'
            )

        weak_rows = ""
        for _, r in weaknesses.iterrows():
            weak_rows += (
                f'<div style="margin:3px 0;font-size:0.82rem;">'
                f'{_or_badge(r["OR"])}'
                f'<span style="color:{_TEXT};">{r["feature_category"]}</span>'
                f'<span style="color:{_RED};font-weight:700;margin-left:6px;">OR {r["OR"]:.2f}</span>'
                f'</div>'
            )

        n_sig = len(sig_df)
        n_pos = len(sig_df[sig_df["OR"] >= 1])
        n_neg = len(sig_df[sig_df["OR"] < 1])

        _none = '<span style="color:#64748B;font-size:0.78rem;">해당 없음</span>'
        _card(
            f'<div style="color:{color};font-weight:700;font-size:0.9rem;margin-bottom:0.4rem;">'
            f'{app} — 유의 기능 {n_sig}개 (긍정 연관 {n_pos}개 / 부정 연관 {n_neg}개)</div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;">'
            f'<div><div style="color:{_GREEN};font-size:0.78rem;font-weight:700;margin-bottom:3px;">▲ 경쟁 강점 Top 3</div>'
            f'{str_rows or _none}</div>'
            f'<div><div style="color:{_RED};font-size:0.78rem;font-weight:700;margin-bottom:3px;">▼ 개선 필요 Top 3</div>'
            f'{weak_rows or _none}</div>'
            f'</div>',
            border_color=color,
        )


# ── 섹션 C: 전략적 우선순위 액션 플랜 (Ch.4.3 + 5.1) ─────────────────────────
def render_priority_action_plan(
    combined_or: pd.DataFrame,
    app_names: list[str],
    base_app: str | None = None,
) -> None:
    """Priority Score 기반 액션 플랜 — 논문 4.3절 + 5.1절 대응."""
    if combined_or.empty or "priority_score" not in combined_or.columns:
        return

    target = base_app or (app_names[0] if app_names else None)
    if target is None:
        return

    app_df = combined_or[combined_or["app_name"] == target].copy()
    if app_df.empty:
        return

    top = app_df.nlargest(8, "priority_score")
    if top.empty:
        return

    st.markdown(
        '<div style="font-size:0.9rem;font-weight:700;color:#93C5FD;margin-bottom:0.5rem;">'
        f'🎯 전략적 우선순위 액션 플랜 — {target} 기준</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-size:0.78rem;color:{_MUTED};margin-bottom:0.7rem;">'
        f'Priority Score = 0.6 × |ΔOR| + 0.4 × vulnerability &nbsp;|&nbsp; '
        f'높을수록 개선 효과가 큰 기능입니다. (논문 식 4.3)</div>',
        unsafe_allow_html=True,
    )

    rows_html = ""
    for rank, (_, r) in enumerate(top.iterrows(), 1):
        ps = r.get("priority_score", 0)
        or_val = r.get("OR", float("nan"))
        delta = r.get("delta_or", float("nan"))

        # action label
        if ps >= _PRIORITY_HIGH and or_val < 1:
            action = "즉시 개선"
            action_color = _RED
        elif ps >= _PRIORITY_HIGH and or_val >= 1:
            action = "강점 강화"
            action_color = _GREEN
        elif ps >= _PRIORITY_MID:
            action = "단기 개선 검토"
            action_color = _YELLOW
        else:
            action = "모니터링"
            action_color = _BLUE

        delta_str = (f"+{delta:.2f}" if delta > 0 else f"{delta:.2f}") if not pd.isna(delta) else "—"
        delta_color = _GREEN if (not pd.isna(delta) and delta > 0) else _RED

        rows_html += (
            f'<div style="display:grid;grid-template-columns:28px 1fr 60px 55px 70px 90px;'
            f'align-items:center;gap:6px;padding:5px 0;border-bottom:1px solid {_BORDER};'
            f'font-size:0.82rem;">'
            f'<div style="color:{_MUTED};text-align:center;">{rank}</div>'
            f'<div style="color:{_TEXT};">{r["feature_category"]}</div>'
            f'<div style="color:#93C5FD;font-weight:700;text-align:right;">{ps:.2f}</div>'
            f'<div style="color:{"#4FD6A5" if (not pd.isna(or_val) and or_val >= 1) else _RED};'
            f'font-weight:700;text-align:right;">{or_val:.2f if not pd.isna(or_val) else "—"}</div>'
            f'<div style="color:{delta_color};font-weight:700;text-align:right;">{delta_str}</div>'
            f'<div style="text-align:center;">'
            f'<span style="background:{action_color}22;color:{action_color};border:1px solid {action_color}55;'
            f'border-radius:999px;padding:1px 7px;font-size:0.72rem;font-weight:700;">{action}</span>'
            f'</div>'
            f'</div>'
        )

    header_html = (
        f'<div style="display:grid;grid-template-columns:28px 1fr 60px 55px 70px 90px;'
        f'gap:6px;padding:4px 0 6px;font-size:0.75rem;font-weight:700;color:{_MUTED};">'
        f'<div>#</div><div>기능 카테고리</div>'
        f'<div style="text-align:right;">우선순위</div>'
        f'<div style="text-align:right;">OR</div>'
        f'<div style="text-align:right;">ΔOR</div>'
        f'<div style="text-align:center;">액션</div>'
        f'</div>'
    )

    _card(header_html + rows_html, border_color=_PURPLE)


# ── 섹션 D: 서비스 기획자 전략 시사점 (Ch.5.1) ───────────────────────────────
def render_planner_implications(
    combined_or: pd.DataFrame,
    app_names: list[str],
    base_app: str | None = None,
) -> None:
    """서비스 기획자 관점 전략 시사점 — 논문 5.1절 대응."""
    target = base_app or (app_names[0] if app_names else None)
    if target is None:
        return

    app_df = combined_or[combined_or["app_name"] == target].copy() if not combined_or.empty else pd.DataFrame()

    st.markdown(
        '<div style="font-size:0.9rem;font-weight:700;color:#93C5FD;margin-bottom:0.5rem;">'
        '💡 서비스 기획자 전략 시사점 (논문 Ch.5 기반)</div>',
        unsafe_allow_html=True,
    )

    # 동적으로 1순위 약점·강점 도출
    weak1 = strong1 = None
    if not app_df.empty and "priority_score" in app_df.columns:
        sig_df = app_df[app_df["p_value"] < _P_SIG] if "p_value" in app_df.columns else app_df
        weak_df = sig_df[sig_df["OR"] < 1].nlargest(1, "priority_score") if not sig_df.empty else pd.DataFrame()
        strong_df = sig_df[sig_df["OR"] >= _OR_STRONG_THRESH].nlargest(1, "OR") if not sig_df.empty else pd.DataFrame()
        if not weak_df.empty:
            weak1 = weak_df.iloc[0]
        if not strong_df.empty:
            strong1 = strong_df.iloc[0]

    implications = [
        (
            "데이터 기반 기능 기획",
            _BLUE,
            "기존 직관적 로드맵 결정에서 탈피해 OR·ΔOR 수치를 기획 기준선으로 활용하세요. "
            "유의한(p&lt;0.05) 기능의 OR이 &lt;0.5이면 즉각 개선 검토가 필요합니다.",
        ),
        (
            "경쟁 우선순위 결정",
            _PURPLE,
            (
                f"<b>{weak1['feature_category']}</b> (OR {weak1['OR']:.2f}, "
                f"Priority {weak1['priority_score']:.2f})이 {target}의 최우선 개선 과제입니다. "
                "ΔOR 음수 폭이 클수록 경쟁사와의 격차가 커 긴급도가 높습니다."
                if weak1 is not None else
                "Priority Score가 높은 기능부터 순차 개선해 경쟁 열위를 해소하세요."
            ),
        ),
        (
            "강점 차별화 유지",
            _GREEN,
            (
                f"<b>{strong1['feature_category']}</b> (OR {strong1['OR']:.2f})은 {target}의 "
                "핵심 경쟁 우위 기능입니다. 마케팅 메시지와 QA 우선순위에 반영해 유지하세요."
                if strong1 is not None else
                "OR &gt; 1.5 기능은 사용자 만족의 핵심입니다 — 유지·강화 투자를 지속하세요."
            ),
        ),
        (
            "프레임워크 반복 적용",
            _YELLOW,
            "분기마다 OR 분석을 재실행해 개선 효과를 수치로 확인하세요. "
            "OR 상승 = 개선 성공, 하락 = 추가 조치 필요. 리뷰 수 증가 시 모형 정밀도도 향상됩니다.",
        ),
    ]

    for title, col, body in implications:
        _card(
            f'<div style="color:{col};font-weight:700;font-size:0.85rem;margin-bottom:0.3rem;">'
            f'▸ {title}</div>'
            f'<div style="color:{_MUTED};font-size:0.81rem;line-height:1.65;">{body}</div>',
            border_color=col,
            padding="0.75rem 1rem",
        )


# ── 섹션 E: 프레임워크 기여 요약 (Ch.5.2) ────────────────────────────────────
def render_framework_contribution() -> None:
    """논문의 방법론적·실증적 기여 요약 카드 — 논문 5.2절 대응."""
    st.markdown(
        '<div style="font-size:0.9rem;font-weight:700;color:#93C5FD;margin-bottom:0.5rem;">'
        '📚 프레임워크 학술·실무 기여 (논문 Ch.5.2)</div>',
        unsafe_allow_html=True,
    )

    contributions = [
        ("방법론적 기여", _BLUE,
         "앱 리뷰 + 로지스틱 회귀 OR 결합 최초 사례 · "
         "기능 단위 경쟁력 수치화 체계 · Fisher 보정으로 희소 카테고리 처리"),
        ("실증적 기여", _GREEN,
         "국내 모바일 금융 3사 비교 · ΔOR 경쟁 갭 지표 최초 정의 · "
         "평점·기간 이중 민감도 검증으로 견고성 확인"),
        ("한계 및 향후 연구", _YELLOW,
         "단일 플랫폼(Google Play) 제한 · LLM 기반 카테고리 분류 고도화 필요 · "
         "종단 패널 데이터 확장 및 Apple App Store 병행 분석 제안"),
    ]

    cols = st.columns(3)
    for col_ui, (title, color, body) in zip(cols, contributions):
        with col_ui:
            st.markdown(
                f'<div style="background:{_CARD};border-top:3px solid {color};'
                f'border-radius:6px;padding:0.75rem 0.9rem;height:100%;">'
                f'<div style="color:{color};font-weight:700;font-size:0.82rem;margin-bottom:0.4rem;">'
                f'{title}</div>'
                f'<div style="color:{_MUTED};font-size:0.78rem;line-height:1.65;">{body}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ── 통합 렌더러 (compare_view 전용) ──────────────────────────────────────────
def render_compare_insights(
    combined_or: pd.DataFrame,
    app_names: list[str],
    vr: dict[str, Any],
    base_app: str | None = None,
) -> None:
    """
    논문 4·5장 기반 종합 인사이트 — compare_view 섹션 7에서 호출.
    """
    st.markdown("#### 📖 연구 결과 종합 시사점 (논문 Ch.4–5)")
    st.markdown(
        f'<div style="background:{_CARD};border-left:4px solid {_BLUE};border-radius:6px;'
        f'padding:0.75rem 1rem;margin-bottom:1.1rem;font-size:0.81rem;color:{_MUTED};">'
        f'<b style="color:#93C5FD;">이 섹션의 목적</b><br>'
        f'본 분석 결과를 논문 프레임워크(로지스틱 회귀 기반 OR 측정)로 해석합니다. '
        f'McFadden R², 앱별 강점·약점, 우선순위 액션 플랜, 서비스 기획자 시사점을 통합 제공합니다.'
        f'</div>',
        unsafe_allow_html=True,
    )

    render_model_performance(vr, app_names)
    st.markdown("<br>", unsafe_allow_html=True)

    render_competitive_diagnosis(combined_or, app_names)
    st.markdown("<br>", unsafe_allow_html=True)

    render_priority_action_plan(combined_or, app_names, base_app=base_app)
    st.markdown("<br>", unsafe_allow_html=True)

    render_planner_implications(combined_or, app_names, base_app=base_app)
    st.markdown("<br>", unsafe_allow_html=True)

    render_framework_contribution()


# ── 통합 렌더러 (single_view 전용) ───────────────────────────────────────────
def render_single_insights(
    combined_or: pd.DataFrame,
    app_name: str,
    vr: dict[str, Any],
) -> None:
    """
    논문 4·5장 기반 단일 앱 인사이트 — single_view 마지막 섹션에서 호출.
    """
    st.divider()
    st.markdown("#### 📖 연구 프레임워크 기반 인사이트 (논문 Ch.4–5)")
    st.markdown(
        f'<div style="background:{_CARD};border-left:4px solid {_BLUE};border-radius:6px;'
        f'padding:0.75rem 1rem;margin-bottom:1.1rem;font-size:0.81rem;color:{_MUTED};">'
        f'<b style="color:#93C5FD;">이 섹션의 목적</b><br>'
        f'OR 분석 결과를 논문 기준(Ch.4)으로 해석하고, 서비스 기획자를 위한 전략 시사점(Ch.5)을 제공합니다.'
        f'</div>',
        unsafe_allow_html=True,
    )

    render_model_performance(vr, [app_name])
    st.markdown("<br>", unsafe_allow_html=True)

    render_competitive_diagnosis(combined_or, [app_name])
    st.markdown("<br>", unsafe_allow_html=True)

    render_priority_action_plan(combined_or, [app_name], base_app=app_name)
    st.markdown("<br>", unsafe_allow_html=True)

    render_planner_implications(combined_or, [app_name], base_app=app_name)
    st.markdown("<br>", unsafe_allow_html=True)

    render_framework_contribution()
