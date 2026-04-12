"""
Tab 4: Feature Priority Matrix

- x축: ΔOR (경쟁 우위/열위)
- y축: 전략 우선도 점수
- 사분면 레이블
- Hover: 기능명, OR, ΔOR, 전략 우선도 점수
"""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analysis.delta_or import get_priority_matrix_df
from src.visualization._common import (
    TEXT as _TEXT, SUBTEXT as _SUBTEXT,
    apply_dark_theme, centered_title,
    render_insight_box, render_skeleton,
)

# 다크 배경용 사분면 색상 (반투명)
# X축 기준: 양수 = 기준앱 경쟁 우위, 음수 = 기준앱 경쟁 열위
_QUADRANT_LABELS = {
    "Q1": ("경쟁 열위 & 개선 시급",  "rgba(185,28,28,0.18)",    "#FF8A9A"),   # 좌상
    "Q2": ("경쟁 우위 유지 영역",    "rgba(6,95,70,0.18)",      "#4FD6A5"),   # 우상
    "Q3": ("산업 공통 문제",          "rgba(146,64,14,0.12)",    "#FBB55C"),   # 좌하
    "Q4": ("현상 유지 영역",          "rgba(30,64,175,0.12)",    "#7BA7F5"),   # 우하
}

_AREA_ORDER = {
    "경쟁 열위 · 개선 시급": 0,
    "산업 공통 문제":        1,
    "경쟁 우위 유지":        2,
    "현상 유지":             3,
}

_AREA_STYLE = {
    "경쟁 열위 · 개선 시급": ("#FF8A9A", "rgba(185,28,28,0.35)"),
    "경쟁 우위 유지":        ("#4FD6A5", "rgba(6,95,70,0.35)"),
    "산업 공통 문제":        ("#FBB55C", "rgba(146,64,14,0.32)"),
    "현상 유지":             ("#7BA7F5", "rgba(30,64,175,0.30)"),
}

_SYMLOG_C = 0.3   # 작을수록 0 근처 분해능 ↑, 이상치 압축 ↑
_Y_CLIP   = 1.5   # y축 최대 표시 점수 — 초과 포인트는 경계에 화살표로 표시


def _symlog(x: float) -> float:
    """sign(x) * log(1 + |x|/c) — 중앙 분해능 확대, 이상치 압축."""
    return math.copysign(math.log1p(abs(x) / _SYMLOG_C), x) if x != 0 else 0.0


def _quadrant_marker_color(x_val: float, y_val: float, y_mid: float) -> str:
    if x_val >= 0 and y_val >= y_mid:  return _QUADRANT_LABELS["Q2"][2]
    if x_val < 0  and y_val >= y_mid:  return _QUADRANT_LABELS["Q1"][2]
    if x_val < 0  and y_val < y_mid:   return _QUADRANT_LABELS["Q3"][2]
    return _QUADRANT_LABELS["Q4"][2]


def _smart_text_pos(df: pd.DataFrame, x_col: str, y_col: str) -> dict[str, str]:
    """인접 포인트를 고려한 라벨 위치 결정 — 겹침 최소화."""
    if df.empty:
        return {}

    positions: dict[str, str] = {}
    cats = df["feature_category"].tolist()
    xs   = df[x_col].tolist()
    ys   = df[y_col].tolist()
    n    = len(df)

    x_span = max(xs) - min(xs) if n > 1 else 1.0
    y_span = max(ys) - min(ys) if n > 1 else 1.0
    xt = max(x_span * 0.08, 0.15)
    yt = max(y_span * 0.12, 0.05)

    for i, cat in enumerate(cats):
        xi, yi = xs[i], ys[i]
        n_above = sum(
            1 for j in range(n)
            if j != i and abs(xs[j] - xi) <= xt and 0 < ys[j] - yi <= yt * 4
        )
        n_right = sum(
            1 for j in range(n)
            if j != i and xs[j] > xi and abs(xs[j] - xi) <= xt * 2 and abs(ys[j] - yi) <= yt
        )

        if n_above > 0 and n_right > 0:
            positions[cat] = "bottom left"
        elif n_above > 0:
            positions[cat] = "bottom center"
        elif n_right > 0:
            positions[cat] = "top left"
        else:
            positions[cat] = "top center"

    return positions


