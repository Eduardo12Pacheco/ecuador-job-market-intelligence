"""Accesorios offline compartidos para las pruebas del adaptador Himalayas.

Todas las pruebas se ejecutan contra manejadores de ``httpx.MockTransport``;
ninguna prueba toca la red ni el sistema de archivos más allá de leer los
accesorios versionados bajo ``data/sample``:

- ``himalayas_browse_page_1.json`` — página 1 del endpoint de exploración
  del feed completo ``/jobs/api`` (limit=20, offset=0), el accesorio offline
  canónico para validar adaptador y analizador.
- ``himalayas_ec_page_1.json`` — página exploratoria de ``/jobs/api/search``
  filtrada por Ecuador, conservada solo como accesorio exploratorio.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from job_market_intelligence.ingestion.adapter import HimalayaAdapter

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_JSON = REPO_ROOT / "data" / "sample" / "himalayas_ec_page_1.json"
FIXTURE_SHA256 = "b39e32b841f8b277c4b94fc4888d17cb30eb725f6dbb1e31e6f8ded29c26c0cf"
BROWSE_SAMPLE_JSON = REPO_ROOT / "data" / "sample" / "himalayas_browse_page_1.json"
BROWSE_METADATA_JSON = REPO_ROOT / "data" / "sample" / "himalayas_browse_page_1.metadata.json"
BROWSE_FIXTURE_SHA256 = "f722f465e4c45735b1dcf7ba23d78e50e9a485b4d33f699ca4a5c01d49832754"
BROWSE_ENDPOINT = "https://himalayas.app/jobs/api"

# Reloj fijo para que la clasificación de caducidad nunca dependa del tiempo real.
FIXED_CAPTURED_AT = datetime(2026, 8, 2, 17, 3, 28, 193510, tzinfo=timezone.utc)
JSON_HEADERS = {"content-type": "application/json"}


@pytest.fixture(scope="session")
def fixture_bytes() -> bytes:
    return SAMPLE_JSON.read_bytes()


@pytest.fixture(scope="session")
def fixture_payload(fixture_bytes: bytes) -> dict:
    return json.loads(fixture_bytes)


@pytest.fixture(scope="session")
def browse_fixture_bytes() -> bytes:
    return BROWSE_SAMPLE_JSON.read_bytes()


@pytest.fixture(scope="session")
def browse_fixture_payload(browse_fixture_bytes: bytes) -> dict:
    return json.loads(browse_fixture_bytes)


def default_job(offset: int, index: int, **overrides) -> dict:
    """Una carga útil de empleo de Himalayas sintética, completa y válida."""
    job = {
        "guid": f"https://himalayas.app/companies/acme/jobs/{offset}-{index}",
        "applicationLink": f"https://himalayas.app/companies/acme/jobs/{offset}-{index}",
        "title": f"Job {offset}-{index}",
        "excerpt": "A short excerpt",
        "companyName": "Acme",
        "companySlug": "acme",
        "companyLogo": "https://himalayas.app/logo.png",
        "employmentType": "Full Time",
        "minSalary": None,
        "maxSalary": None,
        "salaryPeriod": "annual",
        "seniority": ["Mid-level"],
        "currency": "USD",
        "locationRestrictions": ["Ecuador"],
        "timezoneRestrictions": [-5, -6],
        "categories": ["Engineer"],
        "parentCategories": ["Developer"],
        "description": "<p>Description</p>",
        "pubDate": 1785529437,
        "expiryDate": 1786187742,
    }
    job.update(overrides)
    return job


def make_page(offset: int, count: int, total: int, *, updated_at: int = 1785529437, jobs: list | None = None) -> dict:
    """Construye una carga útil de página sintética para ``/jobs/api``."""
    if jobs is None:
        jobs = [default_job(offset, i) for i in range(count)]
    return {
        "comments": "synthetic test page",
        "updatedAt": updated_at,
        "offset": offset,
        "limit": 20,
        "totalCount": total,
        "jobs": jobs,
    }


def encode(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def transport_for(pages: dict[int, bytes | dict]) -> httpx.MockTransport:
    """Transporte simulado que sirve los bytes exactos para cada offset solicitado."""

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params.get("offset", 0))
        page = pages.get(offset)
        if page is None:
            return httpx.Response(404, content=b'{"error": "not found"}')
        if isinstance(page, bytes):
            return httpx.Response(200, content=page, headers=JSON_HEADERS)
        return httpx.Response(200, content=encode(page), headers=JSON_HEADERS)

    return httpx.MockTransport(handler)


def make_adapter(pages: dict[int, bytes | dict]) -> tuple[HimalayaAdapter, httpx.Client]:
    client = httpx.Client(transport=transport_for(pages))
    adapter = HimalayaAdapter(client=client, clock=lambda: FIXED_CAPTURED_AT)
    return adapter, client
