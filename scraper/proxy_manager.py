"""
Proxy pool manager for the RockAuto scraper (Agent B — CONTRACT §3).

Responsibilities
----------------
- Fetch free proxy lists ("ip:port" per line) from ``config.PROXY["sources"]``.
- Dedupe, then health-check candidates concurrently (ThreadPoolExecutor) against
  ``config.PROXY["health_check_url"]`` — a proxy is "healthy" only if it returns
  HTTP 200 within ``health_timeout_s`` (i.e. it can actually reach RockAuto).
- Score proxies: consecutive failures drop them; ``quarantine`` cools an IP for
  a period (expiry timestamp) after a CAPTCHA/ban without discarding it.
- Persist the pool to ``config.PROXY["pool_cache"]`` (JSON) and reload on init so
  restarts are warm.
- Thread-safe: the crawler runs ``RATE["concurrency"]`` workers, each pulling a
  proxy via ``get()`` and reporting results back concurrently.

``get()`` returns ``"http://ip:port"`` (the client wraps it as
``{"http": p, "https": p}`` for requests) or ``None`` when the pool is empty,
which the client treats as a direct (no-proxy) connection.

Robustness: a single dead source or malformed line must never crash ``refill()``.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ``config`` sits next to this file in the scraper/ package. Support running both
# as a package module (``scraper.proxy_manager``) and as a loose script
# (``python scraper/proxy_manager.py`` — cwd puts scraper/ on sys.path).
try:  # pragma: no cover - trivial import shim
    from . import config
except ImportError:  # pragma: no cover
    import config  # type: ignore


# A line is a valid proxy candidate iff it looks like host:port. We accept bare
# ip:port and also strip a leading scheme if a source happens to include one.
_PROXY_RE = re.compile(
    r"^(?:https?://)?"                       # optional scheme (stripped below)
    r"((?:\d{1,3}\.){3}\d{1,3}"              # IPv4 host ...
    r"|[a-zA-Z0-9._-]+)"                     # ... or a hostname
    r":(\d{1,5})$"                            # :port
)


class ProxyManager:
    """Rotating pool of health-checked free HTTP proxies.

    Internal state is a dict keyed by the bare ``"ip:port"`` string. Each value
    tracks scoring metadata::

        {"fails": <consecutive failure count>, "quarantine_until": <epoch secs>}

    A proxy is *available* when it is in the pool and its ``quarantine_until`` is
    in the past. ``get()`` round-robins over the available set.
    """

    # Drop a proxy after this many *consecutive* failures (report_ok resets it).
    MAX_FAILS = 3
    # Cap the concurrent health-check fan-out so we don't open thousands of
    # sockets at once when a source returns a huge list.
    HEALTH_WORKERS = 40

    def __init__(self, cfg: dict = None) -> None:  # cfg defaults to config.PROXY
        self.cfg = cfg if cfg is not None else config.PROXY
        self._lock = threading.RLock()
        # pool: {"ip:port": {"fails": int, "quarantine_until": float}}
        self._pool: dict[str, dict] = {}
        self._rr = 0                      # round-robin cursor for get()
        self._last_refill = 0.0           # epoch of last successful refill()
        self._cache_path = self.cfg.get("pool_cache", "scraper/.proxy_pool.json")
        # Warm start: reload a previously persisted pool if present.
        self._load()

    # ---- public API (CONTRACT §3) ---------------------------------------

    def get(self) -> str | None:
        """Return ``"http://ip:port"`` for the next available proxy, or ``None``.

        ``None`` signals "no proxy available" — the client should then crawl
        direct. Round-robins so load spreads across the whole healthy pool.
        """
        with self._lock:
            avail = self._available_locked()
            if not avail:
                return None
            self._rr = (self._rr + 1) % len(avail)
            return "http://" + avail[self._rr]

    def report_bad(self, proxy: str) -> None:
        """Record a failure for ``proxy``; drop it after ``MAX_FAILS`` in a row."""
        key = self._norm(proxy)
        with self._lock:
            st = self._pool.get(key)
            if st is None:
                return
            st["fails"] = st.get("fails", 0) + 1
            if st["fails"] >= self.MAX_FAILS:
                self._pool.pop(key, None)
            self._save_locked()

    def report_ok(self, proxy: str) -> None:
        """Reset the consecutive-failure counter for a proxy that just worked."""
        key = self._norm(proxy)
        with self._lock:
            st = self._pool.get(key)
            if st is None:
                return
            st["fails"] = 0
            self._save_locked()

    def quarantine(self, proxy: str, seconds: int) -> None:
        """Cool ``proxy`` down for ``seconds`` (e.g. after a CAPTCHA/soft ban).

        The proxy stays in the pool but is excluded from ``get()`` until the
        expiry timestamp passes — so we don't permanently lose an IP that merely
        tripped anti-bot once.
        """
        key = self._norm(proxy)
        with self._lock:
            st = self._pool.get(key)
            if st is None:
                # Unknown proxy: still record the quarantine so a later refill
                # that re-adds it can respect the cool-down window.
                st = {"fails": 0, "quarantine_until": 0.0}
                self._pool[key] = st
            st["quarantine_until"] = time.time() + max(0, int(seconds))
            self._save_locked()

    def refill(self) -> int:
        """Fetch + health-check proxies, merge survivors into the pool.

        Returns the healthy (available) count afterwards. Never raises for a
        dead source or malformed line — those are skipped. Existing scoring
        metadata (fails / quarantine) is preserved for proxies that survive.
        """
        candidates = self._fetch_candidates()            # deduped "ip:port" set
        # Re-check proxies already in the pool too, so stale entries get pruned.
        with self._lock:
            candidates |= set(self._pool.keys())
        healthy = self._health_check_many(candidates)    # subset that returned 200

        with self._lock:
            new_pool: dict[str, dict] = {}
            now = time.time()
            for key in healthy:
                prev = self._pool.get(key)
                if prev is not None:
                    prev["fails"] = 0            # a fresh 200 clears the score
                    new_pool[key] = prev
                else:
                    new_pool[key] = {"fails": 0, "quarantine_until": 0.0}
            self._pool = new_pool
            self._last_refill = now
            self._rr = 0
            self._save_locked()
            return self._healthy_count_locked()

    def healthy_count(self) -> int:
        """Number of currently-available (in-pool, not quarantined) proxies."""
        with self._lock:
            return self._healthy_count_locked()

    # ---- overridable network seams (monkeypatched by the offline self-test) --

    def _fetch_source(self, url: str) -> str:
        """Fetch one raw proxy-list URL. Returns text ("" on any failure)."""
        try:
            resp = requests.get(url, timeout=self.cfg.get("health_timeout_s", 8))
            if resp.status_code == 200:
                return resp.text
        except Exception:  # noqa: BLE001 — any source may be down; ignore it
            pass
        return ""

    def _check_one(self, key: str) -> bool:
        """True iff ``key`` ("ip:port") returns HTTP 200 to the health URL."""
        proxy = "http://" + key
        proxies = {"http": proxy, "https": proxy}
        try:
            resp = requests.get(
                self.cfg["health_check_url"],
                proxies=proxies,
                timeout=self.cfg.get("health_timeout_s", 8),
                allow_redirects=False,
            )
            return resp.status_code == 200
        except Exception:  # noqa: BLE001 — dead proxy; not healthy
            return False

    # ---- internals -------------------------------------------------------

    def _fetch_candidates(self) -> set[str]:
        """Fetch every source, parse + dedupe into a set of "ip:port"."""
        out: set[str] = set()
        for url in self.cfg.get("sources", []):
            # Guard here too: even if a (possibly overridden) _fetch_source
            # raises, one dead source must never abort the whole refill.
            try:
                text = self._fetch_source(url)
            except Exception:  # noqa: BLE001
                text = ""
            for line in text.splitlines():
                key = self._parse_line(line)
                if key:
                    out.add(key)
        return out

    def _health_check_many(self, candidates: set[str]) -> set[str]:
        """Concurrently health-check ``candidates``; return the healthy subset."""
        healthy: set[str] = set()
        if not candidates:
            return healthy
        workers = min(self.HEALTH_WORKERS, len(candidates))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(self._check_one, k): k for k in candidates}
            for fut in as_completed(futs):
                key = futs[fut]
                try:
                    if fut.result():
                        healthy.add(key)
                except Exception:  # noqa: BLE001 — treat as unhealthy
                    pass
        return healthy

    @staticmethod
    def _parse_line(line: str) -> str | None:
        """Return a normalized "ip:port" for a valid line, else None."""
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        m = _PROXY_RE.match(line)
        if not m:
            return None
        host, port = m.group(1), m.group(2)
        try:
            if not (0 < int(port) < 65536):
                return None
        except ValueError:
            return None
        return f"{host}:{port}"

    @staticmethod
    def _norm(proxy: str) -> str:
        """Strip an optional scheme so keys are consistently bare "ip:port"."""
        if not proxy:
            return ""
        return proxy.split("://", 1)[-1].strip().strip("/")

    def _available_locked(self) -> list[str]:
        """Caller must hold the lock. Sorted list of non-quarantined keys."""
        now = time.time()
        return sorted(
            k for k, st in self._pool.items()
            if st.get("quarantine_until", 0.0) <= now
        )

    def _healthy_count_locked(self) -> int:
        return len(self._available_locked())

    # ---- persistence -----------------------------------------------------

    def _load(self) -> None:
        """Reload the persisted pool (best-effort; a bad file is ignored)."""
        try:
            with open(self._cache_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        pool = data.get("proxies", {}) if isinstance(data, dict) else {}
        clean: dict[str, dict] = {}
        for key, st in pool.items():
            k = self._norm(key)
            if not self._parse_line(k):
                continue
            if not isinstance(st, dict):
                st = {}
            clean[k] = {
                "fails": int(st.get("fails", 0) or 0),
                "quarantine_until": float(st.get("quarantine_until", 0.0) or 0.0),
            }
        with self._lock:
            self._pool = clean
            self._last_refill = float(data.get("last_refill", 0.0)) if isinstance(data, dict) else 0.0

    def _save_locked(self) -> None:
        """Persist the pool atomically. Caller must hold the lock."""
        path = self._cache_path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        payload = {
            "proxies": self._pool,
            "last_refill": self._last_refill,
            "saved_at": time.time(),
        }
        tmp = f"{path}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, path)  # atomic on Windows + POSIX
        except OSError:
            # Persistence is best-effort; never crash the crawl over a write error.
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass


class EvomiProxyManager:
    """Duck-typed drop-in for ProxyManager backed by ONE Evomi residential gateway.

    Evomi rotates the exit IP per connection on the base username, so `get()`
    always returns the same authenticated gateway URL and each new session lands
    on a fresh residential IP — there is nothing to quarantine or refill. Creds
    come from `.evomi.env` (gitignored): EVOMI_HOST/PORT/USER/PASS.
    """

    def __init__(self, env_path: str = ".evomi.env") -> None:
        import urllib.parse
        env = self._load(env_path)
        need = ("EVOMI_HOST", "EVOMI_PORT", "EVOMI_USER", "EVOMI_PASS")
        missing = [k for k in need if not env.get(k)]
        if missing:
            raise RuntimeError(f"{env_path}: missing {missing}")
        # Evomi geo-targets via the PASSWORD: "<pass>_country-US". RockAuto shows
        # inflated INTERNATIONAL prices to non-US IPs, so pin US or the catalog is
        # wrong. Set EVOMI_COUNTRY="" only if you deliberately want global exits.
        country = (os.getenv("EVOMI_COUNTRY") or env.get("EVOMI_COUNTRY") or "US").strip()
        raw_pw = env["EVOMI_PASS"] + (f"_country-{country}" if country else "")
        user = urllib.parse.quote(env["EVOMI_USER"], safe="")
        pw = urllib.parse.quote(raw_pw, safe="")
        self._url = f"http://{user}:{pw}@{env['EVOMI_HOST']}:{env['EVOMI_PORT']}"
        self._host = env["EVOMI_HOST"]
        self._country = country

    @staticmethod
    def _load(path: str) -> dict:
        env: dict[str, str] = {}
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    s = line.strip()
                    if s and not s.startswith("#") and "=" in s:
                        k, v = s.split("=", 1)
                        env[k.strip()] = v.split("#")[0].strip()
        except OSError:
            pass
        # Env vars win (lets CI inject creds as secrets without a file).
        for k in ("EVOMI_HOST", "EVOMI_PORT", "EVOMI_USER", "EVOMI_PASS"):
            if os.getenv(k):
                env[k] = os.environ[k]
        return env

    def get(self) -> str:            # same gateway; Evomi rotates IP per connection
        return self._url

    def report_bad(self, proxy: str) -> None:   # nothing to blacklist
        pass

    def report_ok(self, proxy: str) -> None:
        pass

    def quarantine(self, proxy: str, seconds: int) -> None:  # rotation is automatic
        pass

    def refill(self) -> int:
        return 1


class GatewayProxyManager:
    """Duck-typed drop-in for ANY single rotating-proxy gateway — Webshare / Rayobyte
    datacenter, or any provider that rotates the exit IP per connection on one
    authenticated endpoint. Reads the full proxy URL from SP_PROXY_URL, e.g.
    ``http://user:pass@p.webshare.io:80``. Like the Evomi gateway there is nothing to
    quarantine or refill — the provider rotates IPs itself, so `get()` always returns
    the same endpoint and each connection lands on a fresh IP."""

    def __init__(self, url: str | None = None) -> None:
        raw = (url or os.getenv("SP_PROXY_URL") or "").strip()
        if not raw:
            raise RuntimeError("SP_PROXY_URL not set (expected http://user:pass@host:port)")
        self._url = raw if "://" in raw else "http://" + raw

    def get(self) -> str:            # same gateway; provider rotates IP per connection
        return self._url

    def report_bad(self, proxy: str) -> None:
        pass

    def report_ok(self, proxy: str) -> None:
        pass

    def quarantine(self, proxy: str, seconds: int) -> None:
        pass

    def refill(self) -> int:
        return 1


# =========================================================================
# OFFLINE self-test — no network, no live site. Prints PASS/FAIL.
# Run: python scraper/proxy_manager.py
# =========================================================================
if __name__ == "__main__":
    import tempfile

    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    tmpdir = tempfile.mkdtemp(prefix="proxytest_")
    cache = os.path.join(tmpdir, "pool.json")
    fake_cfg = {
        "enabled": True,
        "sources": ["http://fake/list1.txt", "http://fake/list2.txt"],
        "health_check_url": "http://fake-health/",
        "health_timeout_s": 1,
        "min_pool": 10,
        "pool_cache": cache,
        "refresh_interval_s": 1800,
    }

    # --- Fixtures: two overlapping fake source bodies (dupes + junk lines) ---
    FAKE_SOURCES = {
        "http://fake/list1.txt": (
            "1.1.1.1:8080\n"
            "2.2.2.2:3128\n"
            "1.1.1.1:8080\n"          # duplicate within a source
            "# a comment line\n"
            "garbage-not-a-proxy\n"
            "9.9.9.9:99999\n"          # invalid port -> rejected
            "\n"
        ),
        "http://fake/list2.txt": (
            "2.2.2.2:3128\n"          # duplicate across sources
            "http://3.3.3.3:80\n"      # scheme prefix -> normalized
            "4.4.4.4:8888\n"
        ),
    }
    # Health verdicts we want to simulate: 4.4.4.4 is "dead".
    DEAD = {"4.4.4.4:8888"}

    class TestPM(ProxyManager):
        """Offline subclass: replace the two network seams with fixtures."""
        def _fetch_source(self, url: str) -> str:
            return FAKE_SOURCES.get(url, "")

        def _check_one(self, key: str) -> bool:
            return key not in DEAD

    pm = TestPM(fake_cfg)

    # 1) refill(): dedupe + parse + health-check filtering ------------------
    n = pm.refill()
    with pm._lock:
        keys = set(pm._pool.keys())
    # Expected healthy: 1.1.1.1:8080, 2.2.2.2:3128, 3.3.3.3:80  (4.4 dead, junk dropped)
    expected = {"1.1.1.1:8080", "2.2.2.2:3128", "3.3.3.3:80"}
    check("refill dedupes + filters junk/dead", keys == expected)
    check("refill returns healthy count (3)", n == 3)
    check("healthy_count matches", pm.healthy_count() == 3)

    # 2) get(): returns http://ip:port from the pool ------------------------
    g = pm.get()
    check("get() returns http://ip:port form", g is not None and g.startswith("http://")
          and pm._norm(g) in expected)

    # 3) get() cycles over multiple proxies --------------------------------
    seen = {pm._norm(pm.get()) for _ in range(20)}
    check("get() rotates across pool", seen == expected)

    # 4) report_bad drops after MAX_FAILS consecutive failures --------------
    victim = "1.1.1.1:8080"
    for _ in range(ProxyManager.MAX_FAILS):
        pm.report_bad("http://" + victim)   # accept scheme-prefixed form
    with pm._lock:
        dropped = victim not in pm._pool
    check("report_bad drops after MAX_FAILS", dropped)
    check("healthy_count drops to 2", pm.healthy_count() == 2)

    # 5) report_ok resets the failure score --------------------------------
    other = "2.2.2.2:3128"
    pm.report_bad(other)
    pm.report_bad(other)
    pm.report_ok(other)
    with pm._lock:
        fails_after_ok = pm._pool[other]["fails"]
    check("report_ok resets fail score", fails_after_ok == 0)

    # 6) quarantine excludes a proxy, then expires -------------------------
    pm.quarantine(other, 100)
    excluded = other not in pm._available_locked()
    check("quarantine excludes proxy from get()", excluded)
    # Simulate expiry by rewinding the timestamp into the past.
    with pm._lock:
        pm._pool[other]["quarantine_until"] = time.time() - 1
    check("quarantine expiry re-enables proxy", other in pm._available_locked())

    # 7) quarantine of an unknown proxy is recorded ------------------------
    pm.quarantine("5.5.5.5:1234", 50)
    with pm._lock:
        recorded = "5.5.5.5:1234" in pm._pool and pm._pool["5.5.5.5:1234"]["quarantine_until"] > time.time()
    check("quarantine records unknown proxy", recorded)

    # 8) Persistence round-trip: a fresh instance reloads the same pool -----
    with pm._lock:
        before = {k: dict(v) for k, v in pm._pool.items()}
    pm2 = ProxyManager(fake_cfg)   # base class; reads the persisted JSON file
    with pm2._lock:
        after = {k: dict(v) for k, v in pm2._pool.items()}
    check("persistence round-trips pool exactly", before == after)

    # 9) Robustness: a source that raises must not crash refill() ----------
    class BoomPM(ProxyManager):
        def _fetch_source(self, url: str) -> str:
            if url.endswith("list1.txt"):
                raise RuntimeError("simulated dead source")
            return "7.7.7.7:8080\n"
        def _check_one(self, key: str) -> bool:
            return True
    boom_cache = os.path.join(tmpdir, "boom.json")
    boom_cfg = dict(fake_cfg, pool_cache=boom_cache)
    try:
        # _fetch_source raising should be swallowed inside _fetch_candidates?
        # It is not — refill must still not crash. We wrap per-source below.
        bpm = BoomPM(boom_cfg)
        bn = bpm.refill()
        crashed = False
    except Exception as exc:  # noqa: BLE001
        crashed = True
        print("    refill crashed:", exc)
    check("refill survives a throwing source", not crashed and bn == 1)

    print()
    if failures:
        print(f"SELF-TEST: FAIL ({len(failures)} failing) -> {failures}")
        raise SystemExit(1)
    print("SELF-TEST: PASS")
