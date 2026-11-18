"""Daily token budget, accounted in Postgres. The day is the UTC date."""

from typing import TYPE_CHECKING

import psycopg

if TYPE_CHECKING:  # solo para el tipo: `config` no importa `budget`, pero así no se acopla
    from docs_agent.config import Settings

KIND_ASK = "ask"
KIND_EVAL = "eval"  # D39: la evaluación gasta su propio cupo diario, no el de `/ask`
KIND_INGEST = "ingest"
KIND_MCP = "mcp"

_UTC_TODAY = "(now() at time zone 'utc')::date"


class BudgetExceeded(Exception):
    def __init__(self, used: int, limit: int):
        super().__init__(f"daily token budget exceeded: used {used} of {limit}")
        self.used = used
        self.limit = limit


def tokens_used_today(conn: psycopg.Connection, kind: str) -> int:
    row = conn.execute(
        f"SELECT tokens FROM token_usage WHERE day = {_UTC_TODAY} AND kind = %s",
        (kind,),
    ).fetchone()
    return int(row[0]) if row else 0


def record_usage(conn: psycopg.Connection, kind: str, tokens: int) -> None:
    conn.execute(
        f"""
        INSERT INTO token_usage (day, kind, tokens) VALUES ({_UTC_TODAY}, %s, %s)
        ON CONFLICT (day, kind)
        DO UPDATE SET tokens = token_usage.tokens + excluded.tokens
        """,
        (kind, tokens),
    )
    conn.commit()


def check_budget(conn: psycopg.Connection, kind: str, limit: int) -> None:
    used = tokens_used_today(conn, kind)
    if used >= limit:
        raise BudgetExceeded(used, limit)


def daily_limit(settings: "Settings", kind: str) -> int:
    """Tope diario de tokens del kind: único lugar del mapeo kind→límite (`ask`, `eval`, `mcp`); un kind desconocido lanza `ValueError`."""
    if kind == KIND_ASK:
        return settings.ask_daily_token_budget
    if kind == KIND_EVAL:
        return settings.eval_daily_token_budget
    if kind == KIND_MCP:
        return settings.mcp_daily_token_budget
    raise ValueError(f"kind sin tope diario: {kind!r}")
