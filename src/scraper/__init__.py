from .base import AppInfo, BaseScraper, ReviewRecord
from .google_play import GooglePlayScraper
from .app_store import AppStoreScraper

SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "google_play": GooglePlayScraper,
    "app_store": AppStoreScraper,
}

def get_scraper(platform_key: str) -> BaseScraper:
    cls = SCRAPER_REGISTRY.get(platform_key)
    if cls is None:
        raise ValueError(f"지원하지 않는 플랫폼: {platform_key}")
    return cls()
