import psycopg
from pgvector.psycopg import register_vector

from docs_agent.config import get_settings


def connect(database_url: str | None = None) -> psycopg.Connection:
    """Open a connection with the pgvector adapter registered (autocommit off)."""
    conn = psycopg.connect(database_url or get_settings().database_url, connect_timeout=5)
    register_vector(conn)
    return conn
