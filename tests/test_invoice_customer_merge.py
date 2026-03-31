from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app"
if str(APP_PATH) not in sys.path:
    sys.path.append(str(APP_PATH))

data_module = importlib.import_module("data")
merge_module = importlib.import_module("invoice_customer_merge")

Company = data_module.Company
Customer = data_module.Customer
get_session = data_module.get_session
merge_customer_from_new_id = merge_module.merge_customer_from_new_id
parse_new_customer_id = merge_module.parse_new_customer_id


def test_parse_new_customer_id() -> None:
    assert parse_new_customer_id(None) is None
    assert parse_new_customer_id(42) == 42
    assert parse_new_customer_id("7") == 7
    assert parse_new_customer_id("x") is None
    assert parse_new_customer_id("") is None


def test_merge_appends_customer_same_company() -> None:
    with get_session() as session:
        comp = Company(name="Merge Co A", next_invoice_nr=1)
        session.add(comp)
        session.commit()
        session.refresh(comp)
        cust = Customer(
            company_id=int(comp.id),
            kdnr=1,
            name="Neu",
            strasse="S1",
            plz="1",
            ort="O",
        )
        session.add(cust)
        session.commit()
        session.refresh(cust)
        cid = int(cust.id or 0)

    all_customers: list = []
    customers_by_id: dict = {}
    with get_session() as session:
        merge_customer_from_new_id(
            session,
            comp_id=int(comp.id),
            all_customers=all_customers,
            customers_by_id=customers_by_id,
            new_customer_id=cid,
        )
    assert cid in customers_by_id
    assert customers_by_id[cid].name == "Neu"
    assert len(all_customers) == 1


def test_merge_ignores_other_company() -> None:
    with get_session() as session:
        comp_a = Company(name="Co A", next_invoice_nr=1)
        comp_b = Company(name="Co B", next_invoice_nr=1)
        session.add(comp_a)
        session.add(comp_b)
        session.commit()
        session.refresh(comp_a)
        session.refresh(comp_b)
        cust_b = Customer(
            company_id=int(comp_b.id),
            kdnr=1,
            name="Nur B",
            strasse="",
            plz="",
            ort="",
        )
        session.add(cust_b)
        session.commit()
        session.refresh(cust_b)
        bid = int(cust_b.id or 0)

    all_customers: list = []
    customers_by_id: dict = {}
    with get_session() as session:
        merge_customer_from_new_id(
            session,
            comp_id=int(comp_a.id),
            all_customers=all_customers,
            customers_by_id=customers_by_id,
            new_customer_id=bid,
        )
    assert customers_by_id == {}
    assert all_customers == []


def test_merge_ignores_unknown_id() -> None:
    with get_session() as session:
        comp = Company(name="Co X", next_invoice_nr=1)
        session.add(comp)
        session.commit()
        session.refresh(comp)

    all_customers: list = []
    customers_by_id: dict = {}
    with get_session() as session:
        merge_customer_from_new_id(
            session,
            comp_id=int(comp.id),
            all_customers=all_customers,
            customers_by_id=customers_by_id,
            new_customer_id=999_999_999,
        )
    assert customers_by_id == {}
    assert all_customers == []


def test_merge_noop_if_already_in_map() -> None:
    with get_session() as session:
        comp = Company(name="Co Y", next_invoice_nr=1)
        session.add(comp)
        session.commit()
        session.refresh(comp)
        cust = Customer(
            company_id=int(comp.id),
            kdnr=1,
            name="Eins",
            strasse="",
            plz="",
            ort="",
        )
        session.add(cust)
        session.commit()
        session.refresh(cust)
        cid = int(cust.id or 0)

    all_customers = [cust]
    customers_by_id = {cid: cust}
    with get_session() as session:
        merge_customer_from_new_id(
            session,
            comp_id=int(comp.id),
            all_customers=all_customers,
            customers_by_id=customers_by_id,
            new_customer_id=cid,
        )
    assert len(all_customers) == 1
    assert list(customers_by_id.keys()) == [cid]