def _build_scatter(
    matrix_df: pd.DataFrame,
    app_or_data: pd.DataFrame,
    base_app: str | None = None,
) -> go.Figure:
    """메인 산점도 — symlog x축, x/y 이중 클리핑, 방향별 화살표 마커."""
    fig = go.Figure()

    y_mid = matrix_df["priority_score_max"].median() if not matrix_df.empty else 0.5

    df = matrix_df.copy()
    df["_x_plot"] = df["delta_or_mean"].apply(_symlog)

    # ── X축 클리핑: 90th pct, min 1.5 raw ────────────────────────────────────
    raw_abs  = df["delta_or_mean"].abs()
    clip_raw = float(max(raw_abs.quantile(0.90), 1.5))
    clip_sym = _symlog(clip_raw)

    df["_x_display"] = df["_x_plot"].clip(-clip_sym, clip_sym)
    df["_xr_clamp"]  = df["_x_plot"] > clip_sym + 1e-9    # 우측 초과
    df["_xl_clamp"]  = df["_x_plot"] < -(clip_sym + 1e-9) # 좌측 초과

    # ── Y축 클리핑: _Y_CLIP 고정 ─────────────────────────────────────────────
    df["_y_display"] = df["priority_score_max"].clip(upper=_Y_CLIP)
    df["_y_clamp"]   = df["priority_score_max"] > _Y_CLIP + 1e-9

    # Symmetric x range, y range 고정
    x_pad   = clip_sym * 0.12
    x_range = [-(clip_sym + x_pad), clip_sym + x_pad]
    y_range = [0, _Y_CLIP * 1.08]

    # Ticks (x 원본 스케일)
    _cands = [-5, -4, -3, -2.5, -2, -1.5, -1, -0.5, -0.25, 0,
              0.25, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5]
    tick_raw  = [t for t in _cands if abs(t) <= clip_raw * 1.05]
    tick_vals = [_symlog(t) for t in tick_raw]
    tick_text = [("0" if t == 0 else f"{t:+g}") for t in tick_raw]

    # Smart text positions (클리핑된 표시 좌표 기준)
    _pos_input = df[["feature_category"]].copy()
    _pos_input["_xd"] = df["_x_display"]
    _pos_input["_yd"] = df["_y_display"]
    _pos_input = _pos_input.rename(columns={"_xd": "_x_display", "_yd": "priority_score_max"})
    text_positions = _smart_text_pos(_pos_input, "_x_display", "priority_score_max")

    # Quadrant backgrounds
    x_mid = 0.0
    quadrants = [
        (x_range[0], x_mid, y_mid, y_range[1], "Q1"),
        (x_mid,  x_range[1], y_mid, y_range[1], "Q2"),
        (x_range[0], x_mid, y_range[0], y_mid,  "Q3"),
        (x_mid,  x_range[1], y_range[0], y_mid,  "Q4"),
    ]
    for (x0, x1, y0, y1, q) in quadrants:
        label, fillcolor, font_color = _QUADRANT_LABELS[q]
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=fillcolor, opacity=1.0, layer="below", line_width=0)
        # 라벨 y는 표시 범위 내 클리핑
        ann_y = min(y0 + (y1 - y0) * 0.94, y_range[1] * 0.97)
        fig.add_annotation(
            x=(x0 + x1) / 2, y=ann_y,
            text=f"<b>{label}</b>",
            showarrow=False, font=dict(size=12, color=font_color), xanchor="center",
        )

    base_label = f"{base_app} 기준" if base_app else "기준선"
    fig.add_vline(x=0, line_dash="dash", line_color=_SUBTEXT, line_width=1,
                  annotation_text=base_label, annotation_position="top right",
                  annotation_font_color=_SUBTEXT, annotation_font_size=10)
    fig.add_hline(y=y_mid, line_dash="dash", line_color=_SUBTEXT, line_width=1,
                  annotation_text="전략 우선도 중간값", annotation_position="right",
                  annotation_font_color=_SUBTEXT, annotation_font_size=10)

    # X 클리핑 경계선
    if (df["_xr_clamp"] | df["_xl_clamp"]).any():
        for sign in (+1, -1):
            fig.add_vline(x=sign * clip_sym,
                          line_dash="dot", line_color="rgba(148,163,184,0.22)", line_width=1)
    # Y 클리핑 경계선
    if df["_y_clamp"].any():
        fig.add_hline(y=_Y_CLIP,
                      line_dash="dot", line_color="rgba(148,163,184,0.22)", line_width=1,
                      annotation_text=f"표시 한계 ({_Y_CLIP}점)", annotation_position="left",
                      annotation_font_color="rgba(148,163,184,0.5)", annotation_font_size=9)

    for _, row in df.iterrows():
        cat      = row["feature_category"]
        x_raw    = row["delta_or_mean"]
        x_disp   = row["_x_display"]
        y_val    = row["priority_score_max"]   # 실제 값 (hover용)
        y_disp   = row["_y_display"]           # 표시 좌표
        or_val   = row["or_mean"]
        xr_c     = bool(row["_xr_clamp"])
        xl_c     = bool(row["_xl_clamp"])
        yc       = bool(row["_y_clamp"])
        any_c    = xr_c or xl_c or yc

        marker_color = _quadrant_marker_color(x_raw, y_val, y_mid)

        or_detail = ""
        if not app_or_data.empty:
            sub = app_or_data[app_or_data["feature_category"] == cat]
            for _, r2 in sub.iterrows():
                or_detail += f"  {r2['app_name']}: OR={r2['OR']:.3f}<br>"

        delta_label = (
            f"ΔOR ({base_app} 기준): {x_raw:+.3f}"
            if base_app else f"ΔOR: {x_raw:+.3f}"
        )
        pos_label = "→ 경쟁 우위" if x_raw > 0 else "→ 경쟁 열위"
        action = (
            "개선 우선 검토" if (x_raw < 0 and y_val >= y_mid) else
            "강점 유지"     if (x_raw >= 0 and y_val >= y_mid) else
            "모니터링"      if (x_raw < 0 and y_val < y_mid) else
            "현 수준 유지"
        )

        # ── 마커 심볼: 클리핑 방향 조합 ──────────────────────────────────────
        if   yc and xr_c:  symbol = "triangle-ne"
        elif yc and xl_c:  symbol = "triangle-nw"
        elif yc:            symbol = "triangle-up"
        elif xr_c:          symbol = "triangle-right"
        elif xl_c:          symbol = "triangle-left"
        else:               symbol = "circle"

        # 테두리 색: 클리핑 유형 구분
        if yc and (xr_c or xl_c): line_color = "#FB923C"  # 대각 — 주황
        elif yc:                    line_color = "#67E8F9"  # y만  — 시안
        elif xr_c or xl_c:         line_color = "#FFD700"  # x만  — 골드
        else:                       line_color = "white"
        line_width = 2.5 if any_c else 1.5

        # hover 보충 설명
        clamp_parts = []
        if xr_c or xl_c:  clamp_parts.append(f"실제 ΔOR={x_raw:+.3f}")
        if yc:             clamp_parts.append(f"실제 전략 우선도={y_val:.3f}")
        clamp_note = ("<br><i>표시 범위 밖 (" + " / ".join(clamp_parts) + ")</i>") if clamp_parts else ""

        msize = max(10, min(24, y_val * 26 + 9))
        # y 클리핑 포인트는 라벨을 아래에 표시 (경계 위로 튀어나오지 않게)
        tpos = "bottom center" if yc else text_positions.get(cat, "top center")

        fig.add_trace(go.Scatter(
            x=[x_disp], y=[y_disp],
            mode="markers+text",
            text=[cat],
            textposition=tpos,
            textfont=dict(size=8, color=_TEXT),
            marker=dict(
                size=msize, color=marker_color, symbol=symbol,
                opacity=0.88, line=dict(width=line_width, color=line_color),
            ),
            name=cat, showlegend=False,
            hovertemplate=(
                f"<b>{cat}</b><br>"
                f"{delta_label}  {pos_label}<br>"
                f"전략 우선도 점수: {y_val:.3f}<br>"
                f"OR (기준앱): {or_val:.3f}<br>"
                f"권장 액션: <b>{action}</b>"
                f"{clamp_note}<br>{or_detail}"
                "<extra></extra>"
            ),
        ))

    x_axis_title = (
        f"← {base_app} 경쟁 열위 &nbsp;|&nbsp; ΔOR (symlog, c={_SYMLOG_C}) &nbsp;|&nbsp; {base_app} 경쟁 우위 →"
        if base_app else
        f"ΔOR (symlog, c={_SYMLOG_C}) &nbsp;— ← 경쟁 열위 | 경쟁 우위 →"
    )

    chart_height = max(1000, len(df) * 22 + 420)

    fig.update_layout(
        title=centered_title(
            f"기능별 전략 우선도 매트릭스 ({base_app} 기준)" if base_app
            else "기능별 전략 우선도 매트릭스"
        ),
        xaxis_title=x_axis_title,
        yaxis_title="전략 우선도 점수 (개선 시급성 + 강점 유지 중요도)",
        height=chart_height,
        hovermode="closest",
        margin=dict(l=10, r=30, t=80, b=90),
    )
    apply_dark_theme(fig)
    fig.update_xaxes(range=x_range, zeroline=False, tickvals=tick_vals, ticktext=tick_text)
    fig.update_yaxes(range=y_range, zeroline=False)
    return fig


