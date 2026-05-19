from __future__ import annotations

import re

from app.models.evaluation import PriceCandidate, SpecCandidate


_BUNDLE_SPEC_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|斤|lb|磅)\s*[*xX×]\s*(?P<count>\d+)",
    re.IGNORECASE,
)
_SINGLE_SPEC_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|斤|lb|磅)", re.IGNORECASE)
_PRICE_PATTERNS = [
    re.compile(r"[¥￥]\s*(?P<price>\d{1,5}(?:\.\d{1,2})?)"),
    re.compile(r"(?P<price>\d{2,5}(?:\.\d{1,2})?)\s*元"),
    re.compile(r"(?:到手|券后|仅需|低至|实付|售价|价格)\s*(?P<price>\d{2,5}(?:\.\d{1,2})?)"),
]


def _unit_to_grams(value: float, unit: str) -> int:
    normalized = unit.lower()
    if normalized == "kg":
        return round(value * 1000)
    if normalized == "g":
        return round(value)
    if normalized == "斤":
        return round(value * 500)
    if normalized == "lb":
        return round(value * 453.59237)
    if normalized == "磅":
        return round(value * 453.59237)
    raise ValueError(f"Unsupported weight unit: {unit}")


def _non_overlapping_spans(bundle_matches: list[re.Match[str]]) -> list[tuple[int, int]]:
    return [match.span() for match in bundle_matches]


def extract_spec_candidates(text: str, *, source_field: str) -> list[SpecCandidate]:
    candidates: list[SpecCandidate] = []
    bundle_matches = list(_BUNDLE_SPEC_RE.finditer(text))

    for match in bundle_matches:
        value = float(match.group("value"))
        count = int(match.group("count"))
        total_grams = _unit_to_grams(value, match.group("unit")) * count
        candidates.append(
            SpecCandidate(
                raw_text=match.group(0),
                total_grams=total_grams,
                source_field=source_field,
                expression_type="bundle",
            )
        )

    occupied = _non_overlapping_spans(bundle_matches)
    for match in _SINGLE_SPEC_RE.finditer(text):
        start, end = match.span()
        if any(start >= left and end <= right for left, right in occupied):
            continue
        value = float(match.group("value"))
        total_grams = _unit_to_grams(value, match.group("unit"))
        candidates.append(
            SpecCandidate(
                raw_text=match.group(0),
                total_grams=total_grams,
                source_field=source_field,
                expression_type="single",
            )
        )

    deduped: dict[tuple[str, int, str], SpecCandidate] = {}
    for item in candidates:
        deduped[(item.raw_text.lower(), item.total_grams, item.expression_type)] = item
    return list(deduped.values())


def extract_price_candidates(text: str, *, source_field: str) -> list[PriceCandidate]:
    candidates: dict[tuple[str, float], PriceCandidate] = {}
    for pattern in _PRICE_PATTERNS:
        for match in pattern.finditer(text):
            price = float(match.group("price"))
            snippet = match.group(0).strip()
            if price <= 0:
                continue
            if any(unit in snippet.lower() for unit in ("kg", "斤", "g", "lb", "磅")):
                continue
            key = (snippet.lower(), price)
            candidates[key] = PriceCandidate(
                raw_text=snippet,
                amount_cny=price,
                source_field=source_field,
            )
    return sorted(candidates.values(), key=lambda item: item.amount_cny)
