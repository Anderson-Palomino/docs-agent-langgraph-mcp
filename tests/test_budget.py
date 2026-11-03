import pytest

from docs_agent.budget import (
    KIND_ASK,
    KIND_INGEST,
    BudgetExceeded,
    check_budget,
    record_usage,
    tokens_used_today,
)

pytestmark = pytest.mark.integration


def test_record_accumulates(db_conn):
    record_usage(db_conn, KIND_ASK, 100)
    record_usage(db_conn, KIND_ASK, 50)
    assert tokens_used_today(db_conn, KIND_ASK) == 150
    assert tokens_used_today(db_conn, KIND_INGEST) == 0


def test_check_budget_at_limit_raises(db_conn):
    record_usage(db_conn, KIND_ASK, 1000)
    with pytest.raises(BudgetExceeded) as e:
        check_budget(db_conn, KIND_ASK, limit=1000)
    assert e.value.used == 1000 and e.value.limit == 1000


def test_check_budget_under_limit_ok(db_conn):
    record_usage(db_conn, KIND_ASK, 999)
    check_budget(db_conn, KIND_ASK, limit=1000)
