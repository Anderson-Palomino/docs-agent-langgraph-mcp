"""Cliente MCP del grafo: una sesión stdio persistente, reconexión una vez y timeout por llamada (D30).

La sesión (`mcp.Client` como context manager) vive en una tarea propia: el SDK abre task groups y cancel
scopes en `__aenter__` que deben cerrarse en la **misma** tarea, y el grafo llama desde tareas distintas a la
que cierra (`RuntimeError: Attempted to exit cancel scope in a different task`, verificado). Requiere el
backend asyncio de anyio (el de FastAPI y LangGraph).
"""

import asyncio
import logging
import os
import sys
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

import anyio
from mcp import Client, MCPError, StdioServerParameters
from mcp_types import CONNECTION_CLOSED, TextContent

from docs_agent.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]  # src/docs_agent/agent/mcp_client.py -> raíz (pyproject.toml)
logger = logging.getLogger(__name__)
CLOSE_TIMEOUT_S = 10.0  # el SDK ya acota el apagado del proceso (cierra stdin, espera, mata el árbol)

# Qué significa "el proceso del servidor murió" en mcp 2.3 sobre Windows. Medido matando el árbol del
# servidor con `taskkill /F` (script ad hoc, 2026-11-10):
#   - proceso muerto entre llamadas o durante una llamada en vuelo -> `call_tool` lanza
#     `MCPError(code=CONNECTION_CLOSED (-32000), "Connection closed")`; salir del `async with` no lanza.
#   - proceso que muere al arrancar (antes del handshake) -> `__aenter__` lanza
#     `ExceptionGroup(ExceptionGroup(MCPError(CONNECTION_CLOSED)))`: se aceptan grupos cuyas hojas sean todas
#     "proceso muerto".
#   - no lanzar el proceso (ejecutable inexistente) -> `OSError` (documentado en `stdio_client`).
# `anyio.ClosedResourceError`, `BrokenResourceError` y `EndOfStream` no aparecieron en las pruebas (el
# dispatcher los traduce a CONNECTION_CLOSED), pero son los errores de los streams del transporte y se
# mantienen por si una versión futura del SDK los deja pasar.
_DEAD_PROCESS_ERRORS: tuple[type[BaseException], ...] = (
    anyio.ClosedResourceError,
    anyio.BrokenResourceError,
    anyio.EndOfStream,
    OSError,
)

Connect = Callable[[], AbstractAsyncContextManager[Client]]


class DocsServerUnavailable(Exception):
    """El servidor MCP no responde (proceso muerto tras reintentar una vez, o timeout)."""


class DocsToolTimeout(DocsServerUnavailable):
    """La llamada superó `call_timeout_s`; la sesión se descarta y la siguiente llamada reconecta."""


class DocsToolError(Exception):
    """La herramienta (o el servidor) rechazó la llamada; el mensaje es el texto del error."""


class _ProcessDied(Exception):
    """Interno: la sesión quedó inservible y conviene reconectar."""


def _is_dead(exc: BaseException) -> bool:
    if isinstance(exc, BaseExceptionGroup):
        return all(_is_dead(e) for e in exc.exceptions)
    if isinstance(exc, MCPError):
        return exc.code == CONNECTION_CLOSED
    return isinstance(exc, _DEAD_PROCESS_ERRORS)


def _error_text(tool: str, content: list[Any]) -> str:
    text = "\n".join(c.text for c in content if isinstance(c, TextContent))
    return text or f"tool {tool} failed"


class _Session:
    """Una conexión (`connect()`) abierta y cerrada dentro de su propia tarea."""

    def __init__(self, connect: Connect):
        self._connect = connect
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._done = asyncio.Event()
        self._task: asyncio.Task | None = None
        self.client: Any = None
        self.error: BaseException | None = None

    @property
    def alive(self) -> bool:
        return self.client is not None and not self._done.is_set()

    async def _own(self) -> None:
        try:
            async with self._connect() as client:
                self.client = client
                self._ready.set()
                await self._stop.wait()
        except Exception as exc:  # noqa: BLE001 — al abrir: se relanza en `start`; después: la llamada ya vio el error
            self.error = exc
        finally:
            self._ready.set()
            self._done.set()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._own())
        await self._ready.wait()
        if self.client is None:
            raise self.error or ConnectionError("MCP session did not open")

    async def close(self) -> None:
        if self._task is None:
            return
        with anyio.CancelScope(shield=True):
            if self.client is None:
                # Nunca abrió (p. ej. timeout en el arranque): la tarea sigue en `__aenter__` y no mira `_stop`.
                self._task.cancel()
            else:
                self._stop.set()
                with anyio.move_on_after(CLOSE_TIMEOUT_S):
                    await self._done.wait()
                if not self._done.is_set():
                    self._task.cancel()
            with anyio.move_on_after(CLOSE_TIMEOUT_S):
                await self._done.wait()
            if not self._done.is_set():
                logger.warning("MCP session task still running after close; abandoning it")


