import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import pytest
from mcp import MCPError
from mcp.types import CallToolResult, TextContent
from mcp_types import CONNECTION_CLOSED, INVALID_PARAMS

from docs_agent.agent.mcp_client import (
    DocsMCPClient,
    DocsServerUnavailable,
    DocsToolError,
    DocsToolTimeout,
    stdio_connect,
    stdio_params,
)
from docs_agent.config import Settings

REPO = Path(__file__).resolve().parents[2]
BODY = "https://fastapi.tiangolo.com/tutorial/body/"


class FakeSession:
    """Imita `mcp.Client` ya conectado: `call_tool` ejecuta `behavior` o devuelve un resultado estructurado."""

    def __init__(self, idx: int, behavior=None):
        self.idx = idx
        self.behavior = behavior
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name, arguments=None, read_timeout_seconds=None):
        self.calls.append((name, arguments))
        if self.behavior is not None:
            return await self.behavior()
        return CallToolResult(content=[], structured_content={"session": self.idx, "tool": name})


class FakeConnect:
    """Fábrica `connect()` que entrega una sesión nueva por invocación; `behaviors[i]` gobierna la sesión i."""

    def __init__(self, *behaviors):
        self.behaviors = list(behaviors)
        self.sessions: list[FakeSession] = []
        self.closed: list[int] = []

    def __call__(self):
        idx = len(self.sessions)
        session = FakeSession(idx, self.behaviors[idx] if idx < len(self.behaviors) else None)
        self.sessions.append(session)

        @asynccontextmanager
        async def cm():
            # Como el SDK: un cancel scope abierto en __aenter__ que debe cerrarse en la misma tarea.
            with anyio.CancelScope():
                try:
                    yield session
                finally:
                    self.closed.append(idx)

        return cm()

    @property
    def count(self) -> int:
        return len(self.sessions)


def raising(exc):
    async def behavior():
        raise exc

    return behavior


async def sleeping():
    await anyio.sleep(10)


def tool_error_once():
    """Error de herramienta solo en la 1.ª llamada; después la sesión responde normal."""
    fired = False

    async def behavior():
        nonlocal fired
        if fired:
            return CallToolResult(content=[], structured_content={"session": 0, "tool": "list_sources"})
        fired = True
        return CallToolResult(
            content=[TextContent(type="text", text="Error executing tool get_section: Unknown section URL: x")],
            is_error=True,
        )

    return behavior


def connection_closed() -> MCPError:
    return MCPError(code=CONNECTION_CLOSED, message="Connection closed")


@pytest.mark.anyio
async def test_session_is_reused():
    connect = FakeConnect()
    client = DocsMCPClient(connect, call_timeout_s=1)
    assert await client.call("list_sources", {}) == {"session": 0, "tool": "list_sources"}
    assert await client.call("get_section", {"url": BODY}) == {"session": 0, "tool": "get_section"}
    assert connect.count == 1
    assert connect.sessions[0].calls == [("list_sources", {}), ("get_section", {"url": BODY})]
    await client.aclose()
    assert connect.closed == [0]


@pytest.mark.anyio
async def test_reconnects_once_when_process_dies():
    connect = FakeConnect(raising(anyio.ClosedResourceError()))
    client = DocsMCPClient(connect, call_timeout_s=1)
    assert await client.call("list_sources", {}) == {"session": 1, "tool": "list_sources"}
    assert connect.count == 2
    assert connect.closed == [0]  # la sesión muerta se cerró antes de reconectar
    await client.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exc",
    [
        anyio.BrokenResourceError(),
        anyio.EndOfStream(),
        connection_closed(),
        ExceptionGroup("tg", [ExceptionGroup("tg", [connection_closed()])]),
    ],
    ids=["broken", "eos", "mcp-closed", "group"],
)
async def test_dead_process_errors_trigger_reconnect(exc):
    connect = FakeConnect(raising(exc))
    client = DocsMCPClient(connect, call_timeout_s=1)
    assert (await client.call("list_sources", {}))["session"] == 1
    await client.aclose()


@pytest.mark.anyio
async def test_gives_up_after_one_retry():
    connect = FakeConnect(raising(connection_closed()), raising(connection_closed()))
    client = DocsMCPClient(connect, call_timeout_s=1)
    with pytest.raises(DocsServerUnavailable) as info:
        await client.call("list_sources", {})
    assert not isinstance(info.value, DocsToolTimeout)
    assert connect.count == 2
    assert connect.closed == [0, 1]
    # La siguiente llamada vuelve a intentarlo con una sesión nueva.
    assert (await client.call("list_sources", {}))["session"] == 2
    await client.aclose()


@pytest.mark.anyio
async def test_connect_failure_is_unavailable():
    calls = []

    def connect():
        calls.append(1)
        raise OSError("cannot spawn")

    client = DocsMCPClient(connect, call_timeout_s=1)
    with pytest.raises(DocsServerUnavailable):
        await client.call("list_sources", {})
    assert len(calls) == 2
    await client.aclose()


