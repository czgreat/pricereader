from app.services.extractors import extract_spec_candidates


def test_extract_spec_candidates_supports_lb_and_pound() -> None:
    text = "爱肯拿猫粮 11.9lb，百利高蛋白 9.9磅，适合囤货。"
    result = extract_spec_candidates(text, source_field="title")
    grams = sorted(item.total_grams for item in result)

    assert any(5390 <= value <= 5405 for value in grams)
    assert any(4490 <= value <= 4505 for value in grams)