def _build_center_zoom(
    matrix_df: pd.DataFrame,
    app_or_data: pd.DataFrame,
    base_app: str | None = None,
    zoom_limit: float = 1.5,
) -> go.Figure | None:
    """중앙 구간 확대 보조 차트 — 선형 x축, |ΔOR| ≤ zoom_limit 범위만, 전체 라벨 표시."""
    center_df = matrix_df[matrix_df["delta_or_mean"].abs() <= zoom_limit].copy()
    if center_df.empty or len(center_df) < 3:
        return None

    fig   = go.Figure()
    y_mid = matrix_df["priority_score_max"].median()

    _Y_CLIP_ZOOM = 0.9   # 중앙 확대 차트 전용 y축 최대값

    x_range = [-zoom_limit * 1.12, zoom_limit * 1.12]
    y_range = [0, _Y_CLIP_ZOOM * 1.08]

    # Y 클리핑 적용 (중앙 확대 차트는 0.9 기준)
    center_df = center_df.copy()
    center_df["_y_display"] = center_df["priority_score_max"].clip(upper=_Y_CLIP_ZOOM)
    center_df["_y_clamp"]   = center_df["priority_score_max"] > _Y_CLIP_ZOOM + 1e-9

    quadrants = [
        (x_range[0], 0, y_mid, y_range[1], "Q1"),
        (0, x_range[1], y_mid, y_range[1], "Q2"),
        (x_range[0], 0, y_range[0], y_mid, "Q3"),
        (0, x_range[1], y_range[0], y_mid, "Q4"),
    ]
    for (x0, x1, y0, y1, q) in quadrants:
        label, fillcolor, font_color = _QUADRANT_LABELS[q]
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=fillcolor, opacity=1.0, layer="below", line_width=0)
        ann_y = min(y0 + (y1 - y0) * 0.94, y_range[1] * 0.97)
        fig.add_annotation(
            x=(x0 + x1) / 2, y=ann_y,
            text=f"<b>{label}</b>",
            showarrow=False, font=dict(size=10, color=font_color), xanchor="center",
        )

    fig.add_vline(x=0, line_dash="dash", line_color=_SUBTEXT, line_width=1)
    fig.add_hline(y=y_mid, line_dash="dash", line_color=_SUBTEXT, line_width=1)

    if center_df["_y_clamp"].any():
        fig.add_hline(y=_Y_CLIP_ZOOM, line_dash="dot",
                      line_color="rgba(148,163,184,0.22)", line_width=1)

    # 전체 라벨 — 스마트 위치 (클리핑된 좌표 기준)
    _pos2 = center_df[["feature_category"]].copy()
    _pos2["_x"] = center_df["delta_or_mean"]
    _pos2["priority_score_max"] = center_df["_y_display"]
    text_positions = _smart_text_pos(_pos2, "_x", "priority_score_max")

    base_label = f"{base_app} 기준" if base_app else "기준선"
    base_or_label = f"OR ({base_app})" if base_app else "OR (기준앱)"

    for _, row in center_df.iterrows():
        cat    = row["feature_category"]
        x_raw  = row["delta_or_mean"]
        y_val  = row["priority_score_max"]
        y_disp = row["_y_display"]
        yc     = bool(row["_y_clamp"])
        or_val = row["or_mean"]
        marker_color = _quadrant_marker_color(x_raw, y_val, y_mid)
        msize = max(10, min(22, y_val * 24 + 9))
        symbol     = "triangle-up" if yc else "circle"
        line_color = "#67E8F9"    if yc else "white"
        line_width = 2.0          if yc else 1.2
        action = (
            "개선 우선 검토" if (x_raw < 0 and y_val >= y_mid) else
            "강점 유지"     if (x_raw >= 0 and y_val >= y_mid) else
            "모니터링"      if (x_raw < 0 and y_val < y_mid) else
            "현 수준 유지"
        )
        pos_label = "→ 경쟁 우위" if x_raw >= 0 else "→ 경쟁 열위"
        delta_label = f"ΔOR ({base_label}): {x_raw:+.3f}  {pos_label}"
        tpos  = "bottom center" if yc else text_positions.get(cat, "top center")
        clamp_note = f"<br><i>표시 범위 밖 (실제 점수={y_val:.3f})</i>" if yc else ""

        # 앱별 OR 상세 (app_or_data 활용)
        or_detail = ""
        if not app_or_data.empty:
            sub = app_or_data[app_or_data["feature_category"] == cat]
            for _, r2 in sub.iterrows():
                or_detail += f"  {r2['app_name']}: OR={r2['OR']:.3f}<br>"

        fig.add_trace(go.Scatter(
            x=[x_raw], y=[y_disp],
            mode="markers+text",
            text=[cat],
            textposition=tpos,
            textfont=dict(size=8, color=_TEXT),
            marker=dict(size=msize, color=marker_color, symbol=symbol, opacity=0.9,
                        line=dict(width=line_width, color=line_color)),
            name=cat, showlegend=False,
            hovertemplate=(
                f"<b>{cat}</b><br>"
                f"{delta_label}<br>"
                f"전략 우선도 점수: {y_val:.3f}<br>"
                f"{base_or_label}: {or_val:.3f}<br>"
                f"권장 액션: <b>{action}</b>{clamp_note}<br>{or_detail}"
                "<extra></extra>"
            ),
        ))

    zoom_title = (
        f"중앙 구간 확대 — {base_label} |ΔOR| ≤ {zoom_limit:.1f} (선형 스케일)"
        if base_app else
        f"중앙 구간 확대 — |ΔOR| ≤ {zoom_limit:.1f} (선형 스케일)"
    )
    x_axis_title = (
        f"← {base_app} 경쟁 열위 &nbsp;|&nbsp; ΔOR (선형 스케일) &nbsp;|&nbsp; {base_app} 경쟁 우위 →"
        if base_app else
        "ΔOR (선형 스케일) — ← 경쟁 열위 | 경쟁 우위 →"
    )

    fig.update_layout(
        title=centered_title(zoom_title, size=13),
        xaxis_title=x_axis_title,
        yaxis_title="전략 우선도 점수 (개선 시급성 + 강점 유지 중요도)",
        height=560,
        hovermode="closest",
        margin=dict(l=10, r=30, t=60, b=60),
    )
    apply_dark_theme(fig)
    fig.update_xaxes(range=x_range, zeroline=False)
    fig.update_yaxes(range=y_range, zeroline=False)
    return fig


