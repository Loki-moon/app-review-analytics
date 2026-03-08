"""
Apple App Store 스크레이퍼 어댑터

- 앱 검색: iTunes Search API (공개 API, 인증 불필요)
- 리뷰 수집: iTunes Customer Reviews RSS JSON feed
  * 최대 10페이지 × 50건 = 500건, 최신순 정렬
  * 날짜 필터는 수집 후 in-process로 처리
"""
from __future__ import annotations

import time
from datetime import date, datetime, timezone

import requests

from .base import AppInfo, BaseScraper, ReviewRecord

_SEARCH_URL = "https://itunes.apple.com/search"
_REVIEWS_URL = "https://itunes.apple.com/kr/rss/customerreviews/page={page}/id={app_id}/sortBy=mostRecent/json"
_TIMEOUT = 10


class AppStoreScraper(BaseScraper):
    platform_key = "app_store"
    platform_label = "Apple App Store"

    def is_supported(self) -> bool:
        return True

    # ── 앱 검색 ──────────────────────────────────────────────────────────────
    def search_apps(self, query: str, n: int = 5) -> list[AppInfo]:
        try:
            resp = requests.get(
                _SEARCH_URL,
                params={
                    "term": query,
                    "entity": "software",
                    "country": "kr",
                    "lang": "ko_kr",
                    "limit": n,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"App Store 앱 검색 실패: {e}") from e

        apps: list[AppInfo] = []
        for r in data.get("results", [])[:n]:
            apps.append(
                AppInfo(
                    app_id=str(r.get("trackId", "")),
                    app_name=r.get("trackName", ""),
                    developer=r.get("artistName", ""),
                    platform=self.platform_label,
                    icon_url=r.get("artworkUrl512") or r.get("artworkUrl100", ""),
                    rating=r.get("averageUserRating"),
                    installs="",
                    market_url=r.get("trackViewUrl", ""),
                )
            )
        return apps

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
        collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt   = datetime.combine(end_date,   datetime.max.time()).replace(tzinfo=timezone.utc)

        too_old = False
        for page in range(1, 11):  # 최대 10 페이지
            if too_old or len(collected) >= max_count:
                break

            url = _REVIEWS_URL.format(page=page, app_id=app_id)
            try:
                resp = requests.get(url, timeout=_TIMEOUT)
                resp.raise_for_status()
                feed = resp.json().get("feed", {})
            except Exception:
                break

            entries = feed.get("entry", [])
            # 첫 entry는 앱 메타 정보이므로 건너뜀
            if page == 1 and entries:
                entries = entries[1:]

            if not entries:
                break

            for entry in entries:
                try:
                    updated_str = entry.get("updated", {}).get("label", "")
                    review_dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    if review_dt.tzinfo is None:
                        review_dt = review_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    review_dt = None

                if review_dt:
                    if review_dt > end_dt:
                        continue
                    if review_dt < start_dt:
                        too_old = True
                        break

                review_date_str = review_dt.strftime("%Y-%m-%d") if review_dt else ""
                score_raw = entry.get("im:rating", {}).get("label", "0")
                try:
                    score = int(score_raw)
                except ValueError:
                    score = 0

                collected.append(
                    ReviewRecord(
                        platform=self.platform_label,
                        app_name=app_name,
                        app_id=app_id,
                        review_id=entry.get("id", {}).get("label", ""),
                        review_date=review_date_str,
                        score=score,
                        content=entry.get("content", {}).get("label", ""),
                        user_name=entry.get("author", {}).get("name", {}).get("label", ""),
                        review_created_version=entry.get("im:version", {}).get("label", ""),
                        thumbs_up_count=0,
                        collected_at=collected_at,
                    )
                )

            if progress_callback:
                progress_callback(len(collected), min(max_count, 500))

            time.sleep(0.3)  # API 과부하 방지

        return collected
