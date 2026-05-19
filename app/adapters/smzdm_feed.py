from __future__ import annotations

from datetime import datetime
import email.utils
import re
import xml.etree.ElementTree as ET

import httpx

from app.models.config import SourceConfig
from app.models.source_items import SourceFetchResponse, SourceItem

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    ),
}


class SmzdmFeedAdapter:
    def __init__(self, *, timeout: float = 20.0) -> None:
        self.timeout = timeout

    @staticmethod
    def _keyword_groups(source: SourceConfig) -> list[list[str]]:
        groups: list[list[str]] = []
        for phrase in source.keywords:
            tokens = [token.strip() for token in re.split(r"\s+", phrase) if token.strip()]
            if tokens:
                groups.append(tokens)
        return groups

    @staticmethod
    def _keyword_match_mode(source: SourceConfig) -> str:
        return str(getattr(source, "keyword_match_mode", "fuzzy") or "fuzzy").strip().lower()

    @staticmethod
    def _matches_keyword_groups(text: str, source: SourceConfig) -> bool:
        groups = SmzdmFeedAdapter._keyword_groups(source)
        if not groups:
            return True

        haystack = text.casefold()
        match_mode = SmzdmFeedAdapter._keyword_match_mode(source)
        for group in groups:
            if match_mode == "all_tokens":
                if all(token.casefold() in haystack for token in group):
                    return True
                continue
            hits = sum(1 for token in group if token.casefold() in haystack)
            if hits == len(group):
                return True
            if len(group) >= 2 and hits >= 2:
                return True
        return False

    def fetch_feed(self, source: SourceConfig) -> str:
        feed_url = getattr(source, "feed_url", None)
        if not feed_url:
            raise ValueError(f"Source {source.source_key} does not define feed_url.")

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(feed_url, headers=_DEFAULT_HEADERS)
            response.raise_for_status()
            return response.text

    def parse_feed(self, xml_text: str, *, source: SourceConfig, max_items: int = 3) -> SourceFetchResponse:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            raise ValueError("Invalid RSS feed: channel element not found.")

        items: list[SourceItem] = []
        limit = max(1, min(max_items, source.max_items or 5))
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or link).strip()
            description = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()

            if not title or not link:
                continue
            combined_text = "\n".join(part for part in (title, description) if part)
            if not self._matches_keyword_groups(combined_text, source):
                continue

            published_text = ""
            if pub_date:
                try:
                    published_dt = email.utils.parsedate_to_datetime(pub_date)
                    published_text = published_dt.isoformat()
                except (TypeError, ValueError):
                    published_text = pub_date

            items.append(
                SourceItem(
                    source_key=source.source_key,
                    external_id=guid,
                    title=title,
                    url=link,
                    source_type="smzdm_feed",
                    published_text=published_text,
                    summary=description,
                )
            )
            if len(items) >= limit:
                break

        return SourceFetchResponse(
            source_key=source.source_key,
            source_label=source.label,
            requested_items=max_items,
            returned_items=len(items),
            items=items,
        )

    def fetch_sample(self, source: SourceConfig, *, max_items: int = 3) -> SourceFetchResponse:
        xml_text = self.fetch_feed(source)
        return self.parse_feed(xml_text, source=source, max_items=max_items)
