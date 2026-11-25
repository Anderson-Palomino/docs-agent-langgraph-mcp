"""Rate limit por IP para `/ask`: ventana deslizante en memoria + resolución de la IP del cliente tras un proxy.

IP del cliente y `X-Forwarded-For` (comprobado en la doc, Task 7 Step 0):
- Railway: la doc oficial (https://docs.railway.com/networking/public-networking/specs-and-limits) solo
  documenta `X-Real-IP`; no menciona `X-Forwarded-For` ni si pisa copias del cliente.
- Render: la doc oficial (https://render.com/docs/web-services) no dice nada de la IP del cliente; la comunidad
  informa que su proxy NO filtra el `X-Forwarded-For` entrante y agrega la IP al final, así que el primer valor
  lo puede falsificar el cliente.
Como la doc no garantiza el primer valor, se usa el valor más a la derecha que no sea un proxy confiable: es el
que añadió el proxy de confianza, no el cliente.
"""

import ipaddress
import logging
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


@dataclass(frozen=True)
class TrustedProxies:
    all: bool = False
    networks: tuple[IPNetwork, ...] = ()

    def __contains__(self, ip: IPAddress) -> bool:
        return self.all or any(ip in net for net in self.networks)


def parse_trusted(spec: str) -> TrustedProxies:
    """`""` → nadie, `"*"` → todos, o IPs/CIDR separados por comas. Entrada inválida → `ValueError`."""
    spec = spec.strip()
    if not spec:
        return TrustedProxies()
    if spec == "*":
        return TrustedProxies(all=True)
    nets = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        nets.append(ipaddress.ip_network(part, strict=False))  # ValueError si no es IP/CIDR
    return TrustedProxies(networks=tuple(nets))


def _strip_port(value: str) -> str:
    """Quita el puerto de `1.2.3.4:5678` y `[2001:db8::1]:443`; una IPv6 sin corchetes se deja intacta."""
    if value.startswith("["):
        end = value.find("]")
        return value[1:end] if end != -1 else value
    if value.count(":") == 1:
        return value.split(":", 1)[0]
    return value


def _as_ip(value: str | None) -> IPAddress | None:
    try:
        return ipaddress.ip_address(_strip_port((value or "").strip()))
    except ValueError:
        return None


def limit_key(ip: str) -> str:
    """Clave del limitador: IPv4 tal cual; IPv6 por su red /64 (un cliente controla todo su /64 y rotaría
    direcciones). Lo que no es IP (p. ej. "testclient") se usa tal cual."""
    parsed = _as_ip(ip)
    if isinstance(parsed, ipaddress.IPv6Address):
        if parsed.ipv4_mapped is not None:  # ::ffff:1.2.3.4 es un cliente IPv4, no un /64 compartido
            return str(parsed.ipv4_mapped)
        return str(ipaddress.ip_network(f"{parsed}/64", strict=False))
    return str(parsed) if parsed is not None else ip


@dataclass(frozen=True)
class ClientResolution:
    """Cómo se resolvió la IP del cliente: la IP, de dónde salió y la cabecera `X-Forwarded-For` ya partida."""

    ip: str
    source: Literal["peer", "xff"]
    xff_index_from_right: int | None  # 0 = entrada más a la derecha; None si se usó el peer
    xff_entries: list[str]


def resolve_client(peer: str | None, forwarded_for: str | None, trusted: TrustedProxies) -> ClientResolution:
    """IP del cliente: el peer del socket, salvo que sea un proxy confiable y haya `X-Forwarded-For` válido.

    Se recorre la cabecera de derecha a izquierda y se devuelve la primera IP que no sea proxy confiable;
    con `*` (todo confiable) se toma la última. Cualquier valor no-IP → se usa el peer. Un peer que no es IP
    (p. ej. "testclient") nunca es confiable. Devuelve además qué entrada se usó (índice desde la derecha).
    """
    fallback = peer or "unknown"
    entries = [e.strip() for e in forwarded_for.split(",")] if forwarded_for else []
    from_peer = ClientResolution(fallback, "peer", None, entries)
    peer_ip = _as_ip(peer)
    if peer_ip is None or peer_ip not in trusted or not forwarded_for:
        return from_peer
    for index, entry in enumerate(reversed(entries)):
        ip = _as_ip(entry)
        if ip is None:
            return from_peer
        if trusted.all or ip not in trusted:
            return ClientResolution(str(ip), "xff", index, entries)
    return from_peer


def client_ip(peer: str | None, forwarded_for: str | None, trusted: TrustedProxies) -> str:
    """Solo la IP de `resolve_client`."""
    return resolve_client(peer, forwarded_for, trusted).ip


def mask_ip(value: str) -> str:
    """Versión enmascarada para logs: IPv4 `a.b.x.x`; IPv6 (o red /64) `p1:p2:x:x::/64`; no-IP `<no-ip>`.
    Se quita el puerto antes; una IPv4 mapeada en IPv6 se trata como IPv4. Nunca devuelve una IP completa."""
    value = value.strip()
    parsed: IPAddress | None
    if "/" in value:
        try:
            parsed = ipaddress.ip_network(value, strict=False).network_address
        except ValueError:
            parsed = None
    else:
        parsed = _as_ip(value)
    if parsed is None:
        return "<no-ip>"
    if isinstance(parsed, ipaddress.IPv6Address):
        if parsed.ipv4_mapped is not None:
            parsed = parsed.ipv4_mapped
        else:
            first, second = parsed.packed[0] << 8 | parsed.packed[1], parsed.packed[2] << 8 | parsed.packed[3]
            return f"{first:x}:{second:x}:x:x::/64"
    a, b = str(parsed).split(".")[:2]
    return f"{a}.{b}.x.x"


class SlidingWindowLimiter:
    """Ventana deslizante por clave, en memoria (por proceso/instancia; se reinicia al desplegar). `limit=0` = desactivado.

    Las claves se mantienen ordenadas por último acierto: las vencidas se purgan desde el frente (O(1) amortizado
    por petición) y `max_keys` acota la memoria expulsando la clave más antigua (con un aviso, una sola vez).
    Es seguro entre hilos: FastAPI corre la dependencia síncrona en un threadpool, así que `hit` toma un lock.
    """

    def __init__(
        self, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic, max_keys: int = 10_000
    ):
        self.limit = limit
        self.window_s = window_s
        self.max_keys = max_keys
        self._clock = clock
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._warned_full = False
        self._lock = threading.Lock()

    def hit(self, key: str) -> float | None:
        """`None` si se permite; si no, segundos hasta que se libere un cupo (para `Retry-After`)."""
        if self.limit <= 0:
            return None
        with self._lock:
            return self._hit_locked(key)

    def _hit_locked(self, key: str) -> float | None:
        now = self._clock()
        self._purge(now)
        q = self._hits.get(key)
        if q is None:
            if len(self._hits) >= self.max_keys:
                self._hits.popitem(last=False)
                if not self._warned_full:
                    self._warned_full = True
                    logger.warning("rate limiter full (%d keys): evicting the oldest key", self.max_keys)
            q = self._hits[key] = deque()
        cutoff = now - self.window_s
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= self.limit:
            return q[0] + self.window_s - now
        q.append(now)
        self._hits.move_to_end(key)
        return None

    def _purge(self, now: float) -> None:
        """Descarta desde el frente las claves cuyo último acierto ya salió de la ventana."""
        cutoff = now - self.window_s
        while self._hits:
            key, q = next(iter(self._hits.items()))
            if q and q[-1] > cutoff:
                break
            del self._hits[key]
