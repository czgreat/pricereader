from app.adapters.douban_group import DoubanGroupAdapter
from app.models.config import SourceConfig


SAMPLE_HTML = """
<html>
  <body>
    <table class="olt">
      <tr class="th">
        <td>讨论</td><td>作者</td><td class="r-count">回复</td><td>最后回复</td>
      </tr>
      <tr>
        <td class="title">
          <a href="https://www.douban.com/group/topic/482306083/?_spm_id=foo" title="【出闲置】小李子兔肉12罐">【出闲置】小李子兔肉12罐</a>
        </td>
        <td><a href="https://www.douban.com/people/216801541/">咔咔</a></td>
        <td class="r-count">1</td>
        <td class="time">03-28 18:56</td>
      </tr>
      <tr>
        <td class="title">
          <a href="https://www.douban.com/group/topic/482293422/?_spm_id=bar" title="【代拍】小李子70/6罐">【代拍】小李子70/6罐</a>
        </td>
        <td><a href="https://www.douban.com/people/Nanana0829/">nikoni</a></td>
        <td class="r-count">3</td>
        <td class="time">03-28 18:45</td>
      </tr>
    </table>
  </body>
</html>
"""


def test_parse_topic_list_extracts_items() -> None:
    adapter = DoubanGroupAdapter()
    source = SourceConfig(
        source_key="douban_group_656297_tab_42899",
        label="爱猫生活 / 闲车禁拼多多",
        url="https://www.douban.com/group/656297/?tab=42899",
    )

    result = adapter.parse_topic_list(SAMPLE_HTML, source=source, max_items=2)

    assert result.returned_items == 2
    assert result.items[0].external_id == "482306083"
    assert result.items[0].author_name == "咔咔"
    assert result.items[1].reply_count == 3


DETAIL_HTML = """
<html>
  <body>
    <div id="link-report">
      <div class="topic-richtext">
        皇家泌尿处方粮 LP34，剩余半袋。
        <img src="https://img.example.com/1.jpg" />
      </div>
    </div>
  </body>
</html>
"""


def test_parse_topic_detail_extracts_body_and_images() -> None:
    adapter = DoubanGroupAdapter()
    result = adapter.parse_topic_detail(
        DETAIL_HTML,
        source_key="douban_group_656297_tab_42899",
        external_id="482307647",
        fetched_at="2026-03-28T00:00:00+00:00",
    )

    assert result.status == "ok"
    assert "皇家泌尿处方粮" in result.body_text
    assert result.image_urls == ["https://img.example.com/1.jpg"]
