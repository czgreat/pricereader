from app.models.evaluation import CandidateInput
from app.services.config_loader import reload_config_snapshot
from app.services.rule_engine import evaluate_candidate


def test_rule_engine_matches_orijen_rule() -> None:
    snapshot = reload_config_snapshot()
    payload = CandidateInput(
        source_key="douban_group_656297_tab_42899",
        title="渴望猫粮 2.7kg*2 到手379元",
        body="车主自用闲置，orijen 5.4kg，猫粮整包。",
    )

    result = evaluate_candidate(payload, snapshot=snapshot)
    matched = {item.rule_key: item for item in result.matches}

    assert matched["orijen_cat_5_4kg"].matched is True
    assert matched["orijen_cat_5_4kg"].used_price is not None


def test_rule_engine_rejects_high_price() -> None:
    snapshot = reload_config_snapshot()
    payload = CandidateInput(
        source_key="smzdm_keywords_primary",
        title="欧乐B iO3 电动牙刷 到手399元",
        body="整机好价，自用备用机。",
    )

    result = evaluate_candidate(payload, snapshot=snapshot)
    matched = {item.rule_key: item for item in result.matches}

    assert matched["oralb_io3"].matched is False
    assert matched["oralb_io3"].reason == "price_not_matched"


def test_rule_engine_rejects_too_low_price_when_min_configured() -> None:
    snapshot = reload_config_snapshot()
    target = next(item for item in snapshot.rules if item.rule_key == "oralb_io3")
    target.price.min_cny = 250
    payload = CandidateInput(
        source_key="smzdm_keywords_primary",
        title="欧乐B iO3 电动牙刷 到手199元",
        body="看起来像好价，但价格过低，可能是引流活动。",
    )

    result = evaluate_candidate(payload, snapshot=snapshot)
    matched = {item.rule_key: item for item in result.matches}

    assert matched["oralb_io3"].matched is False
    assert matched["oralb_io3"].reason == "price_not_matched"


def test_rule_engine_rejects_excluded_keyword() -> None:
    snapshot = reload_config_snapshot()
    payload = CandidateInput(
        source_key="douban_group_700687_tab_53514",
        title="渴望狗粮 5.4kg 299元",
        body="便宜出。",
    )

    result = evaluate_candidate(payload, snapshot=snapshot)
    matched = {item.rule_key: item for item in result.matches}

    assert matched["orijen_cat_5_4kg"].matched is False
    assert matched["orijen_cat_5_4kg"].reason == "excluded_keyword_hit"
