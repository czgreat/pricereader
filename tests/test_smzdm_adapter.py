from app.adapters.smzdm_feed import SmzdmFeedAdapter
from app.models.config import SourceConfig


SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>什么值得买</title>
    <item>
      <title>欧乐B iO3 电动牙刷 到手339元</title>
      <link>http://www.smzdm.com/p/123456/</link>
      <guid>smzdm-123456</guid>
      <description>官方好价，整机可用。</description>
      <pubDate>Sat, 28 Mar 2026 10:16:39 +0800</pubDate>
    </item>
    <item>
      <title>渴望猫粮 5.4kg 399元</title>
      <link>http://www.smzdm.com/p/654321/</link>
      <guid>smzdm-654321</guid>
      <description>好价回归。</description>
      <pubDate>Sat, 28 Mar 2026 10:20:00 +0800</pubDate>
    </item>
  </channel>
</rss>
"""


def test_parse_feed_extracts_items() -> None:
    adapter = SmzdmFeedAdapter()
    source = SourceConfig(
        source_key="smzdm_keywords_primary",
        label="什么值得买 / 官方RSS",
        feed_url="http://feed.smzdm.com",
        keywords=["渴望 猫粮 5.4kg", "欧乐B io3"],
    )

    result = adapter.parse_feed(SAMPLE_FEED, source=source, max_items=2)

    assert result.returned_items == 2
    assert result.items[0].external_id == "smzdm-123456"
    assert result.items[0].source_type == "smzdm_feed"
    assert result.items[1].title == "渴望猫粮 5.4kg 399元"


def test_parse_feed_filters_unrelated_items() -> None:
    adapter = SmzdmFeedAdapter()
    source = SourceConfig(
        source_key="smzdm_keywords_primary",
        label="什么值得买 / 官方RSS",
        feed_url="http://feed.smzdm.com",
        keywords=["渴望 猫粮 5.4kg", "欧乐B io3"],
    )
    feed = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>安耐晒 小金瓶防晒霜 60ml 59.4元</title>
          <link>http://www.smzdm.com/p/111111/</link>
          <guid>smzdm-111111</guid>
          <description>无关条目。</description>
          <pubDate>Sat, 28 Mar 2026 10:20:00 +0800</pubDate>
        </item>
        <item>
          <title>欧乐B iO3 电动牙刷 到手339元</title>
          <link>http://www.smzdm.com/p/222222/</link>
          <guid>smzdm-222222</guid>
          <description>相关条目。</description>
          <pubDate>Sat, 28 Mar 2026 10:21:00 +0800</pubDate>
        </item>
      </channel>
    </rss>
    """

    result = adapter.parse_feed(feed, source=source, max_items=3)

    assert result.returned_items == 1
    assert result.items[0].external_id == "smzdm-222222"


def test_parse_feed_without_keywords_uses_max_items_limit() -> None:
    adapter = SmzdmFeedAdapter()
    items = "\n".join(
        f"""
        <item>
          <title>测试条目 {index}</title>
          <link>http://www.smzdm.com/p/{index}/</link>
          <guid>smzdm-{index}</guid>
          <description>描述 {index}</description>
          <pubDate>Sat, 28 Mar 2026 10:{index:02d}:00 +0800</pubDate>
        </item>
        """
        for index in range(1, 8)
    )
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        {items}
      </channel>
    </rss>
    """
    source = SourceConfig(
        source_key="smzdm_keywords_primary",
        label="什么值得买 / 官方RSS",
        feed_url="http://feed.smzdm.com",
        max_items=5,
        keywords=[],
    )

    result = adapter.parse_feed(feed, source=source, max_items=9)

    assert result.returned_items == 5
    assert result.items[0].external_id == "smzdm-1"
    assert result.items[-1].external_id == "smzdm-5"


def test_parse_feed_all_tokens_mode_requires_all_tokens() -> None:
    adapter = SmzdmFeedAdapter()
    feed = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>京东 正大 鸡胸肉 2kg 19.9元</title>
          <link>http://www.smzdm.com/p/333333/</link>
          <guid>smzdm-333333</guid>
          <description>冷冻鸡胸肉好价。</description>
          <pubDate>Sat, 28 Mar 2026 10:22:00 +0800</pubDate>
        </item>
        <item>
          <title>正大 鸡胸肉 2kg 19.9元</title>
          <link>http://www.smzdm.com/p/444444/</link>
          <guid>smzdm-444444</guid>
          <description>渠道字段缺失。</description>
          <pubDate>Sat, 28 Mar 2026 10:23:00 +0800</pubDate>
        </item>
      </channel>
    </rss>
    """
    source = SourceConfig.model_validate(
        {
            "source_key": "smzdm_jd_chicken_breast",
            "label": "什么值得买 / 京东鸡胸肉",
            "feed_url": "http://feed.smzdm.com",
            "keywords": ["京东 鸡胸肉", "京东 鸡小胸"],
            "keyword_match_mode": "all_tokens",
        }
    )

    result = adapter.parse_feed(feed, source=source, max_items=5)

    assert result.returned_items == 1
    assert result.items[0].external_id == "smzdm-333333"
