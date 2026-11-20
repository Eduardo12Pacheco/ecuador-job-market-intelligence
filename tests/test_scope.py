"""Pruebas del contrato de clasificación del alcance de ubicación.

Cubre la tabla de clasificación de ``locationRestrictions`` de
``docs/ingestion/himalayas-adapter-contract.md`` y la regla dura de que las
restricciones de zona horaria nunca son evidencia geográfica.
"""

from __future__ import annotations

from datetime import UTC, datetime

from job_market_intelligence.ingestion.models import LocationScope
from job_market_intelligence.ingestion.parser import (
    classify_location_scope,
    parse_job,
)

CAPTURED_AT = datetime(2026, 8, 2, 17, 3, 28, tzinfo=UTC)


class TestClassifyLocationScope:
    def test_explicit_ecuador_is_case_insensitive(self) -> None:
        assert classify_location_scope(["Ecuador"]) is LocationScope.EXPLICIT_EC
        assert classify_location_scope(["ecuador"]) is LocationScope.EXPLICIT_EC
        assert classify_location_scope(["ECUADOR", "Mexico"]) is LocationScope.EXPLICIT_EC
        assert classify_location_scope(["  Ecuador  "]) is LocationScope.EXPLICIT_EC
        assert classify_location_scope(["Mexico", "Peru", "Ecuador"]) is LocationScope.EXPLICIT_EC

    def test_explicit_empty_list_is_worldwide(self) -> None:
        assert classify_location_scope([]) is LocationScope.WORLDWIDE

    def test_non_empty_list_without_ecuador_is_other_country(self) -> None:
        assert classify_location_scope(["Mexico", "Peru"]) is LocationScope.OTHER_COUNTRY
        assert classify_location_scope(["United States"]) is LocationScope.OTHER_COUNTRY

    def test_missing_null_and_malformed_are_unknown(self) -> None:
        assert classify_location_scope(None) is LocationScope.UNKNOWN
        assert classify_location_scope("Ecuador") is LocationScope.UNKNOWN
        assert classify_location_scope({"country": "Ecuador"}) is LocationScope.UNKNOWN
        assert classify_location_scope(42) is LocationScope.UNKNOWN

    def test_non_string_list_items_never_match_ecuador(self) -> None:
        assert classify_location_scope([1, 2, 3]) is LocationScope.OTHER_COUNTRY

    def test_ecuador_among_non_string_items_still_wins(self) -> None:
        assert classify_location_scope([1, "Ecuador", 3]) is LocationScope.EXPLICIT_EC


class TestNoTimezoneInference:
    def test_timezone_restrictions_alone_never_infer_ecuador(self) -> None:
        job = {
            "guid": "https://himalayas.app/companies/x/jobs/tz-only",
            "applicationLink": "https://himalayas.app/companies/x/jobs/tz-only",
            "title": "Timezone only",
            "companyName": "Acme",
            "description": "<p>x</p>",
            "locationRestrictions": None,
            "timezoneRestrictions": [-5, -6],
            "pubDate": 1785529437,
            "expiryDate": 1786187742,
        }
        parsed = parse_job(job, snapshot_id="snap", captured_at=CAPTURED_AT)
        assert parsed.location_scope is LocationScope.UNKNOWN
        assert parsed.timezone_restrictions_raw == [-5, -6]

    def test_ecuador_wins_despite_any_timezone_restrictions(self) -> None:
        job = {
            "guid": "https://himalayas.app/companies/x/jobs/tz-ec",
            "applicationLink": "https://himalayas.app/companies/x/jobs/tz-ec",
            "title": "TZ with Ecuador",
            "companyName": "Acme",
            "description": "<p>x</p>",
            "locationRestrictions": ["Ecuador"],
            "timezoneRestrictions": [-5, -6],
            "pubDate": 1785529437,
            "expiryDate": 1786187742,
        }
        parsed = parse_job(job, snapshot_id="snap", captured_at=CAPTURED_AT)
        assert parsed.location_scope is LocationScope.EXPLICIT_EC

    def test_empty_restrictions_with_timezones_is_worldwide(self) -> None:
        job = {
            "guid": "https://himalayas.app/companies/x/jobs/tz-worldwide",
            "applicationLink": "https://himalayas.app/companies/x/jobs/tz-worldwide",
            "title": "TZ worldwide",
            "companyName": "Acme",
            "description": "<p>x</p>",
            "locationRestrictions": [],
            "timezoneRestrictions": [-11, 14],
            "pubDate": 1785529437,
            "expiryDate": 1786187742,
        }
        parsed = parse_job(job, snapshot_id="snap", captured_at=CAPTURED_AT)
        assert parsed.location_scope is LocationScope.WORLDWIDE


def test_parse_job_rejects_location_scope_mutations_for_unknown_inputs() -> None:
    # Salvaguarda: parse_job sobre un empleo sin locationRestrictions no debe
    # coercionar a una lista vacía / worldwide.
    job = {
        "guid": "g",
        "applicationLink": "a",
        "title": "t",
        "companyName": "c",
        "description": "<p>d</p>",
        "pubDate": 1785529437,
        "expiryDate": 1786187742,
    }
    parsed = parse_job(job, snapshot_id="snap", captured_at=CAPTURED_AT)
    assert parsed.location_scope is LocationScope.UNKNOWN
    assert "missing_location_restrictions" in parsed.quality_flags
