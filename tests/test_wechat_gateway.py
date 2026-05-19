from app.notifiers.wechat_gateway import WeChatGatewayNotifier, WeChatPushMessage


def test_wechat_gateway_payload_and_headers() -> None:
    notifier = WeChatGatewayNotifier(
        push_url="http://localhost:23456/api/push",
        token="token-value",
    )
    message = WeChatPushMessage(
        title="好价提醒",
        content="渴望猫粮 5.4kg 399",
        target_id="target",
        link_url="https://example.com/item",
    )

    payload = notifier.build_payload(message)
    headers = notifier.build_headers()

    assert payload["title"] == "好价提醒"
    assert payload["targetId"] == "target"
    assert payload["linkUrl"] == "https://example.com/item"
    assert headers["Authorization"] == "Bearer token-value"

