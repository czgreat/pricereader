from app.models.evaluation import CandidateInput
from app.models.source_items import SourceItem
from app.services.notification_service import notify_matches
from app.services.rule_engine import evaluate_candidate
from app.services.storage import SourceItemRepository


def test_notify_matches_writes_notification_record_when_configured(monkeypatch, tmp_path) -> None:
    from app.services import notification_service as notification_module
    from app.models.runtime_config import RuntimeConfigPayload

    sent_messages = []

    class FakeNotifier:
        def __init__(self, *args, **kwargs):
            pass

        def send_sync(self, message):
            sent_messages.append(message)

    class FakeSettings:
        wechat_push_url = "http://example.com/push"
        wechat_push_token = "token"
        wechat_target_id = "target-id"

    class FakeRuntimeStore:
        def load(self) -> RuntimeConfigPayload:
            return RuntimeConfigPayload(
                wechat_push_url="http://example.com/push",
                wechat_push_token="token",
                wechat_target_id="target-id",
            )

    monkeypatch.setattr(notification_module, "WeChatGatewayNotifier", FakeNotifier)
    monkeypatch.setattr(notification_module, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(notification_module, "RuntimeConfigStore", FakeRuntimeStore)

    item = SourceItem(
        source_key="smzdm_keywords_primary",
        external_id="demo-1",
        title="欧乐B iO3 电动牙刷 到手339元",
        url="https://www.smzdm.com/p/demo-1/",
        source_type="smzdm_feed",
        summary="整机好价，适合自用。",
    )
    evaluation = evaluate_candidate(
        CandidateInput(
            source_key=item.source_key,
            external_id=item.external_id,
            title=item.title,
            body=item.summary,
            url=item.url,
        )
    )

    repo = SourceItemRepository(db_path=tmp_path / "notify.db")
    attempted, sent, skipped = notify_matches(item, evaluation, repository=repo)
    records = repo.list_notification_records(limit=10)

    assert attempted == 1
    assert sent == 1
    assert skipped == 0
    assert len(sent_messages) == 1
    assert len(records) == 1
    assert records[0].rule_key == "oralb_io3"


def test_notify_matches_respects_cooldown(monkeypatch, tmp_path) -> None:
    from app.services import notification_service as notification_module
    from app.models.runtime_config import RuntimeConfigPayload

    sent_messages = []

    class FakeNotifier:
        def __init__(self, *args, **kwargs):
            pass

        def send_sync(self, message):
            sent_messages.append(message)

    class FakeSettings:
        wechat_push_url = "http://example.com/push"
        wechat_push_token = "token"
        wechat_target_id = "target-id"

    class FakeRuntimeStore:
        def load(self) -> RuntimeConfigPayload:
            return RuntimeConfigPayload(
                wechat_push_url="http://example.com/push",
                wechat_push_token="token",
                wechat_target_id="target-id",
            )

    monkeypatch.setattr(notification_module, "WeChatGatewayNotifier", FakeNotifier)
    monkeypatch.setattr(notification_module, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(notification_module, "RuntimeConfigStore", FakeRuntimeStore)

    item = SourceItem(
        source_key="smzdm_keywords_primary",
        external_id="demo-2",
        title="欧乐B iO3 电动牙刷 到手339元",
        url="https://www.smzdm.com/p/demo-2/",
        source_type="smzdm_feed",
        summary="整机好价，适合自用。",
    )
    evaluation = evaluate_candidate(
        CandidateInput(
            source_key=item.source_key,
            external_id=item.external_id,
            title=item.title,
            body=item.summary,
            url=item.url,
        )
    )

    repo = SourceItemRepository(db_path=tmp_path / "notify-cooldown.db")
    first = notify_matches(item, evaluation, repository=repo)
    second = notify_matches(item, evaluation, repository=repo)
    records = repo.list_notification_records(limit=10)

    assert first == (1, 1, 0)
    assert second == (0, 0, 1)
    assert len(sent_messages) == 1
    assert records[0].status == "skipped_cooldown"


def test_notify_matches_respects_manual_mute(monkeypatch, tmp_path) -> None:
    from app.services import notification_service as notification_module
    from app.models.runtime_config import RuntimeConfigPayload

    sent_messages = []

    class FakeNotifier:
        def __init__(self, *args, **kwargs):
            pass

        def send_sync(self, message):
            sent_messages.append(message)

    class FakeSettings:
        wechat_push_url = "http://example.com/push"
        wechat_push_token = "token"
        wechat_target_id = "target-id"

    class FakeRuntimeStore:
        def load(self) -> RuntimeConfigPayload:
            return RuntimeConfigPayload(
                wechat_push_url="http://example.com/push",
                wechat_push_token="token",
                wechat_target_id="target-id",
            )

    monkeypatch.setattr(notification_module, "WeChatGatewayNotifier", FakeNotifier)
    monkeypatch.setattr(notification_module, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(notification_module, "RuntimeConfigStore", FakeRuntimeStore)

    item = SourceItem(
        source_key="smzdm_keywords_primary",
        external_id="demo-3",
        title="欧乐B iO3 电动牙刷 到手339元",
        url="https://www.smzdm.com/p/demo-3/",
        source_type="smzdm_feed",
        summary="整机好价，适合自用。",
    )
    evaluation = evaluate_candidate(
        CandidateInput(
            source_key=item.source_key,
            external_id=item.external_id,
            title=item.title,
            body=item.summary,
            url=item.url,
        )
    )

    repo = SourceItemRepository(db_path=tmp_path / "notify-muted.db")
    repo.set_item_muted(source_key=item.source_key, external_id=item.external_id, muted=True, reason="manual mute")
    attempted, sent, skipped = notify_matches(item, evaluation, repository=repo)
    records = repo.list_notification_records(limit=10)

    assert attempted == 0
    assert sent == 0
    assert skipped == 1
    assert len(sent_messages) == 0
    assert records[0].status == "skipped_muted"


def test_notify_matches_prefers_runtime_config_over_settings(monkeypatch, tmp_path) -> None:
    from app.services import notification_service as notification_module
    from app.models.runtime_config import RuntimeConfigPayload

    captured = {}

    class FakeNotifier:
        def __init__(self, *, push_url, token, **kwargs):
            captured["push_url"] = push_url
            captured["token"] = token

        def send_sync(self, message):
            captured["target_id"] = message.target_id

    class FakeSettings:
        wechat_push_url = ""
        wechat_push_token = ""
        wechat_target_id = ""

    class FakeRuntimeStore:
        def load(self) -> RuntimeConfigPayload:
            return RuntimeConfigPayload(
                wechat_push_url="http://localhost:23456/api/push",
                wechat_push_token="test-token",
                wechat_target_id="o9cq800nb1_O0PDsDrF1X4gaT_yI@im.wechat",
            )

    monkeypatch.setattr(notification_module, "WeChatGatewayNotifier", FakeNotifier)
    monkeypatch.setattr(notification_module, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(notification_module, "RuntimeConfigStore", FakeRuntimeStore)

    item = SourceItem(
        source_key="smzdm_keywords_primary",
        external_id="demo-runtime-1",
        title="欧乐B iO3 电动牙刷 到手339元",
        url="https://www.smzdm.com/p/demo-runtime-1/",
        source_type="smzdm_feed",
        summary="整机好价，适合自用。",
    )
    evaluation = evaluate_candidate(
        CandidateInput(
            source_key=item.source_key,
            external_id=item.external_id,
            title=item.title,
            body=item.summary,
            url=item.url,
        )
    )

    repo = SourceItemRepository(db_path=tmp_path / "notify-runtime.db")
    attempted, sent, skipped = notify_matches(item, evaluation, repository=repo)

    assert attempted == 1
    assert sent == 1
    assert skipped == 0
    assert captured["push_url"] == "http://localhost:23456/api/push"
    assert captured["token"] == "9fb479465223719122105bf753f37b3f17bcfeed1f6c18fe"
    assert captured["target_id"] == "o9cq800nb1_O0PDsDrF1X4gaT_yI@im.wechat"
