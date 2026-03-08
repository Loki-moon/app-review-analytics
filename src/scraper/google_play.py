"""
Google Play Store 스크레이퍼 어댑터

의존: google-play-scraper
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timezone

from google_play_scraper import app as gp_app
from google_play_scraper import reviews as gp_reviews
from google_play_scraper import search as gp_search
from google_play_scraper.constants.google_play import Sort

from .base import AppInfo, BaseScraper, ReviewRecord


class GooglePlayScraper(BaseScraper):
    platform_key = "google_play"
    platform_label = "Google Play Store"

    LANG = "ko"
    COUNTRY = "kr"

    def _scrape_search_page_ids(self, query: str, n: int) -> list[str]:
        """gp_search가 appId=None 반환 시 직접 검색 페이지에서 package ID 추출"""
        try:
            import requests
            resp = requests.get(
                "https://play.google.com/store/search",
                params={"q": query, "c": "apps", "hl": self.LANG, "gl": self.COUNTRY},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
            )
            ids = re.findall(r"/store/apps/details\?id=([\w.]+)", resp.text)
            seen: set[str] = set()
            unique: list[str] = []
            for aid in ids:
                if aid not in seen:
                    seen.add(aid)
                    unique.append(aid)
            return unique[:n]
        except Exception:
            return []

    # ── 앱 검색 ──────────────────────────────────────────────────────────────
    def search_apps(self, query: str, n: int = 5) -> list[AppInfo]:
        try:
            results = gp_search(
                query,
                lang=self.LANG,
                country=self.COUNTRY,
                n_hits=n,
            )
        except Exception as e:
            raise RuntimeError(f"Google Play 앱 검색 실패: {e}") from e

        # gp_search가 Featured 슬롯의 appId를 None으로 반환하는 라이브러리 버그 대응
        # → 검색 페이지 직접 파싱으로 package ID 보완
        fallback_ids: list[str] = []
        if any(r.get("appId") is None for r in results[:n]):
            fallback_ids = self._scrape_search_page_ids(query, n)

        fallback_idx = 0
        apps: list[AppInfo] = []
        for r in results[:n]:
            app_id = r.get("appId") or ""
            if not app_id and fallback_idx < len(fallback_ids):
                app_id = fallback_ids[fallback_idx]
            if app_id:
                fallback_idx += 1
            apps.append(
                AppInfo(
                    app_id=app_id,
                    app_name=r.get("title", ""),
                    developer=r.get("developer", ""),
                    platform=self.platform_label,
                    icon_url=r.get("icon", ""),
                    rating=r.get("score"),
                    installs=r.get("installs", ""),
                    market_url=f"https://play.google.com/store/apps/details?id={app_id}",
                )
            )
        return apps

    # ── 앱 상세 정보 ──────────────────────────────────────────────────────────
    def get_app_detail(self, app_id: str) -> AppInfo:
        try:
            detail = gp_app(app_id, lang=self.LANG, country=self.COUNTRY)
        except Exception as e:
            raise RuntimeError(f"앱 상세 정보 조회 실패: {e}") from e

        return AppInfo(
            app_id=app_id,
            app_name=detail.get("title", ""),
            developer=detail.get("developer", ""),
            platform=self.platform_label,
            icon_url=detail.get("icon", ""),
            rating=detail.get("score"),
            installs=detail.get("installs", ""),
            market_url=f"https://play.google.com/store/apps/details?id={app_id}",
            extra={
                "genre": detail.get("genre", ""),
                "reviews_count": detail.get("reviews", 0),
            },
        )

    # ── 리뷰 수집 ─────────────────────────────────────────────────────────────
    def fetch_reviews(
        self,
        app_id: str,
        app_name: str,
        start_date: date,
        end_date: date,
        max_count: int = 3000,
        progress_callback=None,
    ) -> list[ReviewRecord]:
        collected: list[ReviewRecord] = []
        continuation_token = None
        collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        batch_size = 200

        # 날짜 범위를 datetime으로 변환 (tz-aware)
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt   = datetime.combine(end_date,   datetime.max.time()).replace(tzinfo=timezone.utc)

        try:
            while len(collected) < max_count:
                result, continuation_token = gp_reviews(
                    app_id,
                    lang=self.LANG,
                    country=self.COUNTRY,
                    sort=Sort.NEWEST,
                    count=batch_size,
                    continuation_token=continuation_token,
                )

                if not result:
                    break

                added_in_batch = 0
                too_old = False

                for r in result:
                    at = r.get("at")
                    if at is None:
                        continue

                    # google-play-scraper는 naive datetime 반환 → UTC로 가정
                    if at.tzinfo is None:
                        at = at.replace(tzinfo=timezone.utc)

                    if at > end_dt:
                        continue
                    if at < start_dt:
                        too_old = True
                        break

                    record = ReviewRecord(
                        platform=self.platform_label,
                        app_name=app_name,
                        app_id=app_id,
                        review_id=r.get("reviewId", ""),
                        review_date=at.strftime("%Y-%m-%d"),
                        score=int(r.get("score", 0)),
                        content=r.get("content", ""),
                        user_name=r.get("userName", ""),
                        review_created_version=r.get("reviewCreatedVersion", ""),
                        thumbs_up_count=int(r.get("thumbsUpCount", 0)),
                        reply_content=r.get("replyContent", "") or "",
                        replied_at=r.get("repliedAt", "").strftime("%Y-%m-%d") if r.get("repliedAt") else "",
                        collected_at=collected_at,
                    )
                    collected.append(record)
                    added_in_batch += 1

                if progress_callback:
                    progress_callback(len(collected), max_count)

                if too_old or continuation_token is None:
                    break

                # API 부하 방지
                time.sleep(0.3)

        except Exception as e:
            raise RuntimeError(f"Google Play 리뷰 수집 실패: {e}") from e

        return collected
