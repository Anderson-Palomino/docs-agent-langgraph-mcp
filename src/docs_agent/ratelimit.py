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
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

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


def _as_ip(value: str | None) -> IPAddress | None:
    try:
        return ipaddress.ip_address((value or "").strip())
    except ValueError:
        return None


def client_ip(peer: str | None, forwarded_for: str | None, trusted: TrustedProxies) -> str:
    """IP del cliente: el peer del socket, salvo que sea un proxy confiable y haya `X-Forwarded-For` válido.

    Se recorre la cabecera de derecha a izquierda y se devuelve la primera IP que no sea proxy confiable;
    con `*` (todo confiable) se toma la última. Cualquier valor no-IP → se usa el peer. Un peer que no es IP
    (p. ej. "testclient") nunca es confiable.
    """
    fallback = peer or "unknown"
    peer_ip = _as_ip(peer)
    if peer_ip is None or peer_ip not in trusted or not forwarded_for:
        return fallback
    entries = [e.strip() for e in forwarded_for.split(",")]
    for entry in reversed(entries):
        ip = _as_ip(entry)
        if ip is None:
            return fallback
        if trusted.all or ip not in trusted:
            return str(ip)
    return fallback


class SlidingWindowLimiter:
    """Ventana deslizante por clave, en memoria (por instancia; se reinicia al desplegar). `limit=0` = desactivado."""

    def __init__(self, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> float | None:
        """`None` si se permite; si no, segundos hasta que se libere un cupo (para `Retry-After`)."""
        if self.limit <= 0:
            return None
        now = self._clock()
        self._purge(now)
        q = self._hits.setdefault(key, deque())
        if len(q) >= self.limit:
            return q[0] + self.window_s - now
        q.append(now)
        return None

    def _purge(self, now: float) -> None:
        """Descarta marcas vencidas y claves vacías para que el dict no crezca sin límite."""
        cutoff = now - self.window_s
        for key in list(self._hits):
            q = self._hits[key]
            while q and q[0] <= cutoff:
                q.popleft()
            if not q:
                del self._hits[key]
