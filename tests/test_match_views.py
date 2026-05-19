from app.models.evaluation import CandidateInput
from app.models.source_items import SourceItem
from app.services.rule_engine import evaluate_candidate
from app.services.storage import SourceItemRepository


def test_list_matched_items_returns_joined_view(tmp_path) -> None:
    repo = SourceItemRepository(db_path=tmp_path / "matches.db")
    item = SourceItem(
        source_key="smzdm_keywords_primary",
        external_id="match-1",
        title="欧乐B iO3 电动牙刷 到手339元",
        url="https://www.smzdm.com/p/match-1/",
        source_type="smzdm_feed",
        summary="整机好价，适合自用。",
    )
    repo.upsert_items(item.source_key, "smzdm", [item], requested_items=1)
    evaluation = evaluate_candidate(
        CandidateInput(
            source_key=item.source_key,
            external_id=item.external_id,
            title=item.title,
            body=item.summary,
            url=item.url,
        )
    )
    repo.write_evaluation_records(item, evaluation)

    matches = repo.list_matched_items(limit=10)

    assert len(matches) == 1
    assert matches[0].rule_key == "oralb_io3"
    assert matches[0].title == item.title
