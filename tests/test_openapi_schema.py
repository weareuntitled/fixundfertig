from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

# Trigger app.api.__init__ so sys.path is set up.
importlib.import_module("app.api")

import internal  # noqa: E402
import customers  # noqa: E402
import auth as auth_module  # noqa: E402
import invoices as invoices_module  # noqa: E402


EXPECTED_PATHS = {
    # internal
    "/api/address-autocomplete": {"get"},
    # customers
    "/api/customers": {"get", "post"},
    "/api/customers/{customer_id}": {"get", "put", "delete"},
    # auth
    "/api/auth/login": {"post"},
    "/api/auth/logout": {"post"},
    "/api/auth/me": {"get"},
    # invoices
    "/api/invoices": {"get"},
    "/api/invoices/{invoice_id}": {"get"},
    "/api/invoices/{invoice_id}/status": {"put"},
    "/api/invoices/preview-pdf": {"post"},
}


def _build_combined_app() -> FastAPI:
    """Build a FastAPI app with all extracted routers — mirrors main.py's include_router."""
    app = FastAPI(title="FixundFertig M0-Block API")
    app.include_router(internal.router)
    app.include_router(customers.router)
    app.include_router(auth_module.router)
    app.include_router(invoices_module.router)
    return app


def test_openapi_schema_is_generated() -> None:
    app = _build_combined_app()
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "paths" in schema


def test_openapi_schema_contains_all_extracted_endpoints() -> None:
    app = _build_combined_app()
    client = TestClient(app)
    response = client.get("/openapi.json")
    schema = response.json()
    actual_paths = {p: set(schema["paths"][p].keys()) for p in schema["paths"]}
    for expected_path, expected_methods in EXPECTED_PATHS.items():
        assert expected_path in actual_paths, f"Missing path: {expected_path}"
        actual_methods = actual_paths[expected_path]
        assert expected_methods.issubset(actual_methods), (
            f"Path {expected_path}: expected methods {expected_methods}, got {actual_methods}"
        )


def test_openapi_schema_includes_request_and_response_schemas() -> None:
    app = _build_combined_app()
    client = TestClient(app)
    response = client.get("/openapi.json")
    schema = response.json()
    components = schema.get("components", {}).get("schemas", {})
    # CustomerCreate, CustomerUpdate, CustomerRead, LoginRequest, LoginResponse, UserPublic,
    # InvoiceItem, InvoiceDraft, InvoiceRead, InvoiceStatusUpdate
    for expected in ("CustomerCreate", "CustomerUpdate", "CustomerRead",
                     "LoginRequest", "LoginResponse", "UserPublic",
                     "InvoiceItem", "InvoiceDraft", "InvoiceRead", "InvoiceStatusUpdate"):
        assert expected in components, f"Missing schema component: {expected}"


def test_login_endpoint_documented_in_openapi() -> None:
    app = _build_combined_app()
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    login = schema["paths"]["/api/auth/login"]["post"]
    assert "requestBody" in login
    assert "responses" in login
    assert "200" in login["responses"]
    assert "401" in login["responses"]


def test_customers_list_endpoint_documented() -> None:
    app = _build_combined_app()
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    list_op = schema["paths"]["/api/customers"]["get"]
    assert "200" in list_op["responses"]


def test_openapi_schema_no_unresolved_refs() -> None:
    """Pydantic must resolve all $ref to components — otherwise the schema is broken."""
    import json
    app = _build_combined_app()
    client = TestClient(app)
    schema_text = client.get("/openapi.json").text
    schema = json.loads(schema_text)
    # Walk through the schema and check that all $ref resolve
    components = schema.get("components", {}).get("schemas", {})

    def walk(node, path=""):
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                assert ref.startswith("#/components/"), f"Unresolvable $ref: {ref} at {path}"
                parts = ref.lstrip("#/").split("/")
                target = schema
                for p in parts:
                    target = target.get(p, {}) if isinstance(target, dict) else None
                assert target is not None, f"$ref target not found: {ref} at {path}"
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(schema)
