"""
Shared visualization utilities
- Dark theme constants
- App color mapping (selection-order-based)
- Unified insight box renderer
- Plotly layout helpers
"""
from __future__ import annotations

import streamlit as st
from config.settings import APP_COLORS

# ── Dark theme constants ───────────────────────────────────────────────────────
BG      = "#0E1116"
GRID    = "#1E2630"
LINE    = "#2D3748"
TEXT    = "#E2E8F0"
SUBTEXT = "#94A3B8"

_DARK_BASE = dict(plot_bgcolor=BG, paper_bgcolor=BG, font=dict(color=TEXT))

# ── App color → square emoji ──────────────────────────────────────────────────
APP_COLOR_EMOJIS: dict[str, str] = {
    "#4F8EF7": "🟦",
    "#F7844F": "🟧",
    "#4FD6A5": "🟩",
    "#C84FF7": "🟪",
    "#F7D84F": "🟨",
}


def apply_dark_theme(fig, centered_legend: bool = False):
    """Apply dark theme + optionally center legend. Returns fig."""
    fig.update_layout(**_DARK_BASE)
    fig.update_xaxes(
        gridcolor=GRID, linecolor=LINE, zerolinecolor=LINE,
        tickfont=dict(color=TEXT),
    )
    fig.update_yaxes(
        gridcolor=GRID, linecolor=LINE, zerolinecolor=LINE,
        tickfont=dict(color=TEXT),
    )
    if centered_legend:
        fig.update_layout(legend=dict(
            bgcolor="#131820", bordercolor=LINE, font=dict(color=TEXT),
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="center", x=0.5,
        ))
    else:
        fig.update_layout(legend=dict(
            bgcolor="#131820", bordercolor=LINE, font=dict(color=TEXT),
        ))
    return fig


def centered_title(text: str, size: int = 15) -> dict:
    """Return a Plotly title dict with center alignment."""
    return dict(text=text, x=0.5, xanchor="center", font=dict(color=TEXT, size=size))


# ── App order & color ──────────────────────────────────────────────────────────

def get_ordered_app_names(raw_df) -> list[str]:
    """
    Return app names in user selection order (session_state.selected_apps),
    filtered to names that actually exist in raw_df.
    Falls back to sorted order for any name not in session state.
    """
    in_data: set[str] = set(raw_df["app_name"].unique()) if not raw_df.empty else set()
    selected = st.session_state.get("selected_apps", [])
    seen: set[str] = set()
    order: list[str] = []
    for a in selected:
        if a.app_name not in seen and a.app_name in in_data:
            seen.add(a.app_name)
            order.append(a.app_name)
    for name in sorted(in_data):
        if name not in seen:
            order.append(name)
    return order


def app_color(app_name: str, ordered_names: list[str]) -> str:
    """Return the consistent hex color for an app, based on its index in ordered_names."""
    try:
        idx = ordered_names.index(app_name)
    except ValueError:
        idx = 0
    return APP_COLORS[idx % len(APP_COLORS)]


def app_emoji(app_name: str, ordered_names: list[str]) -> str:
    """Return the square color emoji for an app."""
    color = app_color(app_name, ordered_names)
    return APP_COLOR_EMOJIS.get(color, "⬜")


# ── Insight box renderer ───────────────────────────────────────────────────────

def render_insight_box(
    title: str,
    purpose: str,
    effect: str,
    app_items: list[tuple[str, str, str]],
    summary: str | None = None,
) -> None:
    """
    Render a unified insight box.

    title       : chart/section title (shown as '{title} Insight')
    purpose     : one-line description of what the analysis measures
    effect      : one-line plain-language benefit / usage tip
    app_items   : list of (app_name, hex_color, interpretation_text)
                  Each item becomes one bullet line.
    summary     : optional overall conclusion shown at the bottom as '==> 종합해석'
    """
    items_html = ""
    for app_name, color, text in app_items:
        emoji = APP_COLOR_EMOJIS.get(color, "⬜")
        items_html += (
            f'<div style="margin:4px 0;line-height:1.7;">'
            f'<b style="color:{color};">[ {emoji} {app_name} ]</b> : '
            f'<span style="color:#CBD5E1;">{text}</span>'
            f'</div>'
        )

    summary_html = ""
    if summary:
        summary_html = (
            f'<div style="border-top:1px solid #2D3748;padding-top:0.5rem;'
            f'margin-top:0.5rem;font-size:0.83rem;">'
            f'<span style="color:#93C5FD;font-weight:700;">=&gt; 종합해석 : </span>'
            f'<span style="color:#CBD5E1;">{summary}</span>'
            f'</div>'
        )

    st.markdown(
        f'<div style="background:#131820;border-left:4px solid #4F8EF7;border-radius:6px;'
        f'padding:0.9rem 1rem;margin-top:0.4rem;margin-bottom:1.2rem;">'
        f'<div style="font-size:0.95rem;font-weight:700;color:#93C5FD;margin-bottom:0.45rem;">'
        f'{title} Insight</div>'
        f'<div style="font-size:0.78rem;color:#64748B;margin-bottom:0.1rem;">'
        f'※ 해당 분석의 목적 : {purpose}</div>'
        f'<div style="font-size:0.78rem;color:#64748B;margin-bottom:0.55rem;">'
        f'※ 해당 분석의 효과 : {effect}</div>'
        f'<div style="border-top:1px solid #1E2630;padding-top:0.45rem;font-size:0.83rem;">'
        f'{items_html}</div>'
        f'{summary_html}'
        f'</div>',
        unsafe_allow_html=True,
    )