@pytest.mark.anyio
async def test_timeout_raises_and_next_call_reconnects():
    connect = FakeConnect(sleeping)
    client = DocsMCPClient(connect, call_timeout_s=0.05)
    with anyio.fail_after(5):
        with pytest.raises(DocsToolTimeout) as info:
            await client.call("list_sources", {})
    assert isinstance(info.value, DocsServerUnavailable)
    assert connect.count == 1  # el timeout no reintenta
    assert connect.closed == [0]  # y descarta la sesión
    assert (await client.call("list_sources", {}))["session"] == 1
    assert connect.count == 2
    await client.aclose()


@pytest.mark.anyio
async def test_tool_error_not_retried():
    connect = FakeConnect(tool_error_once())
    client = DocsMCPClient(connect, call_timeout_s=1)
    with pytest.raises(DocsToolError) as info:
        await client.call("get_section", {"url": "x"})
    assert str(info.value) == "Error executing tool get_section: Unknown section URL: x"
    assert connect.count == 1
    assert connect.closed == []  # la sesión sigue sana y se reutiliza
    assert (await client.call("list_sources", {}))["session"] == 0
    await client.aclose()


@pytest.mark.anyio
async def test_protocol_error_is_tool_error_not_retried():
    connect = FakeConnect(raising(MCPError(code=INVALID_PARAMS, message="Unknown tool: nope")))
    client = DocsMCPClient(connect, call_timeout_s=1)
    with pytest.raises(DocsToolError, match="Unknown tool: nope"):
        await client.call("nope", {})
    assert connect.count == 1
    await client.aclose()


@pytest.mark.anyio
async def test_session_opened_and_closed_in_different_tasks():
    """El grafo llama desde tareas distintas a la que cierra: la sesión no puede depender de la tarea."""
    connect = FakeConnect()
    client = DocsMCPClient(connect, call_timeout_s=1)
    await asyncio.create_task(client.call("list_sources", {}))
    await asyncio.create_task(client.call("list_sources", {}))
    await asyncio.create_task(client.aclose())
    assert connect.count == 1
    assert connect.closed == [0]


@pytest.mark.anyio
async def test_hang_on_startup_is_bounded():
    """Un servidor colgado en el handshake no retiene la llamada más allá de ~2× el timeout (abrir + reintento)."""
    entered = []

    @asynccontextmanager
    async def hanging():
        entered.append(1)
        await anyio.sleep(60)
        yield None

    client = DocsMCPClient(hanging, call_timeout_s=0.2)
    start = time.perf_counter()
    with anyio.fail_after(10):
        with pytest.raises(DocsServerUnavailable):
            await client.call("list_sources", {})
    assert time.perf_counter() - start < 2.0  # muy por debajo de los 60 s del cuelgue; holgura para CI lento
    assert len(entered) == 2  # abrir y un reintento
    await client.aclose()


@pytest.mark.anyio
async def test_cancel_during_startup_closes_session():
    """Cancelar la petición mientras el servidor arranca no deja la tarea de la sesión colgada (ni su proceso)."""
    entered, exited = [], []

    @asynccontextmanager
    async def hanging():
        entered.append(1)
        try:
            await anyio.sleep(60)
            yield None
        finally:
            exited.append(1)

    client = DocsMCPClient(hanging, call_timeout_s=30)
    task = asyncio.create_task(client.call("list_sources", {}))
    while not entered:
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert exited == [1]
    await client.aclose()


@pytest.mark.anyio
async def test_closed_client_never_reopens():
    connect = FakeConnect()
    client = DocsMCPClient(connect, call_timeout_s=1)
    await client.call("list_sources", {})
    await client.aclose()
    with pytest.raises(DocsServerUnavailable, match="closed"):
        await client.call("list_sources", {})
    assert connect.count == 1
    assert connect.closed == [0]


def test_stdio_params_pass_env_and_scope(monkeypatch):
    monkeypatch.setenv("SOME_PARENT_VAR", "kept")
    params = stdio_params(Settings(_env_file=None), "ask")
    assert params.env["MCP_BUDGET_SCOPE"] == "ask"
    assert params.env["DATABASE_URL"] == os.environ["DATABASE_URL"]
    assert params.env["SOME_PARENT_VAR"] == "kept"
    assert params.args == ["-m", "docs_agent.mcp_server"]
    assert Path(params.cwd) == REPO
    assert (Path(params.cwd) / "pyproject.toml").is_file()


@pytest.mark.anyio
@pytest.mark.integration
async def test_real_stdio_roundtrip(seeded_corpus, monkeypatch):
    monkeypatch.setenv("FASTAPI_DOCS_REF", "test-ref")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")  # list_sources y get_section no llaman a OpenAI
    monkeypatch.setenv("LANGSMITH_TRACING", "false")  # ningún test llama a LangSmith
    connect = stdio_connect(Settings(_env_file=None), "mcp")
    client = DocsMCPClient(connect, call_timeout_s=60)
    try:
        sources = await client.call("list_sources", {})
        assert sources == {"project": "FastAPI", "version": "test-ref", "pages": 2, "chunks": 2, "sections": 4}
        section = await client.call("get_section", {"url": f"{BODY}#request-body"})
        assert "Declare a request body with a Pydantic model." in section["content"]
        with pytest.raises(DocsToolError, match="Unknown section URL"):
            await client.call("get_section", {"url": f"{BODY}#nope"})
        assert (await client.call("list_sources", {}))["chunks"] == 2  # la misma sesión sigue viva
    finally:
        await client.aclose()
