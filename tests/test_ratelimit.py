import logging

import pytest

from docs_agent.ratelimit import SlidingWindowLimiter, client_ip, limit_key, parse_trusted


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_without_trusted_proxies_uses_peer():
    assert client_ip("10.0.0.1", "1.2.3.4", parse_trusted("")) == "10.0.0.1"


def test_trusted_peer_takes_rightmost_untrusted_entry():
    # El cliente puede falsificar el primer valor; el que agrega el proxy confiable es el último (ver ratelimit.py).
    assert client_ip("10.0.0.1", " 1.2.3.4 , 5.6.7.8", parse_trusted("10.0.0.0/8")) == "5.6.7.8"
    assert client_ip("10.0.0.1", "9.9.9.9, 5.6.7.8, 10.0.0.2", parse_trusted("10.0.0.0/8")) == "5.6.7.8"


def test_spoofed_first_value_is_ignored():
    assert client_ip("10.0.0.1", "6.6.6.6, 1.2.3.4", parse_trusted("10.0.0.1")) == "1.2.3.4"


def test_untrusted_peer_ignores_header():
    assert client_ip("8.8.8.8", "1.2.3.4", parse_trusted("10.0.0.0/8")) == "8.8.8.8"


def test_star_trusts_any_peer():
    assert client_ip("203.0.113.9", "1.2.3.4", parse_trusted("*")) == "1.2.3.4"
    assert client_ip("203.0.113.9", "9.9.9.9, 1.2.3.4", parse_trusted("*")) == "1.2.3.4"


def test_non_ip_forwarded_value_falls_back_to_peer():
    assert client_ip("10.0.0.1", "unknown", parse_trusted("10.0.0.0/8")) == "10.0.0.1"
    assert client_ip("10.0.0.1", "1.2.3.4, unknown", parse_trusted("*")) == "10.0.0.1"


def test_non_ip_peer_does_not_crash():
    assert client_ip("testclient", "1.2.3.4", parse_trusted("10.0.0.0/8")) == "testclient"
    assert client_ip("testclient", "1.2.3.4", parse_trusted("*")) == "testclient"
    assert client_ip(None, None, parse_trusted("")) == "unknown"


def test_ipv6_and_list():
    t = parse_trusted("10.0.0.0/8, ::1")
    assert client_ip("::1", "2001:db8::5", t) == "2001:db8::5"


def test_parse_trusted_invalid_raises():
    with pytest.raises(ValueError):
        parse_trusted("not-an-ip")


def test_limiter_blocks_21st_and_releases_after_window():
    clock = FakeClock()
    lim = SlidingWindowLimiter(20, 3600, clock)
    assert all(lim.hit("a") is None for _ in range(20))
    wait = lim.hit("a")
    assert wait == pytest.approx(3600)
    assert lim.hit("b") is None  # otra clave no se ve afectada
    clock.now += 3600
    assert lim.hit("a") is None


def test_limiter_retry_after_shrinks_as_time_passes():
    clock = FakeClock()
    lim = SlidingWindowLimiter(1, 100, clock)
    assert lim.hit("a") is None
    clock.now += 40
    assert lim.hit("a") == pytest.approx(60)


def test_limit_zero_never_blocks():
    lim = SlidingWindowLimiter(0, 3600, FakeClock())
    assert all(lim.hit("a") is None for _ in range(100))


def test_limiter_purges_expired_keys_from_front():
    clock = FakeClock()
    lim = SlidingWindowLimiter(5, 10, clock)
    for i in range(50):
        lim.hit(f"ip{i}")
    clock.now += 11
    lim.hit("fresh")
    assert list(lim._hits) == ["fresh"]


def test_limiter_purge_keeps_active_keys_ordered_by_last_hit():
    clock = FakeClock()
    lim = SlidingWindowLimiter(5, 10, clock)
    lim.hit("a")
    clock.now += 6
    lim.hit("b")
    clock.now += 6  # a vencida, b no
    lim.hit("c")
    assert list(lim._hits) == ["b", "c"]
    clock.now += 1
    lim.hit("b")  # b se refresca y pasa al final
    assert list(lim._hits) == ["c", "b"]


def test_limiter_max_keys_evicts_oldest_and_warns_once(caplog):
    clock = FakeClock()
    lim = SlidingWindowLimiter(5, 3600, clock, max_keys=3)
    with caplog.at_level(logging.WARNING, logger="docs_agent.ratelimit"):
        for k in ["a", "b", "c", "d", "e"]:
            lim.hit(k)
            clock.now += 1
    assert list(lim._hits) == ["c", "d", "e"]
    assert caplog.text.count("rate limiter full") == 1


def test_ipv6_keyed_by_slash_64():
    assert limit_key("2001:db8:1:2::1") == limit_key("2001:db8:1:2:ffff:ffff:ffff:ffff")
    assert limit_key("2001:db8:1:2::1") != limit_key("2001:db8:1:3::1")
    assert limit_key("1.2.3.4") == "1.2.3.4"
    assert limit_key("testclient") == "testclient"


def test_port_is_stripped_from_entries():
    t = parse_trusted("10.0.0.0/8")
    assert client_ip("10.0.0.1", "1.2.3.4:5678", t) == "1.2.3.4"
    assert client_ip("10.0.0.1", "[2001:db8::1]:443", t) == "2001:db8::1"
    assert client_ip("10.0.0.1:9999", "1.2.3.4", t) == "1.2.3.4"


def test_ipv4_mapped_ipv6_keys_by_the_ipv4_address():
    assert limit_key("::ffff:1.2.3.4") == "1.2.3.4"
    assert limit_key("::ffff:5.6.7.8") == "5.6.7.8"


def test_limiter_is_thread_safe_under_concurrent_hits():
    """Varios hilos (el threadpool de FastAPI) sobre un limitador chico: sin excepciones y sin pasar el límite."""
    import itertools
    import sys
    import time
    from concurrent.futures import ThreadPoolExecutor

    limiter = SlidingWindowLimiter(limit=5, window_s=0.001, clock=time.monotonic, max_keys=20)
    strict = SlidingWindowLimiter(limit=3, window_s=3600, max_keys=1000)
    counter = itertools.count()

    def worker(_):
        admitted = 0
        for _ in range(3000):
            n = next(counter)
            limiter.hit(f"k{n % 50}")
            if strict.hit("solo") is None:
                admitted += 1
        return admitted

    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # fuerza cambios de hilo a mitad de `hit` para exponer la carrera
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            admitted = sum(pool.map(worker, range(8)))  # relanza cualquier excepción de los hilos
    finally:
        sys.setswitchinterval(previous)
    assert admitted == 3
