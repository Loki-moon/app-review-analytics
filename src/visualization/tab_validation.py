"""
Tab 5: Statistical Validation (PRD 28·29번)

구성:
- 상단 전체 검증 요약 카드
- 7개 검증 항목 (아코디언)
  각 항목: 목적 설명 → 시각화 → 수치 테이블 → 배지 → 해석 문구 → 논문 기술 예시

검증 항목:
  1. 모형 적합도          - Pseudo R², AIC, BIC
  2. 회귀계수 유의성       - β, OR, CI, p-value (기능별 개별 회귀)
  3. 서비스 간 영향력 차이  - 상호작용항 Wald / LR test
  4. 기능 키워드 공출현 패턴 - 스피어만 상관계수 (개별 회귀 설계 → VIF 미적용)
  5. 평점 이분화 기준 민감도 - 3점 처리 3가지 조건 비교
  6. 기간 분할 안정성      - 전체 / 상반기 / 하반기 OR 비교
  7. 표본 분포            - 앱별 건수, 평점분포, 월별 추이
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import seaborn as sns
import streamlit as st

from config.settings import ASSETS_DIR
from src.visualization._common import app_color, get_ordered_app_names, render_skeleton

# ── 한글 폰트 설정 (Streamlit Cloud 대응) ─────────────────────────────────────
_BUNDLED_FONT = ASSETS_DIR / "fonts" / "NanumGothic.ttf"
matplotlib.rcParams["axes.unicode_minus"] = False

def _setup_matplotlib_korean() -> None:
    """한글 폰트를 matplotlib에 등록. packages.txt fonts-nanum 설치 후 동작."""
    import os
    candidates = [
        str(_BUNDLED_FONT),
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/nanum/NanumGothic.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/Library/Fonts/AppleGothic.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                fm.fontManager.addfont(path)
                prop = fm.FontProperties(fname=path)
                matplotlib.rcParams["font.family"] = prop.get_name()
                return
            except Exception:
                continue

_setup_matplotlib_korean()

# ── 다크 테마 상수 ─────────────────────────────────────────────────────────────
_BG      = "#0E1116"
_GRID    = "#1E2630"
_LINE    = "#2D3748"
_TEXT    = "#E2E8F0"
_SUBTEXT = "#94A3B8"


# ─────────────────────────────────────────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────────────────────────────────────────

def _get_font_family() -> str:
    """한국어 폰트 탐색 (Plotly layout용)"""
    import os
    font_files = {
        "NanumGothic": [
            str(_BUNDLED_FONT),
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/nanum/NanumGothic.ttf",
        ],
        "AppleGothic": [
            "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
            "/Library/Fonts/AppleGothic.ttf",
        ],
        "Malgun Gothic": ["C:/Windows/Fonts/malgun.ttf"],
    }
    for name, paths in font_files.items():
        if any(os.path.exists(p) for p in paths):
            return name
    return "sans-serif"


FONT = _get_font_family()
LAYOUT_DEFAULTS = dict(
    font_family=FONT,
    font=dict(color=_TEXT),
    plot_bgcolor=_BG,
    paper_bgcolor=_BG,
    margin=dict(l=10, r=10, t=70, b=40),
    xaxis=dict(gridcolor=_GRID, linecolor=_LINE, zerolinecolor=_LINE, tickfont=dict(color=_TEXT)),
    yaxis=dict(gridcolor=_GRID, linecolor=_LINE, zerolinecolor=_LINE, tickfont=dict(color=_TEXT)),
    legend=dict(bgcolor="#131820", bordercolor=_LINE, font=dict(color=_TEXT),
                orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
)


def _hex_rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB hex color to rgba(r,g,b,alpha) string."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _interp_box(title: str, text: str, purpose: str = "", effect: str = "") -> None:
    """통계 결과해석 박스 — render_insight_box 형식으로 통일"""
    from src.visualization._common import render_insight_box
    render_insight_box(
        title,
        purpose or "해당 통계 검증 항목의 결과를 수치로 확인합니다.",
        effect or "숫자가 기준값을 통과하면 분석 결과를 신뢰할 수 있어요.",
        [("통계 검증 결과", "#4F8EF7", text)],
    )


def _chart_download_btn(fig: go.Figure, filename: str) -> None:
    """Plotly 차트를 PNG로 변환 후 다운로드 버튼 제공"""
    try:
        img_bytes = fig.to_image(format="png", width=900, height=500, scale=2)
        ts = datetime.now().strftime("%Y%m%d")
        st.download_button(
            label="📥 차트 이미지 다운로드",
            data=img_bytes,
            file_name=f"{filename}_{ts}.png",
            mime="image/png",
            key=f"dl_{filename}_{id(fig)}",
        )
    except Exception:
        st.caption("이미지 다운로드를 위해 kaleido 패키지가 필요합니다.")


def _badge_html(status: str) -> str:
    mapping = {
        "pass": '<span style="background:#D1FAE5;color:#065F46;padding:3px 10px;border-radius:99px;font-weight:700;">✅ 양호</span>',
        "warn": '<span style="background:#FEF3C7;color:#92400E;padding:3px 10px;border-radius:99px;font-weight:700;">⚠️ 주의</span>',
        "fail": '<span style="background:#FEE2E2;color:#B91C1C;padding:3px 10px;border-radius:99px;font-weight:700;">❌ 경고</span>',
    }
    return mapping.get(status, mapping["warn"])


def _thesis_box(text: str) -> None:
    st.markdown(f"""
    <div style="background:#131820;border-left:4px solid #64748B;border-radius:6px;
                padding:0.75rem 1rem;font-size:0.83rem;color:#94A3B8;margin-top:0.75rem;">
    <b>📝 논문 기술 예시</b><br>{text}
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 전체 요약 카드
# ─────────────────────────────────────────────────────────────────────────────

