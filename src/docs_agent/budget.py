"""Daily token budget, accounted in Postgres. The day is the UTC date."""

import psycopg

KIND_ASK = "ask"
KIND_INGEST = "ingest"

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