class DocsMCPClient:
    """Sesión MCP perezosa y reutilizada; ver D30."""

    def __init__(self, connect: Connect, call_timeout_s: float):
        self._connect = connect
        self.call_timeout_s = call_timeout_s
        self._session: _Session | None = None
        self._lock = asyncio.Lock()
        self._closed = False

    async def call(self, tool: str, args: dict) -> dict:
        """`structured_content` de la herramienta; reconecta una vez si el proceso murió."""
        if self._closed:
            raise DocsServerUnavailable("MCP client closed")
        try:
            return await self._attempt(tool, args)
        except _ProcessDied:
            pass
        try:
            return await self._attempt(tool, args)
        except _ProcessDied as exc:
            raise DocsServerUnavailable(f"MCP server unavailable calling {tool}") from exc.__cause__

    async def aclose(self) -> None:
        """Cierra la sesión; después `call` lanza `DocsServerUnavailable` y nunca reabre (no deja procesos)."""
        self._closed = True
        async with self._lock:
            session, self._session = self._session, None
        if session is not None:
            await session.close()

    async def _get_session(self) -> _Session:
        async with self._lock:
            if self._closed:
                raise DocsServerUnavailable("MCP client closed")
            if self._session is not None and self._session.alive:
                return self._session
            stale, self._session = self._session, None
            if stale is not None:
                await stale.close()
            session = _Session(self._connect)
            try:
                # Arrancar el servidor también queda acotado: un proceso colgado al abrir cuenta como muerto.
                with anyio.fail_after(self.call_timeout_s):
                    await session.start()
            except BaseException as exc:
                # También ante `CancelledError` (la petición se canceló mientras arrancaba): `close` va blindado
                # contra la cancelación, así que la tarea de la sesión (y el proceso) no queda colgada.
                await session.close()
                if isinstance(exc, TimeoutError) or (isinstance(exc, Exception) and _is_dead(exc)):
                    raise _ProcessDied() from exc
                raise
            self._session = session
            return session

    async def _discard(self, session: _Session) -> None:
        async with self._lock:
            if self._session is session:
                self._session = None
        await session.close()

    async def _attempt(self, tool: str, args: dict) -> dict:
        session = await self._get_session()
        try:
            with anyio.fail_after(self.call_timeout_s):
                result = await session.client.call_tool(tool, args)
        except TimeoutError as exc:
            await self._discard(session)
            raise DocsToolTimeout(f"MCP tool {tool} exceeded {self.call_timeout_s}s") from exc
        except Exception as exc:
            if _is_dead(exc):
                await self._discard(session)
                raise _ProcessDied() from exc
            if isinstance(exc, MCPError):  # error de protocolo (herramienta o argumentos inválidos): no reintentar
                raise DocsToolError(exc.message) from exc
            raise
        if result.is_error:
            raise DocsToolError(_error_text(tool, result.content))
        if result.structured_content is None:
            raise DocsToolError(f"tool {tool} returned no structured content")
        return result.structured_content


def stdio_params(settings: Settings, scope: str) -> StdioServerParameters:
    """`python -m docs_agent.mcp_server` con el entorno completo del padre (el SDK no lo hereda) y el scope.

    `settings` no se usa todavía: el hijo lee su propia configuración del entorno y del `.env` de la raíz.
    """
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "docs_agent.mcp_server"],
        env={**os.environ, "MCP_BUDGET_SCOPE": scope},
        cwd=REPO_ROOT,
    )


def stdio_connect(settings: Settings, scope: str) -> Connect:
    params = stdio_params(settings, scope)
    return lambda: Client(params)