def render(combined: pd.DataFrame) -> None:
    st.markdown("""
    <div class="info-box">
    <b>기능별 전략 우선도 매트릭스</b>는 어떤 기능을 먼저 개선해야 하는지, 어떤 기능이 현재 강점인지를
    한 눈에 보여주는 2차원 전략 지도입니다.<br><br>
    • <b>가로축 (ΔOR)</b>: 기준 앱 대비 경쟁 우위/열위를 나타냅니다.
    ΔOR = 비교 앱 OR − 기준 앱 OR이며, 오른쪽(+)일수록 기준 앱이 경쟁 우위, 왼쪽(−)일수록 경쟁 열위입니다.<br>
    • <b>세로축 (전략 우선도 점수)</b>: 개선 시급성과 강점 유지 중요도를 종합한 점수입니다.
    위로 갈수록 전략적으로 더 중요한 기능입니다.<br>
    • <b>마커 크기</b>: 전략 우선도 점수에 비례합니다. 큰 원일수록 해당 기능의 중요도가 높습니다.<br><br>
    <b>4개 사분면 해석:</b>
    &nbsp;좌상 <span style="color:#FF8A9A">경쟁 열위·개선 시급</span> — 즉시 개선 필요 /
    &nbsp;우상 <span style="color:#4FD6A5">경쟁 우위 유지</span> — 현재 강점, 차별화 포인트 /
    &nbsp;좌하 <span style="color:#FBB55C">산업 공통 문제</span> — 경쟁사도 약함, 선제 투자 시 차별화 가능 /
    &nbsp;우하 <span style="color:#7BA7F5">현상 유지</span> — 우위이나 우선순위 낮음, 모니터링
    </div>
    """, unsafe_allow_html=True)

    if combined.empty or "delta_or" not in combined.columns:
        st.markdown("""
        <div class="info-box" style="border-left-color:#F59E0B;">
        ⚠️ <b>전략 우선도 매트릭스를 표시하려면 최소 2개 앱의 OR 분석이 필요합니다.</b><br><br>
        가능한 원인:<br>
        &nbsp;&nbsp;① 왼쪽 사이드바에서 <b>앱을 2개 이상 선택</b>해야 ΔOR(오즈비 차이)을 계산할 수 있습니다.<br>
        &nbsp;&nbsp;② 오즈비(OR) 탭에서 먼저 분석이 완료되어야 이 탭이 활성화됩니다.<br>
        &nbsp;&nbsp;③ 선택한 앱들의 리뷰에서 <b>공통으로 등장하는 기능 키워드</b>가 없으면 ΔOR 계산이 불가능합니다.<br><br>
        앱 선택 후 OR 분석이 완료되면 이 화면이 자동으로 매트릭스로 전환됩니다.
        </div>
        """, unsafe_allow_html=True)
        render_skeleton("전략 우선도 매트릭스를 분석중입니다", show_chart=True, chart_height=260)
        return

    matrix_df = get_priority_matrix_df(combined)

    if matrix_df.empty:
        st.markdown("""
        <div class="info-box" style="border-left-color:#F59E0B;">
        ⚠️ <b>전략 우선도 점수 계산 결과가 없습니다.</b><br>
        앱 간 공통 기능 카테고리에서 유효한 ΔOR 값이 계산되지 않았습니다.
        각 앱에서 같은 기능 키워드가 충분히 언급되어야(최소 2건 이상) 비교가 가능합니다.
        OR 탭에서 각 앱의 분석 결과를 먼저 확인해 보세요.
        </div>
        """, unsafe_allow_html=True)
        render_skeleton("전략 우선도 매트릭스를 분석중입니다", show_chart=True, chart_height=260)
        return

    # ── 기준앱 이름 추출 ──────────────────────────────────────────────────────
    selected_apps = st.session_state.get("selected_apps", [])
    base_app_name: str | None = (
        selected_apps[0].app_name if selected_apps else None
    )

    # ── 사분면 분류 헬퍼 ──────────────────────────────────────────────────────
    y_mid = matrix_df["priority_score_max"].median()

    def _area(delta_or: float, score: float) -> str:
        if delta_or < 0 and score >= y_mid:   return "경쟁 열위 · 개선 시급"
        if delta_or >= 0 and score >= y_mid:  return "경쟁 우위 유지"
        if delta_or < 0 and score < y_mid:    return "산업 공통 문제"
        return "현상 유지"

    def _action(area: str) -> str:
        return {
            "경쟁 열위 · 개선 시급": "개선 우선 검토",
            "경쟁 우위 유지":        "강점 유지",
            "산업 공통 문제":        "모니터링",
            "현상 유지":             "현 수준 유지",
        }.get(area, "검토")

    tbl = matrix_df.copy()
    tbl["영역"]      = tbl.apply(lambda r: _area(r["delta_or_mean"], r["priority_score_max"]), axis=1)
    tbl["권장 액션"] = tbl["영역"].map(_action)

    # ── 영역 우선순위 기반 정렬 (경쟁우위 ≠ 개선우선) ─────────────────────────
    tbl["_area_order"] = tbl["영역"].map(_AREA_ORDER).fillna(9)
    tbl = tbl.sort_values(
        ["_area_order", "priority_score_max"],
        ascending=[True, False],
    ).reset_index(drop=True)
    tbl.index = tbl.index + 1

    # ── 메인 차트 ─────────────────────────────────────────────────────────────
    fig = _build_scatter(matrix_df, combined, base_app=base_app_name)
    st.plotly_chart(fig, use_container_width=True)

    # ── 중앙 구간 확대 보조 차트 ──────────────────────────────────────────────
    zoom_limit = float(max(
        min(matrix_df["delta_or_mean"].abs().quantile(0.80), 1.5),
        0.8,
    ))
    fig_zoom = _build_center_zoom(
        matrix_df, combined, base_app=base_app_name, zoom_limit=zoom_limit,
    )
    if fig_zoom is not None:
        st.markdown(
            '<div style="font-size:0.78rem;color:#64748B;margin-top:-0.5rem;margin-bottom:0.3rem;">'
            f'▼ <b>중앙 구간 확대 차트</b> — |ΔOR| ≤ {zoom_limit:.1f} 범위만 선형 스케일로 표시합니다. '
            'ΔOR 값이 작아 위 메인 차트에서 겹쳐 보이는 기능들을 더 명확하게 구분할 수 있습니다. '
            '마커 위에 마우스를 올리면 각 앱의 OR 수치도 확인할 수 있습니다.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(fig_zoom, use_container_width=True)

    # ── Insight ───────────────────────────────────────────────────────────────
    q1 = tbl[tbl["영역"] == "경쟁 열위 · 개선 시급"]
    q2 = tbl[tbl["영역"] == "경쟁 우위 유지"]
    q3 = tbl[tbl["영역"] == "산업 공통 문제"]
    q4 = tbl[tbl["영역"] == "현상 유지"]

    def _feat_list(sub, n=5) -> str:
        return "、".join(sub["feature_category"].head(n).tolist()) or "없음"

    render_insight_box(
        "기능별 전략 우선도 매트릭스 핵심 인사이트",
        "ΔOR(경쟁 우위/열위)과 전략 우선도 점수(개선 시급성 + 강점 유지 중요도)를 결합해 "
        "기능별 전략적 포지션을 4개 사분면으로 분류합니다. "
        "ΔOR = 비교 앱 OR − 기준 앱 OR이며, 음수일수록 기준 앱이 경쟁에서 밀리는 기능입니다. "
        "전략 우선도 점수는 사용자 영향력과 경쟁 격차를 종합한 수치로, 높을수록 먼저 대응해야 합니다.",
        f"총 {len(tbl)}개 기능 중 즉시 개선이 필요한 '경쟁 열위·개선 시급' 영역 {len(q1)}개, "
        f"강점으로 유지해야 할 '경쟁 우위 유지' 영역 {len(q2)}개가 확인됩니다. "
        "아래 상세 테이블에서 각 기능의 ΔOR 수치와 권장 액션을 확인하세요.",
        [
            ("경쟁 열위 · 개선 시급", "#FF8A9A",
             f"총 {len(q1)}개 기능 — ΔOR &lt; 0이고 전략 우선도가 높아 즉시 개선 시 만족도 향상 효과가 가장 큽니다. "
             f"경쟁사 대비 뒤처지는 영역이므로 로드맵 최우선 과제로 설정하세요. "
             f"주요 기능: {_feat_list(q1)}"),
            ("경쟁 우위 유지", "#4FD6A5",
             f"총 {len(q2)}개 기능 — ΔOR &gt; 0이고 전략 우선도가 높아 현재 기준 앱의 핵심 강점입니다. "
             f"이 기능의 품질을 유지·강화하면 차별화 포인트로 마케팅에 활용할 수 있습니다. "
             f"주요 기능: {_feat_list(q2)}"),
            ("산업 공통 문제", "#FBB55C",
             f"총 {len(q3)}개 기능 — ΔOR &lt; 0이지만 전략 우선도가 낮아 경쟁사도 함께 약한 영역입니다. "
             f"업계 전체의 미해결 과제이므로, 선제적으로 개선하면 경쟁사 대비 차별화가 가능합니다. "
             f"주요 기능: {_feat_list(q3)}"),
            ("현상 유지", "#7BA7F5",
             f"총 {len(q4)}개 기능 — ΔOR &gt; 0이지만 전략 우선도가 낮아 현재는 유지만으로 충분한 영역입니다. "
             f"자원이 여유로울 때 모니터링하며 점진적으로 개선하세요. "
             f"주요 기능: {_feat_list(q4)}"),
        ],
        summary=(
            f"🔴 즉시 개선(경쟁 열위·개선 시급) {len(q1)}개 · "
            f"🟢 강점 유지(경쟁 우위 유지) {len(q2)}개 · "
            f"🟡 선제 투자 검토(산업 공통 문제) {len(q3)}개 · "
            f"🔵 현 수준 유지(현상 유지) {len(q4)}개."
        ),
    )

    # ── 기능별 전략 우선도 상세 테이블 (영역별 분리) ─────────────────────────
    st.markdown("#### 기능별 전략 우선도 상세 테이블")
    st.markdown("""
    <div class="info-box">
    본 표의 <b>전략 우선도</b>는 개선이 필요한 기능과 경쟁 우위 유지 기능을 함께 포함한 종합 우선도입니다.<br>
    <b>ΔOR &gt; 0</b> = 기준앱 경쟁 우위 (→ <span style="color:#4FD6A5">강점 유지</span>) &nbsp;/&nbsp;
    <b>ΔOR &lt; 0</b> = 기준앱 경쟁 열위 (→ <span style="color:#FF8A9A">개선 우선 검토</span>)
    </div>
    """, unsafe_allow_html=True)

    def _badge(text: str, area: str) -> str:
        tc, bg = _AREA_STYLE.get(area, ("#94A3B8", "rgba(100,116,139,0.2)"))
        return (
            f'<span style="background:{bg};color:{tc};padding:2px 9px;'
            f'border-radius:99px;font-size:0.73rem;font-weight:700;'
            f'white-space:nowrap;">{text}</span>'
        )

    header_cols = ["전략 우선도", "기능 카테고리", "ΔOR", "OR (기준앱)", "전략 우선도 점수", "권장 액션"]
    right_aligned = {"ΔOR", "OR (기준앱)", "전략 우선도 점수"}

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
                f'padding:8px 12px;text-align:{"right" if h in right_aligned else "left"};'
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

    # ── 다운로드 ──────────────────────────────────────────────────────────────
    csv = combined.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 전체 분석 결과 CSV 다운로드",
        data=csv,
        file_name="priority_analysis_result.csv",
        mime="text/csv",
    )
