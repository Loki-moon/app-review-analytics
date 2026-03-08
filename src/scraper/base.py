"""
Scraper 추상 베이스 — 플랫폼별 어댑터가 이 인터페이스를 구현한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class AppInfo:
    """앱 검색 결과 카드 DTO"""
    app_id: str
    app_name: str
    developer: str
    platform: str
    icon_url: str = ""
    rating: float | None = None
    installs: str = ""
    market_url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewRecord:
    """수집된 리뷰 1건 DTO"""
    platform: str
    app_name: str
    app_id: str
    review_id: str
    review_date: str          # ISO 8601 string (YYYY-MM-DD)
    score: int
    content: str
    user_name: str = ""
    review_created_version: str = ""
    thumbs_up_count: int = 0
    reply_content: str = ""
    replied_at: str = ""
    collected_at: str = ""


class BaseScraper(ABC):
    """플랫폼 스크레이퍼 추상 클래스"""

    platform_key: str = ""        # 하위 클래스에서 override
    platform_label: str = ""

    # ── 앱 검색 ──────────────────────────────────────────────────────────────
    @abstractmethod
    def search_apps(self, query: str, n: int = 5) -> list[AppInfo]:
        """앱명으로 검색, 최대 n개 후보 반환"""
        ...

    # ── 리뷰 수집 ─────────────────────────────────────────────────────────────
    @abstractmethod
    def fetch_reviews(
        self,
        app_id: str,
        app_name: str,
        start_date: date,
        end_date: date,
        max_count: int = 3000,
        progress_callback=None,
    ) -> list[ReviewRecord]:
        """
        지정 기간의 리뷰를 수집한다.
        progress_callback(current: int, total_estimate: int) 형태로 진행 보고.
        """
        ...

    # ── 공통 유틸 ─────────────────────────────────────────────────────────────
    def is_supported(self) -> bool:
        """MVP 1차에서 실제 수집 가능 여부"""
        return True
