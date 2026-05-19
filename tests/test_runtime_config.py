from app.models.runtime_config import RuntimeConfigPayload
from app.core.settings import get_settings
from app.services.runtime_config import RuntimeConfigStore


def test_runtime_config_store_roundtrip(tmp_path) -> None:
    store = RuntimeConfigStore(path=tmp_path / ".env.local")
    payload = RuntimeConfigPayload(
        wechat_push_url="http://gateway.local/api/push",
        douban_cookie="ck=demo",
        smzdm_cookie="smzdm=demo",
        wechat_push_token="token",
        wechat_target_id="target",
    )

    stored = store.save(payload)
    loaded = store.load()

    assert stored == loaded
    assert loaded.wechat_push_url == "http://gateway.local/api/push"
    assert loaded.douban_cookie == "ck=demo"
    assert loaded.wechat_target_id == "target"


def test_settings_default_runtime_config_path_is_persistent() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.local_env_path.as_posix() == "data/runtime/.env.local"


def test_runtime_config_view_masks_sensitive_values(tmp_path) -> None:
    store = RuntimeConfigStore(path=tmp_path / ".env.local")
    store.save(
        RuntimeConfigPayload(
            wechat_push_url="http://gateway.local/api/push",
            douban_cookie="dbcl2=example-cookie",
            smzdm_cookie="smzdm=example-cookie",
            wechat_push_token="secret-token-value",
            wechat_target_id="o9cq800nb1_O0PDsDrF1X4gaT_yI@im.wechat",
        )
    )

    masked = store.load_view(reveal=False)
    revealed = store.load_view(reveal=True)

    assert masked.revealed is False
    assert masked.values.wechat_push_url == "http://gateway.local/api/push"
    assert masked.values.wechat_push_token != "secret-token-value"
    assert masked.values.wechat_target_id != "o9cq800nb1_O0PDsDrF1X4gaT_yI@im.wechat"
    assert masked.configured["wechat_push_token"] is True
    assert revealed.revealed is True
    assert revealed.values.wechat_push_token == "secret-token-value"
