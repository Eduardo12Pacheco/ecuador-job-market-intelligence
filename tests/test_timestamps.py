"""Pruebas del contrato de detección y parseo de unidades de marca de tiempo.

El accesorio trae valores de 10 dígitos en segundos Unix mientras que la
documentación publicada de la API menciona milisegundos; el adaptador debe
detectar la unidad de forma defensiva, parsear ambas y rechazar los valores
inverosímiles en lugar de interpretarlos silenciosamente.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from job_market_intelligence.ingestion.errors import TimestampError
from job_market_intelligence.ingestion.models import TimestampUnit
from job_market_intelligence.ingestion.parser import parse_unix_timestamp

EXPECTED_UTC = datetime(2026, 7, 31, 20, 23, 57, tzinfo=UTC)


class TestParseUnixTimestamp:
    def test_unix_seconds(self) -> None:
        parsed, unit = parse_unix_timestamp(1785529437)
        assert parsed == EXPECTED_UTC
        assert unit is TimestampUnit.UNIX_SECONDS

    def test_unix_milliseconds(self) -> None:
        parsed, unit = parse_unix_timestamp(1785529437000)
        assert parsed == EXPECTED_UTC
        assert unit is TimestampUnit.UNIX_MILLISECONDS

    def test_numeric_string(self) -> None:
        parsed, unit = parse_unix_timestamp("1785529437")
        assert parsed == EXPECTED_UTC
        assert unit is TimestampUnit.UNIX_SECONDS

    def test_none_is_null_timestamp(self) -> None:
        parsed, unit = parse_unix_timestamp(None)
        assert parsed is None
        assert unit is TimestampUnit.UNKNOWN

    @pytest.mark.parametrize(
        "value",
        [
            0,
            1,
            -5,
            999_999_999,  # 9 dígitos: fuera de la banda documentada de segundos de 10 dígitos
            12_345_678_901,  # 11 dígitos: ni segundos ni milisegundos
            1_785_529_437_0000,  # 14 dígitos: fuera de la banda de milisegundos de 13 dígitos
            "not-a-number",
            True,  # bool es una subclase de int; no debe aceptarse
            1.5,
            1_785_529_437.5,
        ],
    )
    def test_implausible_values_are_rejected(self, value) -> None:
        with pytest.raises(TimestampError):
            parse_unix_timestamp(value)
