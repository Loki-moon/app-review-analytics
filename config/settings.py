"""
전역 설정 파일 — 경로, 우선순위 공식, 플랫폼 메타 등
"""
from pathlib import Path

# ── 경로 ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
ASSETS_DIR = BASE_DIR / "assets"

# 디렉터리 자동 생성
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ── 플랫폼 메타 ───────────────────────────────────────────────────────────────
PLATFORMS = {
    "Google Play Store": {
        "key": "google_play",
        "supported": True,
        "icon": "🟢",
        "note": None,
    },
    "Apple App Store": {
        "key": "app_store",
        "supported": True,
        "icon": "⚪",
        "note": None,
    },
    "Samsung Galaxy Store": {
        "key": "galaxy_store",
        "supported": False,
        "icon": "⚪",
        "note": "현재 버전에서는 갤럭시 스토어 리뷰 조회가 제한될 수 있어요.",
    },
    "One Store": {
        "key": "one_store",
        "supported": False,
        "icon": "⚪",
        "note": "현재 버전에서는 원스토어 리뷰 조회가 제한될 수 있어요.",
    },
}

# ── 수집 설정 ─────────────────────────────────────────────────────────────────
MAX_APPS = 5
DEFAULT_REVIEW_COUNT = 3000   # 앱당 최대 수집 수
REVIEW_CHUNK_SIZE = 200       # google-play-scraper 1회 배치 크기

# ── 분석 설정 ─────────────────────────────────────────────────────────────────
POSITIVE_THRESHOLD = 4        # 4,5점 → 긍정(1)
NEGATIVE_THRESHOLD = 2        # 1,2점 → 부정(0)
# 3점은 기본 분석에서 제외

UPDATE_FLAG_DAYS = 7          # 버전 변경 후 N일 이내 → update_flag=1

# ── 우선순위 점수 공식 설정 ────────────────────────────────────────────────────
# priority_score = w_delta * |ΔOR| + w_vuln * vulnerability_score
PRIORITY_WEIGHTS = {
    "w_delta": 0.6,
    "w_vuln": 0.4,
}

# ── 시각화 설정 ───────────────────────────────────────────────────────────────
WORDCLOUD_MAX_WORDS = 100
TOP_KEYWORDS_N = 30

APP_COLORS = [
    "#4F8EF7", "#F7844F", "#4FD6A5", "#C84FF7", "#F7D84F",
]
