"""
CSS 디자인 시스템 — 다크모드 스타일
"""
from __future__ import annotations


def get_css() -> str:
    bg_page = "#212121"
    bg_sidebar = "#171717"
    bg_card = "#2A2A2A"
    bg_card_soft = "#242424"
    text_main = "#ECECEC"
    text_sub = "#A3A3A3"
    border = "#3A3A3A"
    header_grad = "linear-gradient(180deg, #1F1F1F 0%, #1F1F1F 100%)"
    input_bg = "#2A2A2A"
    hover_item = "#303030"
    shadow = "0 1px 2px rgba(0,0,0,0.25)"

    primary = "#7C7C7C"
    primary_dark = "#666666"
    positive = "#22C55E"
    negative = "#FB7185"
    neutral = "#FBBF24"
    success = "#10B981"
    warning = "#F59E0B"

    return f"""
<style>
:root {{
  --bg-page: {bg_page};
  --bg-sidebar: {bg_sidebar};
  --bg-card: {bg_card};
  --bg-card-soft: {bg_card_soft};
  --text-main: {text_main};
  --text-sub: {text_sub};
  --border: {border};
  --primary: {primary};
  --primary-dark: {primary_dark};
  --positive: {positive};
  --negative: {negative};
  --neutral: {neutral};
  --success: {success};
  --warning: {warning};
  --shadow: {shadow};
  --radius: 18px;
  --radius-sm: 10px;
  --font: 'Pretendard','Apple SD Gothic Neo','Noto Sans KR',sans-serif;
}}

/* =========================
   GLOBAL BACKGROUND
========================= */
html,
body {{
  background: var(--bg-page) !important;
  color: var(--text-main) !important;
  font-family: var(--font) !important;
}}

[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section[data-testid="stMain"],
.main {{
  background: var(--bg-page) !important;
  color: var(--text-main) !important;
  font-family: var(--font) !important;
}}

[data-testid="stMainBlockContainer"],
.main .block-container {{
  padding-top: 20px !important;
  padding-bottom: 80px !important;
  padding-left: 1.25rem !important;
  padding-right: 1.25rem !important;
  max-width: 1440px !important;
}}

[data-testid="stVerticalBlock"],
[data-testid="element-container"],
.element-container {{
  background: transparent !important;
}}

.stMarkdown,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] * {{
  color: var(--text-main) !important;
  background: transparent !important;
}}

h1, h2, h3, h4, h5, h6,
p, span, label, small, li, div {{
  color: var(--text-main);
}}

h3 {{
  margin: 0.55rem 0 0.35rem 0 !important;
  font-size: 1.12rem !important;
}}

h4 {{
  margin: 0.42rem 0 0.24rem 0 !important;
  font-size: 0.96rem !important;
}}

hr {{
  margin: 0.5rem 0 !important;
  border-color: var(--border) !important;
}}

/* =========================
   HEADER
========================= */
[data-testid="stHeader"] {{
  background: #1F1F1F !important;
  height: 68px !important;
  min-height: 68px !important;
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  z-index: 9999 !important;
  display: flex !important;
  align-items: center !important;
  padding: 0 1.5rem !important;
  box-shadow: none !important;
  border-bottom: 1px solid #2F2F2F !important;
}}

[data-testid="stHeader"] * {{
  color: #F8FAFC !important;
}}

[data-testid="stHeader"] button {{
  background: #2A2A2A !important;
  border: 1px solid #3A3A3A !important;
  color: #F1F1F1 !important;
  border-radius: 8px !important;
  backdrop-filter: none !important;
}}

[data-testid="stHeader"] button:hover {{
  background: #323232 !important;
}}

/* =========================
   HEADER APP CHIPS
========================= */
.header-app-chips {{
  position: fixed;
  top: 0;
  left: 220px;
  right: 160px;
  height: 68px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 10001;
  overflow: hidden;
  padding: 0 0.5rem;
}}

.app-slot-pill {{
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: #2A2A2A;
  border: 1px solid #3A3A3A;
  border-radius: 999px;
  padding: 7px 14px;
  font-size: 0.82rem;
  font-weight: 500;
  color: #EAEAEA;
  white-space: nowrap;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: default;
  backdrop-filter: none;
}}

.app-slot-pill.filled {{
  background: #303030;
  border-color: #444444;
}}

.vs-chip {{
  font-size: 0.78rem;
  font-weight: 700;
  color: #B5B5B5;
  flex-shrink: 0;
}}

.header-add-btn {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #2A2A2A;
  border: 1px solid #3A3A3A;
  color: #FFFFFF;
  font-size: 1rem;
  font-weight: 700;
  flex-shrink: 0;
  cursor: pointer;
}}

/* =========================
   SIDEBAR
========================= */

[data-testid="stHeader"] {{
  border-bottom: 1px solid #2F2F2F !important;
  box-shadow: none !important;
}}

[data-testid="stSidebar"] > div {{
  display: flex;
  flex-direction: column;
  gap: 6px;
}}

[data-testid="stSidebar"] .element-container {{
  margin: 0 !important;
}}

[data-testid="stSidebar"] {{
  background: #171717 !important;
  width: 220px !important;
  min-width: 220px !important;
  border-right: 1px solid #2A2A2A !important;
  padding-top: 12px !important;
}}

[data-testid="stSidebar"] > div {{
  background: transparent !important;
}}

[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {{
  color: {text_main} !important;
  font-size: 0.9rem !important;
}}

.nav-item {{
  display: block;
  padding: 0.6rem 1rem;
  border-radius: 12px;
  cursor: pointer;
  font-size: 0.88rem;
  font-weight: 600;
  color: {text_sub};
  text-decoration: none;
  margin-bottom: 4px;
  border: 1px solid transparent;
  background: transparent;
  width: 100%;
  text-align: left;
}}

.nav-item:hover {{
  background: #242424;
  color: #F1F1F1;
  border-color: transparent;
}}

.nav-item.active {{
  background: #3430B8;
  border: 1px solid #2B2796;
  color: #FFFFFF !important;
  box-shadow: 0 10px 24px rgba(0,0,0,0.35);
}}

.nav-sub {{
  padding-left: 1.5rem;
  font-size: 0.82rem;
}}

.nav-section-label {{
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748B;
  padding: 0.9rem 1rem 0.3rem;
}}

.nav-sub-item {{
  display: flex;
  align-items: center;
  padding: 0.28rem 0.75rem 0.28rem 1.6rem;
  font-size: 0.8rem;
  color: #7C8AA0;
  border-radius: 5px;
  margin-bottom: 1px;
  user-select: none;
}}

/* 헤더 pill X 버튼 */
.pill-remove {{
  font-size: 0.72rem;
  color: rgba(255,255,255,0.45);
  cursor: pointer;
  margin-left: 5px;
  flex-shrink: 0;
  line-height: 1;
  padding: 0 2px;
  transition: color 0.15s;
}}
.pill-remove:hover {{
  color: #FB7185;
}}

/* 사이드바 서브 메뉴 버튼 — nav-sub-item 스타일과 통일 */
[data-testid="stSidebar"] .stButton > button[kind="secondary"] {{
  font-size: 0.8rem !important;
  color: #7C8AA0 !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  text-align: left !important;
  padding: 0.3rem 0.75rem 0.3rem 1.4rem !important;
  min-height: unset !important;
  height: auto !important;
}}
[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {{
  background: #242424 !important;
  color: #EAEAEA !important;
  border: none !important;
}}

/* =========================
   TOP FILTER BAR
========================= */
.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type {{
  background: rgba(17,24,39,0.9) !important;
  border: 1px solid rgba(148,163,184,0.14) !important;
  border-radius: 22px !important;
  padding: 12px 18px !important;
  margin: -0.3rem 0 1.1rem 0 !important;
  box-shadow: 0 12px 32px rgba(0,0,0,0.26) !important;
  align-items: center !important;
  backdrop-filter: blur(12px) !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="column"]:first-child {{
  background: rgba(30,41,59,0.88) !important;
  border: 1px solid rgba(148,163,184,0.12) !important;
  border-radius: 18px !important;
  padding: 10px 12px !important;
  min-height: 78px !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="column"]:last-child {{
  min-height: 78px !important;
  display: flex !important;
  align-items: center !important;
  padding-left: 10px !important;
}}

.top-filter-dates-meta {{
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;
  padding-left: 8px;
}}

.top-filter-dates-meta .meta-item {{
  font-size: 12px;
  color: #94A3B8;
  font-weight: 700;
  line-height: 1;
}}

.top-filter-dates-meta .meta-sep {{
  width: 72px;
}}

.top-filter-date-sep {{
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94A3B8;
  font-size: 18px;
  font-weight: 700;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type [data-testid="stHorizontalBlock"] {{
  align-items: center !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stDateInput"] {{
  margin-bottom: 0 !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stDateInput"] > div {{
  background: rgba(15,23,42,0.95) !important;
  border: 1px solid rgba(148,163,184,0.14) !important;
  border-radius: 12px !important;
  min-height: 44px !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stDateInput"] input {{
  font-size: 15px !important;
  font-weight: 600 !important;
  color: #E2E8F0 !important;
  background: transparent !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stDateInput"] label {{
  display: none !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stButton"] {{
  margin-bottom: 0 !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stButton"] > button {{
  min-height: 44px !important;
  height: 44px !important;
  border-radius: 12px !important;
  border: 1px solid #3A3A3A !important;
  background: #2A2A2A !important;
  color: #D4D4D4 !important;
  font-size: 14px !important;
  font-weight: 500 !important;
  box-shadow: none !important;
  padding: 0 8px !important;
  white-space: nowrap !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stButton"] > button[kind="primary"]:hover,
.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stButton"] > button[kind="primary"]:focus,
.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stButton"] > button[kind="primary"]:active {{
  background: #7B6DFF !important;
  border: 1px solid #8A7DFF !important;
  color: #FFFFFF !important;
  box-shadow: 0 0 0 1px rgba(138,125,255,0.2), 0 10px 24px rgba(123,109,255,0.32) !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stButton"] > button[kind="secondary"] {{
  background: rgba(15,23,42,0.92) !important;
  border: 1px solid rgba(148,163,184,0.14) !important;
  color: #CBD5E1 !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stToggle"] {{
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 48px;
  margin-bottom: 0 !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stToggle"] label {{
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  white-space: nowrap !important;
  font-size: 14px !important;
  color: #CBD5E1 !important;
  font-weight: 500 !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stToggle"] label p {{
  margin: 0 !important;
  line-height: 1.2 !important;
  font-size: 14px !important;
  color: #CBD5E1 !important;
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stToggle"] [data-baseweb="switch"] {{
  transform: scale(0.92);
}}

.top-filter-root > div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stToggle"] input:checked + div {{
  background-color: #22C55E !important;
}}

/* =========================
   INPUTS
========================= */
[data-testid="stTextInput"] > div > div,
[data-testid="stDateInput"] > div > div,
[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div,
textarea {{
  background: #2A2A2A !important;
  border: 1px solid #3A3A3A !important;
  border-radius: 12px !important;
  box-shadow: none !important;
}}

[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stSelectbox"] input,
textarea {{
  color: {text_main} !important;
  background: transparent !important;
}}

[data-testid="stTextInput"] input::placeholder,
textarea::placeholder {{
  color: #64748B !important;
}}

/* =========================
   BUTTONS
========================= */
.stButton > button[kind="primary"] {{
  background: #3430B8 !important;
  border: 1px solid #2B2796 !important;
  color: #FFFFFF !important;
  box-shadow: 0 12px 30px rgba(0,0,0,0.45) !important;
}}

.stButton > button[kind="primary"]:hover {{
  background: #3E3AD1 !important;
  border: 1px solid #302CAD !important;
}}

.stButton > button[kind="secondary"] {{
  background: #2A2A2A !important;
  border: 1px solid #3A3A3A !important;
  color: #EAEAEA !important;
}}

.stButton > button[kind="secondary"]:hover,
.stButton > button[kind="secondary"]:focus,
.stButton > button[kind="secondary"]:active {{
  background: #323232 !important;
  border: 1px solid #4A4A4A !important;
  color: #FFFFFF !important;
}}

/* =========================
   CARDS
========================= */
.card,
.card-sm,
.kpi-card,
.category-panel {{
  background: linear-gradient(180deg, rgba(17,24,39,0.98), rgba(15,23,42,0.98));
  border: 1px solid rgba(148,163,184,0.12);
  box-shadow: 0 14px 36px rgba(0,0,0,0.26);
}}

.card {{
  border-radius: var(--radius);
  padding: 1.5rem;
  margin-bottom: 1.25rem;
}}

.card-sm {{
  border-radius: var(--radius-sm);
  padding: 1rem 1.25rem;
}}

.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}}

.kpi-card {{
  border-radius: var(--radius);
  padding: 1.25rem 1rem;
  text-align: center;
}}

.kpi-value {{
  font-size: 2rem;
  font-weight: 800;
  color: #C4B5FD;
  line-height: 1;
}}

.kpi-label {{
  font-size: 0.78rem;
  color: {text_sub};
  margin-top: 0.4rem;
}}

.kpi-pos {{
  color: {positive};
}}

.kpi-neg {{
  color: {negative};
}}

/* =========================
   SLOTS
========================= */
.slot-grid {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.75rem;
  margin: 1rem 0;
}}

.slot-filled {{
  background: rgba(17,24,39,0.96);
  border: 1px solid rgba(139,92,246,0.5);
  border-radius: var(--radius-sm);
  padding: 0.75rem;
  text-align: center;
  position: relative;
  box-shadow: 0 10px 24px rgba(0,0,0,0.22);
}}

.slot-empty {{
  border: 1px dashed rgba(148,163,184,0.24);
  background: rgba(17,24,39,0.42);
  border-radius: var(--radius-sm);
  padding: 0.75rem;
  text-align: center;
  color: {text_sub};
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 80px;
}}

.slot-number {{
  font-size: 1.5rem;
  font-weight: 800;
  color: #475569;
}}

.slot-app-name {{
  font-size: 0.78rem;
  font-weight: 600;
  color: {text_main};
  margin-top: 0.25rem;
  word-break: break-all;
}}

.category-tag {{
  display: inline-block;
  padding: 0.25rem 0.65rem;
  border-radius: 99px;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  margin: 3px;
}}

.category-tag.on {{
  background: linear-gradient(135deg, #8B5CF6, #6366F1);
  color: #FFFFFF;
}}

.category-tag.off {{
  background: rgba(15,23,42,0.9);
  color: {text_sub};
  border: 1px solid rgba(148,163,184,0.12);
}}

/* =========================
   DATA + INFO
========================= */
[data-testid="stProgress"] > div > div {{
  background: linear-gradient(90deg, #8B5CF6, #6366F1) !important;
  border-radius: 99px !important;
}}

[data-testid="stDataFrame"] {{
  background: rgba(17,24,39,0.96) !important;
  border-radius: var(--radius-sm) !important;
  overflow-x: auto !important;
  border: 1px solid rgba(148,163,184,0.12) !important;
}}

.info-box {{
  background: rgba(30,41,59,0.96);
  border-left: 4px solid #8B5CF6;
  border-radius: var(--radius-sm);
  padding: 0.85rem 1rem;
  font-size: 0.88rem;
  color: {text_main};
  margin: 0.75rem 0;
}}

.warn-box {{
  background: rgba(66,32,6,0.42);
  border-left: 4px solid {warning};
  border-radius: var(--radius-sm);
  padding: 0.85rem 1rem;
  font-size: 0.88rem;
  color: #FDE68A;
  margin: 0.75rem 0;
}}

/* =========================
   LOADING
========================= */
.loading-overlay {{
  position: fixed;
  inset: 0;
  background: rgba(2,6,23,0.72);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 99998;
  display: flex;
  align-items: center;
  justify-content: center;
}}

.loading-modal {{
  background: linear-gradient(180deg, rgba(17,24,39,0.98), rgba(15,23,42,0.98));
  border: 1px solid rgba(148,163,184,0.12);
  border-radius: 20px;
  padding: 2.75rem 2.5rem 2rem;
  text-align: center;
  box-shadow: 0 24px 64px rgba(0,0,0,0.45);
  width: min(420px, 88vw);
  animation: fadeInUp 0.22s ease;
}}

@keyframes fadeInUp {{
  from {{
    opacity: 0;
    transform: translateY(16px);
  }}
  to {{
    opacity: 1;
    transform: translateY(0);
  }}
}}

.loading-parrot {{
  font-size: 3.6rem;
  line-height: 1;
  margin-bottom: 0.9rem;
  display: block;
  animation: bounce 1s ease infinite;
}}

@keyframes bounce {{
  0%, 100% {{
    transform: translateY(0);
  }}
  50% {{
    transform: translateY(-6px);
  }}
}}

.loading-stage {{
  font-size: 1.05rem;
  font-weight: 700;
  color: {text_main};
  margin-bottom: 0.35rem;
}}

.loading-detail {{
  font-size: 0.84rem;
  color: {text_sub};
  margin-bottom: 1.4rem;
}}

.loading-bar-wrap {{
  background: rgba(148,163,184,0.16);
  border-radius: 99px;
  height: 6px;
  overflow: hidden;
  margin-bottom: 0.6rem;
}}

.loading-bar-fill {{
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #8B5CF6, #6366F1);
  transition: width 0.35s ease;
}}

.loading-pct {{
  font-size: 0.78rem;
  color: {text_sub};
  font-weight: 600;
}}

/* -- Overall stage tracker -- */
.loading-overall {{
  margin-bottom: 1.5rem;
  padding-bottom: 1.3rem;
  border-bottom: 1px solid rgba(148,163,184,0.08);
}}
.loading-overall-toprow {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.55rem;
}}
.loading-overall-title {{
  font-size: 0.66rem;
  color: rgba(148,163,184,0.45);
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}}
.loading-overall-pct {{
  font-size: 0.82rem;
  font-weight: 800;
  color: #C4B5FD;
  letter-spacing: 0.02em;
}}

/* ── 전체 진행 바 (스테퍼 위) ─────────────────────────────── */
.loading-overall-bar {{
  position: relative;
  background: rgba(148,163,184,0.10);
  border-radius: 99px;
  height: 7px;
  margin-bottom: 1.25rem;
  overflow: hidden;
}}
.loading-overall-bar-fill {{
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #5B21B6, #8B5CF6, #C4B5FD);
  background-size: 200% 100%;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  animation: shimmer-bar 2.2s linear infinite;
  box-shadow: 0 0 8px rgba(139,92,246,0.45);
}}
@keyframes shimmer-bar {{
  0%   {{ background-position: 200% 0; }}
  100% {{ background-position: -200% 0; }}
}}

/* ── 스테퍼 (라벨 + 도트) ───────────────────────────────── */
.loading-stepper {{
  display: flex;
  align-items: flex-start;
  position: relative;
}}
.loading-stepper-track {{
  position: absolute;
  top: 7px;
  left: 8px;
  right: 8px;
  height: 2px;
  background: rgba(148,163,184,0.10);
  z-index: 0;
  border-radius: 99px;
}}
.loading-stepper-track-fill {{
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #5B21B6, #8B5CF6);
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}}
.loading-step {{
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  z-index: 1;
}}
.loading-step-dot {{
  width: 16px;
  height: 16px;
  border-radius: 50%;
  margin-bottom: 5px;
  flex-shrink: 0;
}}
.dot-done {{
  background: #6D28D9;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.6rem;
  font-weight: 700;
  color: #fff;
  line-height: 1;
  box-shadow: 0 0 0 2px rgba(109,40,217,0.3);
}}
.dot-active {{
  background: #A78BFA;
  box-shadow: 0 0 0 3px rgba(167,139,250,0.28);
  animation: pulse-step 1.3s ease-in-out infinite;
}}
.dot-pending {{
  background: rgba(148,163,184,0.13);
  border: 1.5px solid rgba(148,163,184,0.18);
  box-sizing: border-box;
}}
@keyframes pulse-step {{
  0%, 100% {{ box-shadow: 0 0 0 3px rgba(167,139,250,0.28); }}
  50% {{ box-shadow: 0 0 0 5px rgba(167,139,250,0.10); }}
}}
.loading-step-lbl {{
  font-size: 0.57rem;
  line-height: 1.2;
  text-align: center;
  word-break: keep-all;
  max-width: 40px;
}}
.lbl-done   {{ color: rgba(167,139,250,0.55); }}
.lbl-active {{ color: #C4B5FD; font-weight: 700; }}
.lbl-pending {{ color: rgba(148,163,184,0.25); }}

/* =========================
   SKELETON LOADING
========================= */
@keyframes skeleton-shimmer {{
  0%   {{ background-position: -200% center; }}
  100% {{ background-position:  200% center; }}
}}
@keyframes skeleton-pulse {{
  0%, 100% {{ opacity: 1; }}
  50%       {{ opacity: 0.25; }}
}}

.skeleton-wrap {{
  padding: 1.4rem 1.2rem 1rem;
  border-radius: 10px;
  background: rgba(255,255,255,0.015);
  border: 1px solid rgba(255,255,255,0.06);
  margin: 0.4rem 0 1rem;
}}

.skeleton-label {{
  font-size: 0.77rem;
  color: #64748B;
  letter-spacing: 0.05em;
  font-weight: 600;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 1.1rem;
}}

.skeleton-spinner {{
  display: inline-block;
  width: 13px;
  height: 13px;
  border: 2px solid rgba(148,163,184,0.15);
  border-top-color: #7BA7F5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}}

@keyframes spin {{
  to {{ transform: rotate(360deg); }}
}}

.skeleton-dots {{
  animation: skeleton-pulse 1.3s ease infinite;
  color: #475569;
}}

.skeleton-bar {{
  height: var(--skh, 10px);
  border-radius: 5px;
  width: var(--skw, 100%);
  background: linear-gradient(
    90deg,
    rgba(255,255,255,0.03) 0%,
    rgba(255,255,255,0.09) 40%,
    rgba(255,255,255,0.03) 70%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.7s linear infinite;
  margin-bottom: var(--skmb, 10px);
}}

.skeleton-chart {{
  width: 100%;
  height: var(--skch, 200px);
  border-radius: 8px;
  background: linear-gradient(
    90deg,
    rgba(255,255,255,0.025) 0%,
    rgba(255,255,255,0.07)  40%,
    rgba(255,255,255,0.025) 70%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.7s linear infinite;
  margin-bottom: 14px;
  position: relative;
}}

.skeleton-row {{
  display: flex;
  gap: 8px;
  margin-bottom: 7px;
}}

.skeleton-cell {{
  flex: var(--skflex, 1);
  height: 28px;
  border-radius: 4px;
  background: linear-gradient(
    90deg,
    rgba(255,255,255,0.025) 0%,
    rgba(255,255,255,0.07)  40%,
    rgba(255,255,255,0.025) 70%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.7s linear infinite;
}}

/* =========================
   BADGES + TABS
========================= */
.token-badge {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 99px;
  font-size: 0.75rem;
  font-weight: 600;
  background: rgba(16,185,129,0.14);
  color: #6EE7B7;
  margin: 2px;
}}

.stopword {{
  text-decoration: line-through;
  color: {text_sub};
  font-size: 0.82rem;
}}

.badge {{
  display: inline-block;
  padding: 2px 10px;
  border-radius: 99px;
  font-size: 0.75rem;
  font-weight: 700;
}}

.badge-pass {{
  background: rgba(16,185,129,0.16);
  color: #6EE7B7;
}}

.badge-warn {{
  background: rgba(245,158,11,0.16);
  color: #FCD34D;
}}

.badge-fail {{
  background: rgba(244,63,94,0.16);
  color: #FDA4AF;
}}

.badge-platform-ok {{
  background: rgba(139,92,246,0.16);
  color: #C4B5FD;
  font-size: 0.7rem;
}}

.badge-platform-na {{
  background: rgba(30,41,59,0.96);
  color: {text_sub};
  font-size: 0.7rem;
}}

button[data-baseweb="tab"] {{
  font-weight: 600 !important;
  color: {text_sub} !important;
}}

button[data-baseweb="tab"][aria-selected="true"] {{
  color: #C4B5FD !important;
  border-bottom-color: #8B5CF6 !important;
}}

/* =========================
   FLOAT BUTTON
========================= */
.float-btn-wrap {{
  position: fixed !important;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}}

.float-btn-label {{
  background: rgba(17,24,39,0.96);
  color: {text_sub};
  font-size: 0.78rem;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid rgba(148,163,184,0.14);
  white-space: nowrap;
  box-shadow: 0 8px 20px rgba(0,0,0,0.2);
}}


/* =========================
   RESPONSIVE
========================= */


@media (max-width: 768px) {{
  .main .block-container {{
    padding-left: 0.75rem !important;
    padding-right: 0.75rem !important;
  }}

  .kpi-grid {{
    grid-template-columns: repeat(2, 1fr);
  }}

  .slot-grid {{
    grid-template-columns: repeat(3, 1fr);
  }}

[data-testid="stSidebar"] .stMarkdown {{
  margin-top: 6px !important;
}}

[data-testid="stSidebar"] hr {{
  margin: 10px 0 12px 0 !important;
}}

[data-testid="stSidebar"] {{
  background: #171717 !important;
  width: 220px !important;
  min-width: 220px !important;
  border-right: 1px solid #2A2A2A !important;

  position: fixed !important;
  top: 68px !important;      /* 헤더 바로 아래 */
  left: 0;
  bottom: 0;

  padding-top: 12px !important;
}}
}}

</style>
"""