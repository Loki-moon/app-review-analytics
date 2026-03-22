"""
Shared visualization utilities
- Dark theme constants
- App color mapping (selection-order-based, icon-extracted)
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

# ── App color → square emoji (static fallback palette) ───────────────────────
APP_COLOR_EMOJIS: dict[str, str] = {
    "#4F8EF7": "🟦",
    "#F7844F": "🟧",
    "#4FD6A5": "🟩",
    "#C84FF7": "🟪",
    "#F7D84F": "🟨",
}
_INDEX_EMOJIS = ["🟦", "🟧", "🟩", "🟪", "🟨"]


# ── Icon color extraction ─────────────────────────────────────────────────────

def _extract_dominant_color(icon_url: str) -> str | None:
    """
    Download an app icon and return the most visually dominant brand color as hex.

    Algorithm:
    1. Fetch & resize to 80×80 for speed
    2. Composite onto white background (handles transparency)
    3. Quantize to 10 colors
    4. Pick the color with highest (saturation × pixel_count), excluding
       near-white (v>0.9, s<0.15) and near-black (v<0.12) regions
    """
    try:
        import colorsys
        import io
        import requests
        from PIL import Image

        resp = requests.get(icon_url, timeout=6)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        img = img.resize((80, 80), Image.LANCZOS)

        # Composite onto white background
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        rgb_img = bg.convert("RGB")

        quantized = rgb_img.quantize(colors=10, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette()          # flattened [R,G,B, R,G,B, ...]

        from collections import Counter
        color_counts: Counter = Counter(quantized.getdata())

        def _score(idx_count: tuple[int, int]) -> float:
            idx, count = idx_count
            r = palette[idx * 3]
            g = palette[idx * 3 + 1]
            b = palette[idx * 3 + 2]
            _, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if v > 0.90 and s < 0.15:   # near-white → skip
                return 0.0
            if v < 0.12:                # near-black → skip
                return 0.0
            return s * count

        best_idx, _ = max(color_counts.items(), key=_score)
        r = palette[best_idx * 3]
        g = palette[best_idx * 3 + 1]
        b = palette[best_idx * 3 + 2]

        # Reject if the "best" color is still near-white or near-black
        _, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if (v > 0.90 and s < 0.15) or v < 0.12:
            return None

        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_icon_color(icon_url: str) -> str | None:
    """Cached wrapper around _extract_dominant_color."""
    return _extract_dominant_color(icon_url)


def get_icon_color(icon_url: str, fallback: str) -> str:
    """Return the extracted dominant icon color, or fallback hex if unavailable."""
    if icon_url:
        color = _fetch_icon_color(icon_url)
        if color:
            return color
    return fallback


def get_app_icon_url(app_name: str) -> str:
    """Return the icon_url for an app from session_state.selected_apps."""
    for app in st.session_state.get("selected_apps", []):
        if app.app_name == app_name and getattr(app, "icon_url", None):
            return app.icon_url
    return ""


def app_icon_html(app_name: str, size: int = 16, color: str = "#94A3B8") -> str:
    """
    Return an HTML snippet showing the app icon image.
    Falls back to a colored '●' dot if no icon is available.
    """
    icon_url = get_app_icon_url(app_name)
    if icon_url:
        return (
            f'<img src="{icon_url}" width="{size}" height="{size}" '
            f'style="border-radius:{size//4}px;object-fit:cover;'
            f'vertical-align:middle;margin-right:4px;" />'
        )
    return f'<span style="color:{color};font-size:{size}px;vertical-align:middle;margin-right:2px;">●</span>'


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
    """
    Return the brand color for an app.
    Priority: extracted icon color → fallback palette by selection index.
    """
    selected = st.session_state.get("selected_apps", [])
    for app in selected:
        if app.app_name == app_name and getattr(app, "icon_url", None):
            color = _fetch_icon_color(app.icon_url)
            if color:
                return color
            break
    try:
        idx = ordered_names.index(app_name)
    except ValueError:
        idx = 0
    return APP_COLORS[idx % len(APP_COLORS)]


def app_emoji(app_name: str, ordered_names: list[str]) -> str:
    """Return the square color emoji for an app (index-based, consistent regardless of icon color)."""
    try:
        idx = ordered_names.index(app_name)
    except ValueError:
        idx = 0
    return _INDEX_EMOJIS[idx % len(_INDEX_EMOJIS)]


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
        icon = app_icon_html(app_name, size=16, color=color)
        items_html += (
            f'<div style="margin:4px 0;line-height:1.7;display:flex;align-items:center;gap:0;">'
            f'{icon}'
            f'<b style="color:{color};">{app_name}</b>'
            f'<span style="color:#CBD5E1;"> : {text}</span>'
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


_SHIMMER_BG = (
    "linear-gradient(90deg,"
    "rgba(255,255,255,0.025) 0%,"
    "rgba(255,255,255,0.08) 40%,"
    "rgba(255,255,255,0.025) 70%)"
)
_SHIMMER_STYLE = (
    f"background:{_SHIMMER_BG};"
    "background-size:200% 100%;"
    "animation:skeleton-shimmer 1.7s linear infinite;"
    "border-radius:5px;"
)


def render_skeleton(
    message: str = "데이터를 분석중입니다",
    show_chart: bool = True,
    n_rows: int = 4,
    chart_height: int = 200,
) -> None:
    """Shimmer skeleton placeholder shown while section data is being computed."""
    # --- spinner ---
    spinner = (
        '<span style="display:inline-block;width:13px;height:13px;'
        'border:2px solid rgba(148,163,184,0.15);border-top-color:#7BA7F5;'
        'border-radius:50%;animation:spin 0.8s linear infinite;'
        'vertical-align:middle;margin-right:6px;flex-shrink:0;"></span>'
    )
    # --- label row ---
    label = (
        f'<div style="font-size:0.77rem;color:#64748B;letter-spacing:0.05em;'
        f'font-weight:600;text-transform:uppercase;display:flex;align-items:center;'
        f'gap:0.45rem;margin-bottom:1.1rem;">'
        f'{spinner}{message}'
        f'<span style="animation:skeleton-pulse 1.3s ease infinite;color:#475569;"> ···</span>'
        f'</div>'
    )
    # --- fake title bars ---
    def _bar(width: str, height: str = "9px", mb: str = "8px") -> str:
        return (
            f'<div style="height:{height};width:{width};{_SHIMMER_STYLE}'
            f'margin-bottom:{mb};"></div>'
        )

    bar_html = _bar("42%") + _bar("61%", mb="18px")

    # --- fake chart block ---
    chart_html = (
        f'<div style="width:100%;height:{chart_height}px;{_SHIMMER_STYLE}'
        f'border-radius:8px;margin-bottom:14px;"></div>'
        if show_chart else ""
    )

    # --- fake table rows ---
    col_flex_sets = [[3, 1, 1, 1, 1], [2, 1, 2, 1, 1], [3, 1, 1, 2, 1], [2, 2, 1, 1, 1]]
    rows_html = ""
    for i in range(min(n_rows, len(col_flex_sets))):
        cells = "".join(
            f'<div style="flex:{f};height:26px;{_SHIMMER_STYLE}border-radius:4px;"></div>'
            for f in col_flex_sets[i % len(col_flex_sets)]
        )
        rows_html += f'<div style="display:flex;gap:8px;margin-bottom:7px;">{cells}</div>'

    st.markdown(
        f'<div style="padding:1.4rem 1.2rem 1rem;border-radius:10px;'
        f'background:rgba(255,255,255,0.015);border:1px solid rgba(255,255,255,0.06);'
        f'margin:0.4rem 0 1rem;">'
        f'{label}{bar_html}{chart_html}{rows_html}'
        f'</div>',
        unsafe_allow_html=True,
    )
