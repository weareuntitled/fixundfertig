from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

internal_module = importlib.import_module("app.api.internal")
format_nominatim_result = internal_module.format_nominatim_result
build_internal_router = getattr(internal_module, "router", None)


def _build_test_app() -> FastAPI:
    """Mount the internal router in a fresh FastAPI app for isolated testing."""
    app = FastAPI()
    if build_internal_router is not None:
        app.include_router(build_internal_router)
    return app


def test_format_nominatim_result_extracts_road_house_number_city_zip_country() -> None:
    item = {
        "display_name": "Beispielstraße 1, 10115 Berlin, Deutschland",
        "address": {
            "road": "Beispielstraße",
            "house_number": "1",
            "postcode": "10115",
            "city": "Berlin",
            "country_code": "de",
            "country": "Deutschland",
        },
    }
    result = format_nominatim_result(item)
    assert result == {
        "label": "Beispielstraße 1, 10115 Berlin, Deutschland",
        "street": "Beispielstraße 1",
        "zip": "10115",
        "city": "Berlin",
        "country": "Deutschland",
    }


def test_format_nominatim_result_falls_back_to_town_when_no_city() -> None:
    item = {
        "address": {
            "road": "Hauptweg",
            "house_number": "5",
            "postcode": "20095",
            "town": "Hamburg",
            "country_code": "de",
        }
    }
    result = format_nominatim_result(item)
    assert result["street"] == "Hauptweg 5"
    assert result["zip"] == "20095"
    assert result["city"] == "Hamburg"
    assert result["country"] == "DE"


def test_format_nominatim_result_uses_display_name_when_no_address_parts() -> None:
    item = {"display_name": "Freiburg im Breisgau, Deutschland", "address": {}}
    result = format_nominatim_result(item)
    assert result["label"] == "Freiburg im Breisgau, Deutschland"
    assert result["street"] == ""
    assert result["city"] == ""
    assert result["country"] == ""


@pytest.mark.skipif(build_internal_router is None, reason="app.api.internal.router not yet extracted")
def test_address_autocomplete_short_query_returns_empty_without_calling_nominatim() -> None:
    client = TestClient(_build_test_app())
    with patch("app.api.internal.urlopen") as mock_urlopen:
        response = client.get("/api/address-autocomplete", params={"q": "ab", "country": "DE"})
    assert response.status_code == 200
    assert response.json() == []
    mock_urlopen.assert_not_called()


@pytest.mark.skipif(build_internal_router is None, reason="app.api.internal.router not yet extracted")
def test_address_autocomplete_calls_nominatim_and_returns_formatted_results() -> None:
    fake_response = MagicMock()
    fake_response.read.return_value = b'[{"display_name":"X","address":{"road":"R","postcode":"12345","city":"C","country_code":"de"}}]'
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False
    with patch("app.api.internal.urlopen", return_value=fake_response):
        client = TestClient(_build_test_app())
        response = client.get("/api/address-autocomplete", params={"q": "Musterstadt", "country": "DE"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["street"] == "R"
    assert data[0]["zip"] == "12345"
    assert data[0]["city"] == "C"


@pytest.mark.skipif(build_internal_router is None, reason="app.api.internal.router not yet extracted")
def test_address_autocomplete_returns_empty_on_nominatim_failure() -> None:
    with patch("app.api.internal.urlopen", side_effect=Exception("network down")):
        client = TestClient(_build_test_app())
        response = client.get("/api/address-autocomplete", params={"q": "Berlin", "country": "DE"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.skipif(build_internal_router is None, reason="app.api.internal.router not yet extracted")
def test_address_autocomplete_returns_empty_when_nominatim_payload_is_not_list() -> None:
    fake_response = MagicMock()
    fake_response.read.return_value = b'{"error":"bad"}'
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False
    with patch("app.api.internal.urlopen", return_value=fake_response):
        client = TestClient(_build_test_app())
        response = client.get("/api/address-autocomplete", params={"q": "Berlin", "country": "DE"})
    assert response.status_code == 200
    assert response.json() == []
