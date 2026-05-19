from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.models.config import SourceConfig
from app.models.source_items import SourceFetchResponse, SourceItem, SourceItemDetail

_TOPIC_ID_RE = re.compile(r"/group/topic/(?P<topic_id>\d+)/")
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    ),
    "Referer": "https://www.douban.com/group/",
}


class DoubanGroupAdapter:
    def __init__(self, *, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def _build_headers(self, cookie: str | None = None) -> dict[str, str]:
        headers = dict(_DEFAULT_HEADERS)
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def fetch_html(self, source: SourceConfig, *, cookie: str | None = None) -> str:
        if not source.url:
            raise ValueError(f"Source {source.source_key} does not define a URL.")

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(source.url, headers=self._build_headers(cookie))
            response.raise_for_status()
            return response.text

    def parse_topic_list(self, html: str, *, source: SourceConfig, max_items: int = 3) -> SourceFetchResponse:
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table.olt tr")
        items: list[SourceItem] = []

        for row in rows:
            title_cell = row.select_one("td.title a")
            if title_cell is None:
                continue

            href = title_cell.get("href", "").strip()
            topic_match = _TOPIC_ID_RE.search(href)
            if not href or topic_match is None:
                continue

            author_cell = row.select_one("td:nth-of-type(2) a")
            reply_cell = row.select_one("td.r-count")
            time_cell = row.select_one("td.time")

            items.append(
                SourceItem(
                    source_key=source.source_key,
                    external_id=topic_match.group("topic_id"),
                    title=title_cell.get_text(strip=True),
                    url=urljoin("https://www.douban.com", href),
                    source_type="douban_topic",
                    author_name=author_cell.get_text(strip=True) if author_cell else "",
                    author_url=urljoin("https://www.douban.com", author_cell.get("href", "").strip()) if author_cell and author_cell.get("href") else None,
                    reply_count=int(reply_cell.get_text(strip=True) or "0") if reply_cell else 0,
                    last_active_text=time_cell.get_text(strip=True) if time_cell else "",
                )
            )
            if len(items) >= max_items:
                break

        return SourceFetchResponse(
            source_key=source.source_key,
            source_label=source.label,
            requested_items=max_items,
            returned_items=len(items),
            items=items,
        )

    def fetch_sample(self, source: SourceConfig, *, cookie: str | None = None, max_items: int = 3) -> SourceFetchResponse:
        capped_items = max(1, min(max_items, 3))
        html = self.fetch_html(source, cookie=cookie)
        return self.parse_topic_list(html, source=source, max_items=capped_items)

    def fetch_topic_detail(self, item: SourceItem, *, cookie: str | None = None) -> SourceItemDetail:
        fetched_at = datetime.now(timezone.utc).isoformat()
        if not cookie:
            return SourceItemDetail(
                source_key=item.source_key,
                external_id=item.external_id,
                status="missing_cookie",
                fetched_at=fetched_at,
            )

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(
                item.url,
                headers=self._build_headers(cookie),
            )

        if response.status_code in (401, 403):
            return SourceItemDetail(
                source_key=item.source_key,
                external_id=item.external_id,
                status=f"http_{response.status_code}",
                fetched_at=fetched_at,
            )
        response.raise_for_status()
        return self.parse_topic_detail(
            response.text,
            source_key=item.source_key,
            external_id=item.external_id,
            fetched_at=fetched_at,
        )

    def parse_topic_detail(self, html: str, *, source_key: str, external_id: str, fetched_at: str) -> SourceItemDetail:
        soup = BeautifulSoup(html, "html.parser")

        body_selectors = [
            "#link-report .topic-richtext",
            "#link-report .topic-content",
            ".topic-doc",
            ".rich-content",
        ]
        body_text = ""
        for selector in body_selectors:
            node = soup.select_one(selector)
            if node:
                body_text = node.get_text("\n", strip=True)
                if body_text:
                    break

        if not body_text:
            title_node = soup.select_one("h1")
            title_text = title_node.get_text(" ", strip=True) if title_node else ""
            if "没有访问权限" in title_text:
                return SourceItemDetail(
                    source_key=source_key,
                    external_id=external_id,
                    status="access_denied",
                    fetched_at=fetched_at,
                )

        image_urls: list[str] = []
        for selector in [
            "#link-report img",
            ".topic-doc img",
            ".topic-content img",
            ".rich-content img",
        ]:
            for node in soup.select(selector):
                src = (node.get("src") or node.get("data-src") or "").strip()
                if src and src not in image_urls:
                    image_urls.append(src)

        return SourceItemDetail(
            source_key=source_key,
            external_id=external_id,
            status="ok" if body_text else "empty",
            body_text=body_text,
            image_urls=image_urls,
            fetched_at=fetched_at,
        )