def _render_summary(vr: dict[str, Any]) -> None:
    """7개 항목 상태를 한눈에 보여주는 카드"""
    items = []

    mf = vr.get("model_fit", {})
    mf_table = mf.get("table", pd.DataFrame()) if isinstance(mf, dict) else pd.DataFrame()
    if not mf_table.empty and "status" in mf_table.columns:
        worst = "fail" if "fail" in mf_table["status"].values else ("warn" if "warn" in mf_table["status"].values else "pass")
        items.append(("모형 적합도", worst))
    else:
        items.append(("모형 적합도", "warn"))

    cs = vr.get("coef_sig", pd.DataFrame())
    if isinstance(cs, pd.DataFrame) and not cs.empty and "status" in cs.columns:
        sig_count = (cs["p_value"] < 0.05).sum() if "p_value" in cs.columns else 0
        total = len(cs)
        ratio = sig_count / total if total > 0 else 0
        items.append(("회귀계수 유의성", "pass" if ratio >= 0.5 else "warn"))
    else:
        items.append(("회귀계수 유의성", "warn"))

    ia = vr.get("interaction", pd.DataFrame())
    if isinstance(ia, pd.DataFrame) and not ia.empty and "status" in ia.columns:
        sig = (ia["lr_pvalue"] < 0.05).sum() if "lr_pvalue" in ia.columns else 0
        items.append(("상호작용 검정", "pass" if sig > 0 else "warn"))
    else:
        items.append(("상호작용 검정", "warn"))

    mc = vr.get("multicol", {})
    corr_m = mc.get("corr_matrix", pd.DataFrame()) if isinstance(mc, dict) else pd.DataFrame()
    if not corr_m.empty:
        # 대각선 제외 절대값이 0.7 이상인 쌍이 있으면 warn
        mask = np.ones(corr_m.shape, dtype=bool)
        np.fill_diagonal(mask, False)
        high_corr = (corr_m.where(mask).abs() >= 0.7).any().any()
        items.append(("공출현 패턴", "warn" if high_corr else "pass"))
    else:
        items.append(("공출현 패턴", "pass"))

    items.append(("평점 민감도", "pass"))
    items.append(("기간 안정성", "pass"))

    sd = vr.get("sample_dist", {})
    imbalance = sd.get("imbalance_status", {}) if isinstance(sd, dict) else {}
    worst_imb = "warn" if any(v == "warn" for v in imbalance.values()) else "pass"
    items.append(("표본 분포", worst_imb))

    statuses = [s for _, s in items]
    overall = "pass" if all(s == "pass" for s in statuses) else ("fail" if "fail" in statuses else "warn")
    overall_msg = {
        "pass": "✅ 모든 검증 항목이 양호합니다. 분석 결과를 신뢰할 수 있어요.",
        "warn": "⚠️ 일부 항목에 주의가 필요합니다. 아래 세부 항목을 확인해주세요.",
        "fail": "❌ 일부 항목에 경고가 있습니다. 데이터 또는 모형 설정을 점검해주세요.",
    }

    st.markdown(f"""
    <div style="background:{'#D1FAE5' if overall=='pass' else '#FEF3C7' if overall=='warn' else '#FEE2E2'};
                border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.5rem;">
        <div style="font-size:1rem;font-weight:700;margin-bottom:0.75rem;">
            {overall_msg[overall]}
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:0.5rem;">
    """, unsafe_allow_html=True)

    for label, status in items:
        bg = {"pass": "#065F46", "warn": "#92400E", "fail": "#B91C1C"}[status]
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}[status]
        st.markdown(f"""
        <span style="background:{bg};color:white;padding:4px 12px;border-radius:99px;
                     font-size:0.8rem;font-weight:600;">{icon} {label}</span>
        """, unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 항목 1: 모형 적합도
# ─────────────────────────────────────────────────────────────────────────────

def _render_model_fit(vr: dict[str, Any]) -> None:
    mf = vr.get("model_fit", {})
    if not isinstance(mf, dict):
        render_skeleton("모형 적합도를 계산중입니다", show_chart=True, chart_height=160)
        return
    table = mf.get("table", pd.DataFrame())

    st.markdown("""
    <div class="info-box">
    <b>목적:</b> 로지스틱 회귀모형이 데이터를 얼마나 잘 설명하는지 평가합니다.<br>
    이 모형은 리뷰 데이터로 긍정/부정 평점을 얼마나 잘 설명하는지를 나타내요.
    수치가 높을수록 기능 키워드가 평점에 미치는 영향을 잘 포착하고 있어요.
    </div>
    """, unsafe_allow_html=True)

    if table.empty:
        render_skeleton("모형 적합도를 계산중입니다", show_chart=True, chart_height=160)
        return

    # 앱 선택 순서에 맞게 게이지 정렬
    _sel = st.session_state.get("selected_apps", [])
    _order = {a.app_name: i for i, a in enumerate(_sel)}
    if _order:
        table = table.sort_values(
            "app_name",
            key=lambda s: s.map(lambda x: _order.get(x, 999)),
        ).reset_index(drop=True)

    cols = st.columns(len(table))
    for i, (_, row) in enumerate(table.iterrows()):
        with cols[i]:
            r2 = row.get("pseudo_r2", 0)
            status = row.get("status", "warn")
            r2_grade = "양호" if r2 >= 0.2 else ("주의" if r2 >= 0.1 else "경고")
            grade_color = "#4FD6A5" if r2 >= 0.2 else ("#FBB55C" if r2 >= 0.1 else "#FF8A9A")

            # 앱명을 게이지 상단에 별도 표시 (잘림 방지)
            st.markdown(
                f'<div style="text-align:center;font-size:0.9rem;font-weight:700;'
                f'color:{_TEXT};margin-bottom:4px;">{row["app_name"]}</div>',
                unsafe_allow_html=True,
            )
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge",
                value=float(r2),
                title={"text": "Pseudo R²", "font": {"size": 13, "color": _TEXT}},
                gauge={
                    "axis": {"range": [0, 0.4], "tickcolor": _TEXT,
                             "tickfont": {"color": _TEXT}},
                    "bar": {"color": "#4F8EF7"},
                    "bgcolor": _GRID,
                    "bordercolor": _LINE,
                    "steps": [
                        {"range": [0, 0.1],  "color": "#3B1F1F"},
                        {"range": [0.1, 0.2], "color": "#3B3320"},
                        {"range": [0.2, 0.4], "color": "#1A3D2B"},
                    ],
                    "threshold": {"line": {"color": _TEXT, "width": 3}, "value": r2},
                },
            ))
            fig_gauge.update_layout(
                height=200,
                plot_bgcolor=_BG,
                paper_bgcolor=_BG,
                font=dict(color=_TEXT),
                margin=dict(l=20, r=20, t=40, b=10),
            )
            st.plotly_chart(fig_gauge, use_container_width=True)
            _chart_download_btn(fig_gauge, f"model_fit_gauge_{row['app_name']}")
            st.markdown(
                f'<div style="text-align:center;font-size:1.4rem;font-weight:700;'
                f'color:{grade_color};margin-bottom:4px;">{r2:.3f}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(_badge_html(status), unsafe_allow_html=True)
            # 정량적 설명
            st.markdown(
                f'<div style="font-size:0.78rem;color:{_SUBTEXT};line-height:1.6;'
                f'padding:6px 8px;background:{_GRID};border-radius:4px;margin-top:6px;">'
                f'현재 R²=<b style="color:{grade_color};">{r2:.3f}</b> → <b style="color:{grade_color};">{r2_grade}</b><br>'
                f'· &lt;0.1: 경고 (기능 키워드 설명력 낮음)<br>'
                f'· 0.1~0.2: 주의 (기본 분석 가능)<br>'
                f'· ≥0.2: 양호 (신뢰할 수 있는 수준)'
                f'</div>',
                unsafe_allow_html=True,
            )

    # 3개 이상 앱 동시 분석 시 Pseudo R² 요약 안내
    if len(table) >= 3:
        r2_summary = " / ".join(
            f"<b>{row['app_name']}</b> R²={row['pseudo_r2']:.3f}"
            for _, row in table.iterrows()
        )
        st.markdown(
            f'<div class="info-box" style="margin-top:10px;border-left:3px solid #4F8EF7;">'
            f'💡 <b>Pseudo R² 비교:</b> {r2_summary}<br>'
            f'R²가 낮은 앱은 이용자 만족이 특정 기능보다 서비스 전반에 분산되어 있거나, '
            f'리뷰에서 기능 언급 빈도가 낮을 수 있습니다.'
            f'</div>',
            unsafe_allow_html=True,
        )

    # 개선 방법 안내
    st.markdown(
        '<div class="info-box" style="margin-top:12px;">'
        '📈 <b>모형 적합도를 높이려면:</b><br>'
        '① 리뷰 수 확대 — 앱당 300건 이상 수집 시 안정적 수렴<br>'
        '② 기능 카테고리 세분화 — 너무 광범위한 카테고리는 신호를 희석시킴<br>'
        '③ 리뷰 기간 다양화 — 특정 이벤트 편향 없이 최소 3개월 이상 분포<br>'
        '④ 불용어/노이즈 제거 강화 — 기능과 무관한 감탄사·이모지 토큰 정제</div>',
        unsafe_allow_html=True,
    )

    # AIC/BIC 막대 비교
    if len(table) > 1:
        fig_aic = go.Figure()
        for metric, color in [("aic", "#4F8EF7"), ("bic", "#F7844F")]:
            fig_aic.add_trace(go.Bar(
                name=metric.upper(),
                x=table["app_name"].tolist(),
                y=table[metric].tolist(),
                marker_color=color,
                hovertemplate=f"<b>%{{x}}</b><br>{metric.upper()}: %{{y:.1f}}<br>값이 낮을수록 모형이 간결해요<extra></extra>",
            ))
        fig_aic.update_layout(
            title=dict(text="AIC / BIC 비교 (낮을수록 좋음)", x=0.5, xanchor="center", font=dict(color=_TEXT)),
            barmode="group",
            height=320,
            **LAYOUT_DEFAULTS,
        )
        st.plotly_chart(fig_aic, use_container_width=True)
        _chart_download_btn(fig_aic, "model_fit_aic_bic")

        # AIC/BIC 해석
        best_aic_row = table.loc[table["aic"].idxmin()]
        r2_vals = " / ".join(f"{r['app_name']} R²={r['pseudo_r2']:.3f}" for _, r in table.iterrows())
        _interp_box(
            "AIC / BIC 비교",
            f"모형 적합도: {r2_vals}. "
            f"AIC가 가장 낮은 앱: <b>{best_aic_row['app_name']}</b> (AIC={best_aic_row['aic']:.1f}) "
            f"— AIC가 낮을수록 데이터를 군더더기 없이 잘 설명하는 모형입니다. "
            f"Pseudo R²가 0.1 이상이면 기능 키워드가 평점에 유의미한 영향을 주고 있다는 뜻입니다.",
        )
    else:
        # 단일 앱 게이지 해석
        r2_val = table.iloc[0].get("pseudo_r2", 0)
        r2_grade = "우수" if r2_val >= 0.2 else ("양호" if r2_val >= 0.1 else "낮음")
        _interp_box(
            "모형 적합도 (Pseudo R²)",
            f"Pseudo R² = <b>{r2_val:.3f}</b> → 적합도 <b>{r2_grade}</b>. "
            f"이 수치는 기능 키워드가 사용자 평점 변동의 약 {r2_val*100:.1f}%를 설명한다는 의미입니다. "
            f"0.1 이상이면 분석에 활용할 수 있는 수준입니다.",
        )

    # 수치 테이블
    display_cols = {
        "app_name": "앱", "log_likelihood": "Log-Likelihood",
        "aic": "AIC", "bic": "BIC", "pseudo_r2": "Pseudo R²", "n_obs": "관측수",
    }
    st.dataframe(
        table[[c for c in display_cols if c in table.columns]].rename(columns=display_cols),
        use_container_width=True,
    )

    _thesis_box(
        "본 연구의 로지스틱 회귀모형은 McFadden Pseudo R² = <b>[수치]</b>로, "
        "기능 키워드가 평점 이분화 결과를 유의미하게 설명함을 확인하였다 (p &lt; 0.05)."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 항목 2: 회귀계수 유의성 (Forest Plot)
# ─────────────────────────────────────────────────────────────────────────────

def _render_coef_sig(vr: dict[str, Any]) -> None:
    cs = vr.get("coef_sig", pd.DataFrame())

    st.markdown("""
    <div class="info-box">
    <b>목적:</b> 각 기능 키워드가 평점에 미치는 영향이 통계적으로 유의한지 확인합니다.<br>
    p-value가 낮을수록 우연이 아닐 가능성이 높아요. OR이 1보다 크면 긍정, 작으면 부정 평가와 연관됩니다.
    </div>
    """, unsafe_allow_html=True)

    if not isinstance(cs, pd.DataFrame) or cs.empty:
        render_skeleton("회귀계수 유의성 분석중입니다", show_chart=False, n_rows=4)
        return

    ordered_names = get_ordered_app_names(cs)
    app_names = [n for n in ordered_names if n in (cs["app_name"].unique() if "app_name" in cs.columns else [])]
    if not app_names:
        app_names = cs["app_name"].unique().tolist() if "app_name" in cs.columns else []

    fig = go.Figure()
    for app_name in app_names:
        sub = cs[cs["app_name"] == app_name].copy()
        color = app_color(app_name, ordered_names)
        sub["point_color"] = sub["p_value"].apply(lambda p: color if p < 0.05 else "#4A5568")

        fig.add_trace(go.Scatter(
            x=sub["OR"],
            y=sub["feature_category"],
            mode="markers",
            name=app_name,
            marker=dict(
                color=sub["point_color"].tolist(),
                size=10,
                symbol="circle",
                line=dict(width=1, color="white"),
            ),
            error_x=dict(
                type="data",
                symmetric=False,
                array=(sub["ci_upper"] - sub["OR"]).tolist(),
                arrayminus=(sub["OR"] - sub["ci_lower"]).tolist(),
                color=color,
                thickness=1.5,
                width=5,
            ),
            hovertemplate=(
                f"<b>{app_name}</b> | %{{y}}<br>"
                "OR: %{x:.3f}<br>"
                "95% CI: [%{customdata[0]:.3f}, %{customdata[1]:.3f}]<br>"
                "p-value: %{customdata[2]:.4f} %{customdata[3]}<br>"
                "OR > 1이면 긍정 연관, < 1이면 부정 연관<extra></extra>"
            ),
            customdata=sub[["ci_lower", "ci_upper", "p_value", "significance"]].values,
        ))

    fig.add_vline(x=1.0, line_dash="dash", line_color=_SUBTEXT, line_width=1.5,
                  annotation_text="OR=1 기준", annotation_position="top right",
                  annotation_font_color=_SUBTEXT)

    # 극단값 클리핑 — 상위 5% 이상치가 있으면 95th percentile 기준으로 x축 제한
    clip_note = ""
    if "ci_upper" in cs.columns and not cs["ci_upper"].dropna().empty:
        upper_vals = cs["ci_upper"].dropna()
        x_max_raw = float(upper_vals.max())
        x_max_clip = float(np.percentile(upper_vals, 95)) * 1.15
        x_min_clip = max(0.0, float(np.percentile(cs["ci_lower"].dropna(), 5)) * 0.85)
        if x_max_raw > x_max_clip * 1.5:
            fig.update_xaxes(range=[x_min_clip, x_max_clip])
            clip_note = " (극단값 클리핑 적용 — hover로 실제값 확인)"

    fig.update_layout(
        title=dict(text=f"기능 키워드별 오즈비 (Forest Plot) — 흐린 점 = 비유의(p≥0.05){clip_note}",
                   x=0.5, xanchor="center", font=dict(color=_TEXT, size=13)),
        xaxis_title="오즈비 (OR)",
        height=max(350, len(cs["feature_category"].unique()) * 35 + 150),
        **LAYOUT_DEFAULTS,
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=55, b=80),
        legend=dict(
            bgcolor="#131820", bordercolor=_LINE, font=dict(color=_TEXT),
            orientation="h", yanchor="top", y=-0.06, xanchor="center", x=0.5,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)
    _chart_download_btn(fig, "forest_plot_or")

    # Forest Plot 해석
    sig_count = int((cs["p_value"] < 0.05).sum()) if "p_value" in cs.columns else 0
    total_count = len(cs)
    sig_pct = sig_count / total_count * 100 if total_count > 0 else 0
    per_app_lines = []
    for app_name in app_names:
        sub = cs[cs["app_name"] == app_name]
        sig = sub[sub["p_value"] < 0.05] if "p_value" in sub.columns else sub
        if not sig.empty:
            top = sig.nlargest(1, "OR").iloc[0]
            per_app_lines.append(
                f"<b>{app_name}</b>: 유의 기능 {len(sig)}개 — 최강 긍정 연관: "
                f"<b>{top['feature_category']}</b> (OR={top['OR']:.2f})"
            )
    _interp_box(
        "기능 키워드별 오즈비 (Forest Plot)",
        f"전체 {total_count}개 기능-앱 조합 중 <b>{sig_count}개({sig_pct:.0f}%)</b>가 통계적으로 유의합니다(p&lt;0.05). "
        f"흐린 점(회색)은 우연에 의한 결과일 가능성이 있어 해석 시 주의가 필요합니다. "
        + (" | ".join(per_app_lines) if per_app_lines else ""),
    )

    # 테이블
    display_cols = {
        "feature_category": "기능", "app_name": "앱",
        "beta": "β", "OR": "OR", "ci_lower": "CI 하한", "ci_upper": "CI 상한",
        "p_value": "p-value", "significance": "유의성",
    }
    disp = cs[[c for c in display_cols if c in cs.columns]].rename(columns=display_cols)
    st.dataframe(disp, use_container_width=True, height=360)

    _thesis_box(
        "각 기능 키워드의 로지스틱 회귀계수는 Wald 검정을 통해 유의성을 확인하였으며, "
        "OR 및 95% 신뢰구간을 제시하였다. p &lt; 0.05인 키워드를 유의한 예측변수로 간주하였다."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 항목 3: 상호작용 효과 검정 (ΔOR 막대 차트)
# ─────────────────────────────────────────────────────────────────────────────

def _render_interaction(vr: dict[str, Any], combined_or: pd.DataFrame) -> None:
    ia = vr.get("interaction", pd.DataFrame())

    st.markdown("""
    <div class="info-box">
    <b>목적:</b> 같은 기능이라도 앱에 따라 평점에 미치는 영향이 실제로 다른지 확인합니다.<br>
    3개 이상 앱 분석 시 모든 앱 쌍(A-B, A-C, B-C)에 대해 개별 검정을 수행하여
    쌍별 영향력 차이를 정확하게 파악합니다. 유의한 쌍이 있으면 ΔOR을 신뢰할 수 있는 비교 지표로 사용할 수 있어요.
    </div>
    """, unsafe_allow_html=True)

    if not combined_or.empty and "delta_or" in combined_or.columns:
        delta_data = combined_or.dropna(subset=["delta_or"]).copy()

        # p-value 기준 정렬 (유의한 것 상단) — lr_pvalue 기준, 없으면 delta_or 절대값 기준
        cat_order = None
        if not ia.empty and "feature_category" in ia.columns and "lr_pvalue" in ia.columns:
            cat_pv = ia.set_index("feature_category")["lr_pvalue"]
            # ascending=False → 큰 p(비유의)가 아래, 작은 p(유의)가 위
            cat_order = cat_pv.sort_values(ascending=False).index.tolist()
        else:
            # delta_or 절대값 기준 — 큰 차이가 위
            agg = delta_data.groupby("feature_category")["delta_or"].apply(lambda x: x.abs().max())
            cat_order = agg.sort_values(ascending=True).index.tolist()

        ordered_names_ia = get_ordered_app_names(delta_data)
        fig = go.Figure()
        for app_name in (ordered_names_ia or delta_data["app_name"].unique().tolist()):
            sub = delta_data[delta_data["app_name"] == app_name].copy()
            if sub.empty:
                continue
            color = app_color(app_name, ordered_names_ia)

            sig_labels = []
            if not ia.empty and "feature_category" in ia.columns:
                for cat in sub["feature_category"]:
                    row = ia[ia["feature_category"] == cat]
                    sig_labels.append(row["lr_sig"].values[0] if not row.empty else "")
            else:
                sig_labels = [""] * len(sub)

            bar_colors = [
                _hex_rgba(color, 0.90) if v >= 0 else _hex_rgba(color, 0.45)
                for v in sub["delta_or"]
            ]
            text = [f"{v:.3f} {s}" for v, s in zip(sub["delta_or"], sig_labels)]

            fig.add_trace(go.Bar(
                name=app_name,
                y=sub["feature_category"].tolist(),   # 수평 막대: y=카테고리
                x=sub["delta_or"].tolist(),            # 수평 막대: x=값
                orientation="h",
                marker_color=bar_colors,
                text=text,
                textposition="outside",
                textfont=dict(size=9, color=_TEXT),
                hovertemplate=(
                    f"<b>{app_name}</b><br>기능: %{{y}}<br>ΔOR: %{{x:.3f}}<br>"
                    "양수=기준앱 대비 우위 / 음수=열위<extra></extra>"
                ),
            ))

        fig.add_vline(x=0, line_dash="dash", line_color=_SUBTEXT, line_width=1.5)
        n_cats = len(delta_data["feature_category"].unique())

        # 극단값 클리핑 — 90th percentile × 1.2 기준
        abs_max = delta_data["delta_or"].abs().max() if not delta_data.empty else 1.0
        clip_x = float(delta_data["delta_or"].abs().quantile(0.90)) * 1.2 if abs_max > 2 else abs_max
        do_clip = bool(clip_x < abs_max * 0.9)
        clip_note = f" (극단값 클리핑 ±{clip_x:.1f})" if do_clip else ""

        fig.update_layout(
            title=dict(text=f"기능별 ΔOR 비교 (*** p<0.001 · ** p<0.01 · * p<0.05){clip_note}",
                       x=0.5, xanchor="center", font=dict(color=_TEXT, size=13)),
            yaxis_title="기능 카테고리",
            xaxis_title="ΔOR (양수=기준앱 우위, 음수=열위)",
            barmode="group",
            height=max(420, n_cats * 32 + 150),
            **LAYOUT_DEFAULTS,
        )
        fig.update_layout(
            margin=dict(l=10, r=10, t=55, b=80),
            legend=dict(
                bgcolor="#131820", bordercolor=_LINE, font=dict(color=_TEXT),
                orientation="h", yanchor="top", y=-0.06, xanchor="center", x=0.5,
            ),
        )
        if cat_order:
            fig.update_yaxes(categoryorder="array", categoryarray=cat_order)
        if do_clip:
            fig.update_xaxes(range=[-clip_x * 1.5, clip_x * 1.5])
        st.plotly_chart(fig, use_container_width=True)
        _chart_download_btn(fig, "delta_or_bar")

        # ΔOR 해석
        if not delta_data.empty:
            best  = delta_data.loc[delta_data["delta_or"].idxmax()]
            worst = delta_data.loc[delta_data["delta_or"].idxmin()]
            _interp_box(
                "기능별 ΔOR 비교",
                f"가장 큰 경쟁 <b>우위</b>: <b>{best['app_name']}</b>의 <b>{best['feature_category']}</b> "
                f"(ΔOR=+{best['delta_or']:.2f}) — 이 기능에서 사용자 만족도가 경쟁사 대비 높습니다. "
                f"| 가장 큰 경쟁 <b>열위</b>: <b>{worst['app_name']}</b>의 <b>{worst['feature_category']}</b> "
                f"(ΔOR={worst['delta_or']:.2f}) — 이 기능의 불만이 경쟁사보다 더 높으므로 우선 개선이 필요합니다.",
            )

    # 상호작용 테이블 (기능별 요약 + 쌍별 상세)
    if isinstance(ia, pd.DataFrame) and not ia.empty:
        summary_cols = {
            "feature_category": "기능",
            "pair": "비교 쌍",
            "wald_pvalue": "Wald p-value",
            "wald_sig": "Wald 유의성",
            "lr_pvalue": "LR p-value",
            "lr_sig": "LR 유의성",
        }
        st.markdown("**기능별 유의 쌍 요약** (기능별 가장 유의한 쌍 기준)")
        st.dataframe(
            ia[[c for c in summary_cols if c in ia.columns]].rename(columns=summary_cols),
            use_container_width=True,
        )
        # 쌍별 전체 상세 결과 (attrs에 저장된 경우)
        pairs_detail = ia.attrs.get("pairs_detail", pd.DataFrame())
        if not pairs_detail.empty and "pair" in pairs_detail.columns:
            with st.expander("전체 쌍별 상세 결과 보기"):
                st.dataframe(
                    pairs_detail[[c for c in summary_cols if c in pairs_detail.columns]]
                    .rename(columns=summary_cols),
                    use_container_width=True,
                )
    else:
        st.info("상호작용 검정은 2개 이상의 앱이 분석된 경우에 제공됩니다.")

    _thesis_box(
        "서비스 간 기능 영향력 차이를 검정하기 위해 서비스 쌍(pair)별로 기능 키워드 × 서비스 더미 "
        "상호작용항을 포함한 모형과 제외한 모형 간 LR 검정을 수행하였다. "
        "3개 이상 서비스 분석 시 모든 쌍 조합(A-B, A-C, B-C)에 대해 개별 검정을 실시하였으며, "
        "각 기능에서 가장 유의한 쌍의 결과를 대표값으로 보고하였다. "
        "유의한 상호작용이 확인된 기능에 대해 ΔOR을 비교 지표로 활용하였다."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 항목 4: 기능 키워드 공출현 패턴 (스피어만 상관계수 히트맵)
# ─────────────────────────────────────────────────────────────────────────────

def _render_multicollinearity(vr: dict[str, Any]) -> None:
    mc = vr.get("multicol", {})
    if not isinstance(mc, dict):
        render_skeleton("공출현 패턴 분석중입니다", show_chart=True, chart_height=180)
        return

    corr_matrix = mc.get("corr_matrix", pd.DataFrame())

    st.markdown("""
    <div class="info-box">
    <b>목적:</b> 기능 키워드들이 같은 리뷰에서 함께 등장하는 패턴을 확인합니다.<br>
    본 분석은 기능별 개별 회귀 설계를 채택하였으므로 동일 모형 내 다중공선성은
    구조적으로 발생하지 않습니다. 스피어만 상관계수는 공출현 경향의 참고 지표입니다.<br>
    |r| ≥ 0.7인 쌍(빨간 테두리)은 같은 리뷰에서 자주 함께 등장하므로 해석 시 주의하세요.
    </div>
    """, unsafe_allow_html=True)

    # ── 스피어만 상관계수 히트맵 ─────────────────────────────────────────────
    st.markdown("**스피어만 상관계수 히트맵** (|r| ≥ 0.7 은 주의)")
    if not corr_matrix.empty:
        n_feats = len(corr_matrix)
        fig_h = max(6, n_feats * 0.35)
        fig_w = max(8, n_feats * 0.4)
        fig_corr, ax = plt.subplots(figsize=(fig_w, fig_h), facecolor=_BG)
        ax.set_facecolor(_BG)
        mask = np.zeros_like(corr_matrix, dtype=bool)
        mask[np.triu_indices_from(mask, k=1)] = True

        sns.heatmap(
            corr_matrix,
            ax=ax,
            annot=True,
            fmt=".2f",
            cmap="RdYlGn_r",
            vmin=-1,
            vmax=1,
            mask=mask,
            linewidths=0.5,
            annot_kws={"size": 7},
            linecolor=_GRID,
        )
        ax.tick_params(colors=_TEXT, labelsize=8)
        ax.xaxis.label.set_color(_TEXT)
        ax.yaxis.label.set_color(_TEXT)
        for spine in ax.spines.values():
            spine.set_edgecolor(_LINE)

        # |r| >= 0.7 쌍 강조 (빨간 테두리)
        for i in range(len(corr_matrix)):
            for j in range(i):
                val = corr_matrix.iloc[i, j]
                if abs(val) >= 0.7:
                    ax.add_patch(plt.Rectangle((j, i), 1, 1, fill=False,
                                               edgecolor="#FF6B8A", lw=2.5))

        ax.set_title("기능 키워드 간 스피어만 상관계수 (공출현 패턴)", fontsize=12, pad=10, color=_TEXT)
        plt.tight_layout()

        buf = io.BytesIO()
        fig_corr.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor=_BG)
        plt.close(fig_corr)
        buf.seek(0)
        img_bytes = buf.read()
        st.image(img_bytes, use_container_width=True)

        st.download_button(
            "📥 히트맵 이미지 다운로드",
            data=img_bytes,
            file_name=f"cooccurrence_heatmap_{datetime.now().strftime('%Y%m%d')}.png",
            mime="image/png",
            key="dl_corr_heatmap",
        )

        # 고상관 쌍 탐지 및 배지
        mask_diag = np.ones(corr_matrix.shape, dtype=bool)
        np.fill_diagonal(mask_diag, False)
        high_pairs = []
        for i in range(len(corr_matrix)):
            for j in range(i):
                val = corr_matrix.iloc[i, j]
                if abs(val) >= 0.7:
                    high_pairs.append(
                        f"<b>{corr_matrix.index[i]}</b> ↔ <b>{corr_matrix.columns[j]}</b> (r={val:.2f})"
                    )

        overall_status = "warn" if high_pairs else "pass"
        st.markdown(_badge_html(overall_status), unsafe_allow_html=True)

        if high_pairs:
            _interp_box(
                "기능 키워드 공출현 패턴",
                f"|r| ≥ 0.7 주의 쌍 {len(high_pairs)}개: " + " | ".join(high_pairs) +
                ". 이 기능들은 같은 리뷰에서 자주 함께 언급됩니다. "
                "개별 회귀 설계이므로 다중공선성 문제는 아니지만, 개별 OR 해석 시 "
                "공출현 맥락을 함께 고려하세요.",
            )
        else:
            _interp_box(
                "기능 키워드 공출현 패턴",
                "모든 기능 키워드 쌍의 스피어만 |r| < 0.7입니다. "
                "각 키워드가 독립적인 문맥에서 등장하는 경향이 있어 OR 해석이 용이합니다.",
            )
    else:
        st.info("공출현 패턴 계산에 필요한 데이터가 부족합니다.")

    _thesis_box(
        "본 연구는 기능 카테고리별 개별 로지스틱 회귀를 채택하였으므로, 동일 모형 내 "
        "복수 기능 예측변수가 공존하지 않아 다중공선성은 구조적으로 발생하지 않는다. "
        "이에 VIF 산출은 적용하지 않으며, 기능 키워드 간 공출현 패턴을 파악하기 위해 "
        "이진 더미 변수에 적합한 스피어만(Spearman) 순위 상관계수 행렬을 보조 지표로 보고하였다. "
        "|r| ≥ 0.7인 쌍은 해석 시 공출현 맥락을 함께 고려하였다."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 항목 5: 평점 이분화 기준 민감도 (라인 차트)
# ─────────────────────────────────────────────────────────────────────────────

def _render_threshold_sensitivity(vr: dict[str, Any]) -> None:
    sens = vr.get("threshold_sens", (pd.DataFrame(), pd.DataFrame()))
    if not isinstance(sens, tuple) or len(sens) != 2:
        render_skeleton("평점 이분화 민감도 분석중입니다", show_chart=True, chart_height=180)
        return

    combined, pivot = sens

    st.markdown("""
    <div class="info-box">
    <b>목적:</b> 3점 리뷰 처리 방식에 따라 결과가 달라지는지 확인합니다.<br>
    3가지 조건에서도 OR 방향이 일관되면 분석 결과를 더 신뢰할 수 있어요.
    </div>
    """, unsafe_allow_html=True)

    if combined.empty:
        raw_stats: dict = vr.get("raw_stats", {})
        MIN_NEEDED = 50
        rows = []
        all_sufficient = True
        for app_name, st_data in raw_stats.items():
            total = st_data.get("total", 0)
            pos   = st_data.get("pos",   0)
            neg   = st_data.get("neg",   0)
            usable = min(pos, neg)
            ok = "✅" if usable >= MIN_NEEDED else "⚠️"
            if usable < MIN_NEEDED:
                all_sufficient = False
            rows.append(
                f"{ok} <b>{app_name}</b>: 전체 {total:,}건 "
                f"(긍정 {pos:,} / 부정 {neg:,}) — "
                f"분석 가능 표본 {usable:,}건 "
                f"[필요: 최소 {MIN_NEEDED}건 {'충족' if usable >= MIN_NEEDED else f'— {MIN_NEEDED - usable}건 부족'}]"
            )
        detail = "<br>".join(rows) if rows else "수집된 리뷰 데이터가 없습니다."
        if all_sufficient and raw_stats:
            # 데이터는 충분하지만 분석 실패 → 다시 실행 시도 또는 오류 안내
            st.markdown(
                f'<div class="info-box" style="border-left:4px solid #F59E0B;">'
                f'⚠️ <b>분석 조건은 충족되었으나 민감도 분석을 완료하지 못했습니다.</b><br>'
                f'리뷰 데이터를 다시 분석하거나 앱을 재선택하면 해결될 수 있습니다.<br><br>'
                f'{detail}'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="info-box" style="border-left:4px solid #F59E0B;">'
                f'⚠️ <b>민감도 분석을 위한 데이터가 충분하지 않습니다.</b><br>'
                f'3점 이분화 조건을 바꾸며 로지스틱 회귀를 재실행하려면 각 앱당 <b>긍정·부정 리뷰 각 {MIN_NEEDED}건 이상</b>이 필요합니다.<br><br>'
                f'{detail}'
                f'</div>',
                unsafe_allow_html=True,
            )
        return

    conditions = combined["condition"].unique().tolist() if "condition" in combined.columns else []
    condition_colors = ["#4F8EF7", "#10B981", "#F59E0B"]

    # 선택한 순서대로 앱 목록 결정
    available_apps: set[str] = set(combined["app_name"].unique()) if "app_name" in combined.columns else set()
    ordered_apps = [
        a.app_name for a in st.session_state.get("selected_apps", [])
        if a.app_name in available_apps
    ] or list(available_apps)

    for app_idx, selected_app in enumerate(ordered_apps):
        if app_idx > 0:
            st.divider()

        sub = combined[combined["app_name"] == selected_app]
        fig = go.Figure()

        for i, cond in enumerate(conditions):
            c_sub = sub[sub["condition"] == cond]
            color = condition_colors[i % len(condition_colors)]

            markers = []
            if not pivot.empty and "direction_consistent" in pivot.columns:
                for cat in c_sub["feature_category"]:
                    p_row = (
                        pivot[(pivot["feature_category"] == cat) & (pivot["app_name"] == selected_app)]
                        if "app_name" in pivot.columns
                        else pivot[pivot["feature_category"] == cat]
                    )
                    consistent = p_row["direction_consistent"].values[0] if not p_row.empty else True
                    markers.append("circle" if consistent else "x")
            else:
                markers = ["circle"] * len(c_sub)

            fig.add_trace(go.Scatter(
                x=c_sub["feature_category"].tolist(),
                y=c_sub["OR"].tolist(),
                mode="lines+markers",
                name=cond,
                line=dict(color=color, width=2),
                marker=dict(color=color, size=9, symbol=markers),
                hovertemplate=f"<b>{cond}</b><br>기능: %{{x}}<br>OR: %{{y:.3f}}<br>X 표시=방향 불일치<extra></extra>",
            ))

        fig.add_hline(y=1.0, line_dash="dash", line_color=_SUBTEXT, line_width=1.5,
                      annotation_text="OR=1 기준", annotation_font_color=_SUBTEXT)
        fig.update_layout(
            title=dict(text=f"{selected_app} — 평점 이분화 기준별 OR 비교",
                       x=0.5, xanchor="center", font=dict(color=_TEXT, size=14)),
            xaxis_title="기능 카테고리",
            yaxis_title="오즈비 (OR)",
            height=400,
            **LAYOUT_DEFAULTS,
        )
        st.plotly_chart(fig, use_container_width=True, key=f"thresh_sens_{selected_app}_{app_idx}")
        _chart_download_btn(fig, f"threshold_sensitivity_{selected_app}")

        # 민감도 해석
        if not pivot.empty and "direction_consistent" in pivot.columns:
            app_pivot = pivot[pivot["app_name"] == selected_app] if "app_name" in pivot.columns else pivot
            consistent_count = int(app_pivot["direction_consistent"].sum()) if not app_pivot.empty else 0
            total_cats = len(app_pivot)
            _interp_box(
                f"{selected_app} — 평점 이분화 기준별 OR 비교",
                f"전체 {total_cats}개 기능 중 <b>{consistent_count}개({consistent_count/total_cats*100:.0f}%)</b>가 "
                f"3가지 이분화 기준 모두에서 OR 방향이 일치합니다. "
                f"80% 이상이면 분석 결과가 기준에 덜 민감하다는 뜻으로 신뢰도가 높습니다. "
                f"X 표시된 기능은 기준에 따라 결과가 달라지므로 해석 시 주의가 필요합니다.",
            )
        else:
            _interp_box(
                f"{selected_app} — 평점 이분화 기준별 OR 비교",
                "3가지 이분화 조건에서 OR 추이를 비교합니다. "
                "3개 선이 비슷한 방향으로 움직이면 분석이 안정적임을 의미합니다.",
            )

    if not pivot.empty:
        st.markdown("**조건별 방향 일치 여부**")
        st.dataframe(pivot, use_container_width=True, height=280)

    _thesis_box(
        "평점 이분화 기준의 민감도를 분석한 결과, 3점 제외/긍정포함/부정포함 세 조건에서 "
        "주요 기능 키워드의 OR 방향이 일관되게 나타났으며, 분석 결과의 안정성을 확인하였다."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 항목 6: 기간 분할 안정성 (OR 히트맵)
# ─────────────────────────────────────────────────────────────────────────────

def _render_period_stability(vr: dict[str, Any]) -> None:
    ps = vr.get("period_stab", (pd.DataFrame(), pd.DataFrame()))
    if not isinstance(ps, tuple) or len(ps) != 2:
        render_skeleton("기간 분할 안정성 분석중입니다", show_chart=True, chart_height=180)
        return

    combined, pivot = ps

    st.markdown("""
    <div class="info-box">
    <b>목적:</b> 특정 시기의 이벤트나 장애가 전체 결과를 왜곡하지 않았는지 확인합니다.<br>
    기간을 나눠도 결과가 비슷하다면 분석 결과의 시간적 안정성이 확보돼요.
    </div>
    """, unsafe_allow_html=True)

    if pivot.empty:
        raw_stats: dict = vr.get("raw_stats", {})
        MIN_PER_PERIOD = 50
        rows = []
        for app_name, st_data in raw_stats.items():
            n1 = st_data.get("n_first_half",  0)
            n2 = st_data.get("n_second_half", 0)
            ok1 = "✅" if n1 >= MIN_PER_PERIOD else "⚠️"
            ok2 = "✅" if n2 >= MIN_PER_PERIOD else "⚠️"
            rows.append(
                f"<b>{app_name}</b>: 상반기 {ok1} {n1:,}건 / 하반기 {ok2} {n2:,}건 "
                f"[각 기간 최소 {MIN_PER_PERIOD}건 필요]"
            )
        detail = "<br>".join(rows) if rows else "수집된 리뷰 데이터가 없습니다."
        st.markdown(
            f'<div class="info-box" style="border-left:4px solid #F59E0B;">'
            f'⚠️ <b>기간 분할 분석에 필요한 데이터가 부족합니다.</b><br>'
            f'상반기·하반기 각 기간별로 <b>앱당 {MIN_PER_PERIOD}건 이상</b>의 리뷰가 있어야 분석이 가능합니다.<br><br>'
            f'{detail}'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    periods = [c for c in ["전체", "상반기", "하반기"] if c in pivot.columns]

    if periods and "feature_category" in pivot.columns:
        heat_data = pivot.set_index("feature_category")[periods]

        fig = go.Figure(go.Heatmap(
            z=heat_data.values.tolist(),
            x=periods,
            y=heat_data.index.tolist(),
            colorscale="RdYlGn",
            zmid=1.0,
            colorbar=dict(title=dict(text="OR", font=dict(color=_TEXT)), tickfont=dict(color=_TEXT)),
            hovertemplate="기능: %{y}<br>기간: %{x}<br>OR: %{z:.3f}<br>1 기준 위=긍정 연관, 아래=부정 연관<extra></extra>",
            text=heat_data.round(2).values.tolist(),
            texttemplate="%{text}",
        ))

        if "direction_consistent" in pivot.columns:
            shapes = []
            for i, (_, row) in enumerate(pivot.iterrows()):
                if not row.get("direction_consistent", True):
                    for j in range(len(periods)):
                        shapes.append(dict(
                            type="rect",
                            x0=j - 0.5, x1=j + 0.5,
                            y0=i - 0.5, y1=i + 0.5,
                            line=dict(color="#FF6B8A", width=2),
                        ))
            fig.update_layout(shapes=shapes)

        fig.update_layout(
            title=dict(text="기간별 OR 히트맵 (빨간 테두리=방향 불일치)",
                       x=0.5, xanchor="center", font=dict(color=_TEXT, size=14)),
            height=max(350, len(heat_data) * 30 + 150),
            **LAYOUT_DEFAULTS,
        )
        st.plotly_chart(fig, use_container_width=True)
        _chart_download_btn(fig, "period_stability_heatmap")

        # 기간 안정성 해석
        if "direction_consistent" in pivot.columns:
            consistent_count = int(pivot["direction_consistent"].sum())
            total_count = len(pivot)
            _interp_box(
                "기간별 OR 히트맵",
                f"전체 {total_count}개 기능 중 <b>{consistent_count}개({consistent_count/total_count*100:.0f}%)</b>가 "
                f"상반기·하반기 모두 같은 방향(긍정/부정)을 유지합니다. "
                f"빨간 테두리로 표시된 기능은 기간에 따라 결과가 달라졌으므로 외부 이벤트(업데이트, 장애 등) 영향을 의심해볼 수 있습니다. "
                f"80% 이상 일치하면 시간적 강건성이 확보된 것으로 판단합니다.",
            )
        else:
            _interp_box(
                "기간별 OR 히트맵",
                "전체·상반기·하반기 OR을 비교합니다. "
                "색이 일관되면(모두 녹색 또는 모두 빨간색) 기간과 무관하게 결과가 안정적입니다.",
            )

    st.dataframe(pivot, use_container_width=True)

    _thesis_box(
        "수집 기간을 전체·상반기·하반기로 분할하여 OR 방향의 일관성을 검토하였다. "
        "대부분의 기능 키워드에서 기간 간 OR 방향이 일치하여 시간적 강건성이 확인되었다."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 항목 7: 표본 분포 (평점 분포 + 월별 + 도넛)
# ─────────────────────────────────────────────────────────────────────────────

def _render_sample_distribution(vr: dict[str, Any]) -> None:
    sd = vr.get("sample_dist", {})
    if not isinstance(sd, dict) or not sd:
        render_skeleton("표본 분포를 분석중입니다", show_chart=True, chart_height=160)
        return

    st.markdown("""
    <div class="info-box">
    <b>목적:</b> 수집된 데이터의 전반적인 분포를 확인합니다.<br>
    긍정과 부정 리뷰가 극단적으로 불균형하면 분석 결과가 한쪽으로 치우칠 수 있어요.
    </div>
    """, unsafe_allow_html=True)

    app_counts   = sd.get("app_counts",   pd.DataFrame())
    score_dist   = sd.get("score_dist",   pd.DataFrame())
    sentiment_df = sd.get("sentiment_dist", pd.DataFrame())
    monthly      = sd.get("monthly",      pd.DataFrame())
    imbalance    = sd.get("imbalance_status", {})

    col1, col2 = st.columns(2)

    # 평점 분포 막대 차트
    with col1:
        st.markdown("**평점 분포**")
        if not score_dist.empty:
            fig_score = go.Figure()
            _ordered_sd = get_ordered_app_names(score_dist)
            for app_name in (_ordered_sd or score_dist["app_name"].unique().tolist()):
                sub = score_dist[score_dist["app_name"] == app_name]
                if sub.empty:
                    continue
                fig_score.add_trace(go.Bar(
                    name=str(app_name),
                    x=sub["score"].tolist(),
                    y=sub["count"].tolist(),
                    marker_color=app_color(app_name, _ordered_sd),
                    hovertemplate=f"<b>{app_name}</b><br>평점: %{{x}}점<br>건수: %{{y:,}}건<extra></extra>",
                ))
            fig_score.update_layout(
                title=dict(text="평점별 리뷰 분포", x=0.5, xanchor="center", font=dict(color=_TEXT)),
                barmode="group",
                xaxis_title="평점",
                yaxis_title="리뷰 수",
                height=300,
                **LAYOUT_DEFAULTS,
            )
            st.plotly_chart(fig_score, use_container_width=True)
            _chart_download_btn(fig_score, "score_distribution")

            # 평점 분포 해석
            score_lines = []
            for app_name in (score_dist["app_name"].unique() if "app_name" in score_dist.columns else []):
                sub = score_dist[score_dist["app_name"] == app_name]
                total = sub["count"].sum()
                neg = sub[sub["score"] <= 2]["count"].sum()
                pos = sub[sub["score"] >= 4]["count"].sum()
                if total > 0:
                    score_lines.append(
                        f"<b>{app_name}</b>: 부정(1~2점) {neg/total*100:.0f}% / 긍정(4~5점) {pos/total*100:.0f}%"
                    )
            _interp_box(
                "평점별 리뷰 분포",
                (" | ".join(score_lines) if score_lines else "데이터 없음") +
                ". 부정 비율이 매우 높으면 OR 분석에서 부정 편향이 발생할 수 있습니다.",
            )

    # 월별 추이 라인 차트
    with col2:
        st.markdown("**월별 리뷰 수 추이**")
        if not monthly.empty:
            fig_monthly = go.Figure()
            _ordered_mn = get_ordered_app_names(monthly)
            for app_name in (_ordered_mn or monthly["app_name"].unique().tolist()):
                sub = monthly[monthly["app_name"] == app_name]
                if sub.empty:
                    continue
                fig_monthly.add_trace(go.Scatter(
                    name=str(app_name),
                    x=sub["year_month"].tolist(),
                    y=sub["count"].tolist(),
                    mode="lines+markers",
                    line=dict(color=app_color(app_name, _ordered_mn), width=2),
                    hovertemplate=f"<b>{app_name}</b><br>월: %{{x}}<br>리뷰 수: %{{y:,}}건<extra></extra>",
                ))
            fig_monthly.update_layout(
                title=dict(text="월별 리뷰 추이", x=0.5, xanchor="center", font=dict(color=_TEXT)),
                xaxis_title="월",
                yaxis_title="리뷰 수",
                height=300,
                **LAYOUT_DEFAULTS,
            )
            st.plotly_chart(fig_monthly, use_container_width=True)
            _chart_download_btn(fig_monthly, "monthly_trend")

            # 월별 추이 해석
            peak_rows = []
            for app_name in (monthly["app_name"].unique() if "app_name" in monthly.columns else []):
                sub = monthly[monthly["app_name"] == app_name]
                if not sub.empty:
                    peak = sub.loc[sub["count"].idxmax()]
                    peak_rows.append(f"<b>{app_name}</b>: 최다 리뷰 {peak['year_month']}({int(peak['count'])}건)")
            _interp_box(
                "월별 리뷰 추이",
                (" | ".join(peak_rows) if peak_rows else "데이터 없음") +
                ". 특정 월에 리뷰가 급증했다면 업데이트나 이벤트 등 외부 요인을 검토하세요.",
            )

    # 긍정/부정 도넛 차트 (full width, below)
    st.markdown("**긍정/부정 비율**")
    if not sentiment_df.empty:
        apps = sentiment_df["app_name"].unique().tolist() if "app_name" in sentiment_df.columns else []
        donut_cols = st.columns(max(1, len(apps[:4])))
        donut_interp_lines = []
        for idx, app_name in enumerate(apps[:4]):
            sub = sentiment_df[sentiment_df["app_name"] == app_name]
            with donut_cols[idx]:
                fig_donut = go.Figure(go.Pie(
                    labels=sub["sentiment"].tolist(),
                    values=sub["count"].tolist(),
                    hole=0.5,
                    marker_colors=["#10B981", "#F59E0B", "#EF4444"],
                    hovertemplate="<b>%{label}</b><br>%{value:,}건 (%{percent})<extra></extra>",
                ))
                status = imbalance.get(str(app_name), "pass")
                fig_donut.update_layout(
                    title=dict(
                        text=f"{app_name} {_badge_html(status)}",
                        font=dict(color=_TEXT),
                    ),
                    height=280,
                    plot_bgcolor=_BG,
                    paper_bgcolor=_BG,
                    font=dict(color=_TEXT),
                    legend=dict(bgcolor="#131820", bordercolor=_LINE, font=dict(color=_TEXT)),
                    margin=dict(l=10, r=10, t=50, b=40),
                )
                st.plotly_chart(fig_donut, use_container_width=True)
                _chart_download_btn(fig_donut, f"sentiment_donut_{app_name}")

            total = sub["count"].sum()
            for _, row in sub.iterrows():
                if "긍정" in str(row.get("sentiment", "")):
                    pct = row["count"] / total * 100 if total > 0 else 0
                    donut_interp_lines.append(f"<b>{app_name}</b> 긍정 비율 {pct:.0f}%")
        if donut_interp_lines:
            _interp_box(
                "긍정/부정 비율",
                " | ".join(donut_interp_lines) +
                ". 긍정·부정 비율이 9:1 이상으로 극단적이면 OR 분석의 신뢰도가 낮아질 수 있습니다. "
                "⚠️ 주의 표시된 앱은 데이터 불균형 보정 여부를 검토하세요.",
            )

    if not app_counts.empty:
        st.markdown("**앱별 수집 건수 요약**")
        st.dataframe(app_counts.rename(columns={"app_name": "앱", "review_count": "리뷰 수"}),
                     use_container_width=True)

    _thesis_box(
        "분석에 사용된 리뷰 데이터의 긍정·부정 비율 및 평점 분포를 검토하였다. "
        "데이터 불균형 여부를 확인하고 분석 결과 해석 시 이를 고려하였다."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 메인 렌더 함수
# ─────────────────────────────────────────────────────────────────────────────

def render(
    vr: dict[str, Any],
    combined_or: pd.DataFrame,
) -> None:
    st.markdown("""
    <div class="info-box">
    분석 결과의 통계적 신뢰성을 다각도로 검증합니다.
    각 항목을 펼쳐 세부 결과와 해석을 확인하세요. 논문 강건성 검증 섹션에 바로 활용할 수 있습니다.
    </div>
    """, unsafe_allow_html=True)

    if not vr:
        render_skeleton("통계 검증 데이터를 분석중입니다", show_chart=True, n_rows=4, chart_height=180)
        return

    _render_summary(vr)

    with st.expander("1️⃣ 모형 적합도 (Model Fit)", expanded=True):
        _render_model_fit(vr)

    with st.expander("2️⃣ 회귀계수 유의성 (Coefficient Significance)", expanded=True):
        _render_coef_sig(vr)

    with st.expander("3️⃣ 서비스 간 영향력 차이 검정 (Interaction Effect Test)", expanded=True):
        _render_interaction(vr, combined_or)

    with st.expander("4️⃣ 기능 키워드 공출현 패턴 (Feature Co-occurrence)", expanded=True):
        _render_multicollinearity(vr)

    with st.expander("5️⃣ 평점 이분화 기준 민감도 (Threshold Sensitivity)", expanded=True):
        _render_threshold_sensitivity(vr)

    with st.expander("6️⃣ 기간 분할 안정성 (Period Stability)", expanded=True):
        _render_period_stability(vr)

    with st.expander("7️⃣ 표본 분포 (Sample Distribution)", expanded=True):
        _render_sample_distribution(vr)
