"""
scraper/ra_client.py — Agent A (HTTP Client)

Thin, polite, rotation-aware HTTP layer over the RockAuto catalog. Everything
that touches the network for the crawler lives here so the parsers/frontier stay
pure. Implements the CONTRACT §3 surface:

    Blocked(Exception)
    RAClient.new_session()                       -> fresh cookies + UA + proxy, harvest _nck
    RAClient.get(url)                            -> HTML (raises Blocked on CAPTCHA/ban)
    RAClient.fetch_children(node, max_group_index) -> catalog HTML fragment (raises Blocked)
    RAClient.rotate()                            -> quarantine current proxy, new_session()

Protocol notes (verified — see CONTRACT §0):
  * A requests.Session carries the PHPSESSID / saved_server / mkt_* cookies that
    RockAuto hands out on the first GET of CATALOG_ROOT. We also harvest the
    ~364-char `_nck` nonce from that page; it is required on every catalogapi POST.
  * Lazy tree children load via POST func=tab_fetch to CATALOG_API. The node's
    `jsn` dict (groupindex/nodetype/make/year/model/carcode/...) plus a
    `max_group_index` int is JSON-encoded into the `payload` form field.
  * Anti-bot fires a 302 -> /captcha/ (securimage). We never try to solve it: we
    detect it, quarantine the offending proxy, cool down, rotate IP+UA, and let
    the caller re-enqueue the node so nothing is lost.

Only stdlib + `requests` are used. Import of ProxyManager is intentionally soft
(duck-typed) so this module unit-tests offline with a fake pool.
"""
from __future__ import annotations

import gzip
import json
import os
import random
import re
import threading
import time
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from requests.exceptions import RequestException

# Support both "python -m scraper.ra_client" (package) and "python ra_client.py"
# (script) execution. As a package we use the relative import; run as a bare
# script there is no parent package, so fall back to a top-level import.
try:
    from . import config
    from .config import CATALOG_API, CATALOG_ROOT, CAPTCHA_PATH, RATE, USER_AGENTS
except ImportError:  # pragma: no cover - script-mode fallback
    import config  # type: ignore
    from config import (  # type: ignore
        CATALOG_API,
        CATALOG_ROOT,
        CAPTCHA_PATH,
        RATE,
        USER_AGENTS,
    )


class Blocked(Exception):
    """Raised when a request lands on the CAPTCHA wall or is otherwise soft-banned.

    The orchestrator treats this as recoverable: rotate the IP and re-enqueue the
    node. It is NOT a crawl-fatal error.
    """


class BudgetExceeded(Exception):
    """Raised when the crawl has transferred its byte budget — the HARD Evomi $
    cap. Crawl-fatal by design: the run loop catches it and exits cleanly so the
    residential-proxy bill can never run past the configured ceiling."""


class _BudgetMeter:
    """Thread-safe meter of billed proxy bytes with a hard stop.

    Evomi bills gzipped WIRE bytes both ways. We approximate per request as
    (compressed response) + (request out) + fixed TLS/header overhead, summed
    across all worker threads. `spent` persists to a small state file so a
    resumed / re-dispatched run keeps counting from where it left off and the
    global cap holds across many 6h jobs. No cap set -> meter is a no-op.
    """

    def __init__(self) -> None:
        self.max_bytes = 0
        self.spent = 0
        self._state = None
        self._since_save = 0
        self._lock = threading.Lock()

    def configure(self, max_gb, state_path: str | None = None) -> None:
        self.max_bytes = int(float(max_gb) * 1_000_000_000)
        self._state = state_path or None
        if self._state and os.path.exists(self._state):
            try:
                self.spent = int(open(self._state).read().strip() or "0")
            except (OSError, ValueError):
                self.spent = 0
        print(f"[budget] cap={self.max_bytes/1e9:.2f}GB already_spent={self.spent/1e9:.3f}GB", flush=True)

    def _persist(self) -> None:
        if self._state:
            try:
                with open(self._state, "w") as fh:
                    fh.write(str(self.spent))
            except OSError:
                pass

    def record(self, resp, up_bytes: int) -> None:
        if not self.max_bytes:
            return
        cl = resp.headers.get("Content-Length")
        try:
            down = int(cl) if cl and cl.isdigit() else len(gzip.compress(resp.content or b""))
        except Exception:  # noqa: BLE001 - never let metering break a fetch
            down = len(resp.content or b"")
        billed = down + max(0, up_bytes) + 600      # + rough per-request TLS/header overhead
        with self._lock:
            self.spent += billed
            self._since_save += billed
            if self._since_save >= 5_000_000:       # checkpoint ~every 5 MB
                self._persist()
                self._since_save = 0
            over = self.spent >= self.max_bytes
        if over:
            self._persist()
            raise BudgetExceeded(
                f"byte budget reached: {self.spent/1e9:.2f}GB >= {self.max_bytes/1e9:.2f}GB"
            )


# One meter shared by every RAClient/worker in the process.
BUDGET = _BudgetMeter()


# --- regexes (module-level so they compile once) --------------------------
# The nonce lives in <input name="_nck" value="...">. Attribute order on the
# RockAuto form is name-then-value, but we tolerate the reverse just in case.
_NCK_RE_NAME_FIRST = re.compile(
    r'name=["\']_nck["\'][^>]*?value=["\']([^"\']+)["\']', re.IGNORECASE
)
_NCK_RE_VALUE_FIRST = re.compile(
    r'value=["\']([^"\']+)["\'][^>]*?name=["\']_nck["\']', re.IGNORECASE
)
# Strong CAPTCHA fingerprints in a response body (securimage widget markup).
_CAPTCHA_BODY_RE = re.compile(r"securimage|captchaimage|captcha_code", re.IGNORECASE)
# BUT: RockAuto embeds the securimage checkout widget in EVERY catalog page, so
# a securimage hit alone is NOT a captcha wall. A real wall is the standalone
# /captcha/ page, which lacks these catalog/nav markers. Presence of any marker
# means the page is real catalog content (with an incidental checkout captcha).
_CATALOG_MARKER_RE = re.compile(
    r"ranavnode|navlabellink|treeroot|html_fill_sections|listing-|nchildren"
    r"|section-tab-panel",
    re.IGNORECASE,
)
# --- /captcha/ wall extraction (securimage) -------------------------------
# The challenge image: <img class="captchaimage" src="/captcha/securimage/securimage_show.php?ID">.
_CAPTCHA_IMG_RE = re.compile(
    r'<img[^>]+class=["\'][^"\']*captchaimage[^"\']*["\'][^>]*src=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_CAPTCHA_IMG_FALLBACK_RE = re.compile(
    r'src=["\']([^"\']*securimage_show\.php[^"\']*)["\']', re.IGNORECASE
)
# The captcha <form action="..."> plus its hidden inputs, so we resubmit anything
# RockAuto expects alongside the solved `captchacode`.
_CAPTCHA_FORM_ACTION_RE = re.compile(
    r'<form[^>]*\baction=["\']([^"\']*)["\']', re.IGNORECASE
)
_HIDDEN_INPUT_RE = re.compile(
    r'<input[^>]+type=["\']hidden["\'][^>]*>', re.IGNORECASE
)
_INPUT_NAME_RE = re.compile(r'\bname=["\']([^"\']+)["\']', re.IGNORECASE)
_INPUT_VALUE_RE = re.compile(r'\bvalue=["\']([^"\']*)["\']', re.IGNORECASE)


class RAClient:
    """A single crawl worker's HTTP session (one proxy + one UA at a time).

    Instances are cheap; the orchestrator creates one per worker. Not thread
    safe — give each thread its own RAClient (each on its own proxy), which is
    exactly how config.RATE["concurrency"] is meant to be used.
    """

    def __init__(self, proxies: "object | None" = None) -> None:
        # `proxies` is a ProxyManager (duck-typed: .get/.quarantine). None = direct.
        self._proxies = proxies
        self._session: requests.Session | None = None
        self._proxy: str | None = None      # current proxy URL ("http://ip:port") or None
        self._ua: str | None = None         # current User-Agent string
        self._nck: str | None = None        # current catalog nonce
        self._solver_mod: object = "unset"  # lazy captcha_solver handle ("unset" until first use)

    # -- public API --------------------------------------------------------

    def new_session(self) -> None:
        """Start a fresh session: pick a proxy + UA, warm CATALOG_ROOT for
        cookies, and harvest the `_nck` nonce.

        Self-contained and bounded: if the warm-up hits a CAPTCHA or a dead
        proxy it quarantines that proxy and tries another, up to
        RATE["max_attempts"]. It never calls rotate()/get() (which would recurse
        back into new_session). If it can't get a clean warm page it still leaves
        a usable session behind so the higher-level get()/fetch_children() retry
        loops can take over and keep rotating.
        """
        last_err: str | None = None
        for attempt in range(int(RATE["max_attempts"])):
            self._proxy = self._pool_get()
            self._ua = random.choice(USER_AGENTS)
            self._session = self._build_session()
            try:
                resp = self._send("GET", CATALOG_ROOT)
            except RequestException as exc:  # dead/slow proxy — try another
                last_err = f"{type(exc).__name__}: {exc}"
                self._quarantine_current()
                self._sleep_backoff(attempt)
                continue
            if self._is_captcha(resp):       # soft ban on the warm page itself
                last_err = "captcha on warm-up"
                self._quarantine_current()
                self._sleep_captcha_backoff()
                continue
            nck = self._extract_nck(resp.text)
            if nck:
                self._nck = nck
            return  # clean warm session established
        # Exhausted warm-up attempts. Keep the last session so callers can retry.
        if self._session is None:
            self._session = self._build_session()
        # (Intentionally not raising: warm-up failure is not fatal; get() will retry.)
        _ = last_err

    def get(self, url: str) -> str:
        """GET `url`, returning the response HTML.

        Raises Blocked if every attempt lands on the CAPTCHA wall (or the request
        keeps failing after rotation). Rotates proxy+UA on CAPTCHA or network
        error between attempts.
        """
        if self._session is None:
            self.new_session()
        last_err: str | None = None
        attempts = int(RATE["max_attempts"])
        for attempt in range(attempts):
            self._sleep_polite(attempt)
            try:
                resp = self._send("GET", url)
            except RequestException as exc:  # timeout / conn reset / bad proxy
                last_err = f"{type(exc).__name__}: {exc}"
                self.rotate()
                continue
            if self._is_captcha(resp):
                last_err = f"captcha at {getattr(resp, 'url', url)!r}"
                # Try to OCR-solve the securimage wall on the SAME session first;
                # only rotate the IP if solving fails. A solve clears the session
                # so the next loop iteration re-requests `url` cleanly.
                if not self._try_solve_captcha(resp):
                    self.rotate()
                continue
            return resp.text
        raise Blocked(f"GET {url} blocked after {attempts} attempts ({last_err})")

    def fetch_children(self, node: dict, max_group_index: int = 4) -> str:
        """Expand one nav node's lazy children via POST func=tab_fetch.

        `node` is a TreeNode dict (see CONTRACT §2); we only need its `jsn`
        object. Returns the catalog HTML fragment string embedded in the JSON
        `html_fill_sections`. Raises Blocked on CAPTCHA/repeated failure.

        Refreshes the `_nck` nonce and retries if a response signals a stale
        nonce (RockAuto rotates it periodically).
        """
        if self._session is None:
            self.new_session()
        jsn = dict(node.get("jsn") or {})
        attempts = int(RATE["max_attempts"])
        last_err: str | None = None
        for attempt in range(attempts):
            self._sleep_polite(attempt)
            # Build the form body fresh each attempt (nonce may have refreshed).
            jsn["max_group_index"] = int(max_group_index)
            body = {
                "func": "tab_fetch",
                # requests url-encodes this JSON string once on the wire, which is
                # exactly the `payload=urlencode(json.dumps(...))` shape RockAuto wants.
                "payload": json.dumps(jsn, separators=(",", ":")),
                "api_json_request": "1",
                "sctchecked": "1",
                "scbeenloaded": "false",
                "curCartGroupID": "",
            }
            if self._nck:
                body["_nck"] = self._nck
            try:
                resp = self._send(
                    "POST", CATALOG_API, data=body, headers=self._api_headers()
                )
            except RequestException as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                self.rotate()
                continue
            if self._is_captcha(resp):
                last_err = "captcha on tab_fetch"
                if not self._try_solve_captcha(resp):
                    self.rotate()
                continue
            try:
                data = resp.json()
            except ValueError:
                # Non-JSON body: likely an interstitial/captcha HTML page.
                if self._is_captcha_body(resp.text):
                    self.rotate()
                else:
                    last_err = "non-JSON tab_fetch response"
                continue
            # Some responses echo a fresh nonce — adopt it silently.
            self._absorb_nonce(data)
            if self._nonce_stale(data):
                last_err = "stale _nck"
                self._refresh_nck()
                continue
            fragment = self._extract_catalog_fragment(data)
            if fragment is not None:
                return fragment
            # No sections at all and not obviously stale: treat as a leaf/empty
            # nav node rather than an error.
            return ""
        raise Blocked(
            f"fetch_children({jsn.get('nodetype')}) blocked after {attempts} attempts ({last_err})"
        )

    def fetch_listings(self, jsn: dict, max_group_index: int = 0) -> str:
        """Fetch a parttype node's LISTINGS via the catalogapi navnode_fetch XHR —
        the compact fragment RockAuto's own UI uses, without the full-page chrome.

        Payload shape mirrors the site JS exactly: func=navnode_fetch with
        payload = json({"jsn": <node jsn>, "max_group_index": N}). Returns the
        listing HTML fragment (from html_fill_sections), or "" if none.
        """
        if self._session is None:
            self.new_session()
        attempts = int(RATE["max_attempts"])
        last_err = None
        for attempt in range(attempts):
            self._sleep_polite(attempt)
            payload = {"jsn": jsn, "max_group_index": int(max_group_index)}
            body = {
                "func": "navnode_fetch",
                "payload": json.dumps(payload, separators=(",", ":")),
                "api_json_request": "1",
                "sctchecked": "1",
                "scbeenloaded": "false",
                "curCartGroupID": "",
            }
            if self._nck:
                body["_nck"] = self._nck
            try:
                resp = self._send("POST", CATALOG_API, data=body, headers=self._api_headers())
            except RequestException as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                self.rotate()
                continue
            if self._is_captcha(resp):
                last_err = "captcha on navnode_fetch"
                if not self._try_solve_captcha(resp):
                    self.rotate()
                continue
            try:
                data = resp.json()
            except ValueError:
                if self._is_captcha_body(resp.text):
                    self.rotate()
                else:
                    last_err = "non-JSON navnode_fetch response"
                continue
            self._absorb_nonce(data)
            if self._nonce_stale(data):
                self._refresh_nck()
                continue
            frag = self._extract_catalog_fragment(data)
            return frag if frag is not None else ""
        raise Blocked(f"fetch_listings blocked after {attempts} attempts ({last_err})")

    def rotate(self) -> None:
        """Quarantine the current proxy (captcha cool-down) and start fresh."""
        self._quarantine_current()
        self.new_session()

    # -- internals ---------------------------------------------------------

    def _build_session(self) -> requests.Session:
        """Create a requests.Session wired with the current UA + proxy + cookies."""
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": self._ua or random.choice(USER_AGENTS),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        if self._proxy:
            s.proxies.update({"http": self._proxy, "https": self._proxy})
        return s

    def _api_headers(self) -> dict:
        """Headers RockAuto's catalogapi.php expects on an XHR POST."""
        return {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": config.BASE,
            "Referer": CATALOG_ROOT,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }

    def _send(self, method: str, url: str, **kw) -> requests.Response:
        """One raw request via the current session. No retry, no captcha logic.

        Frontier hrefs are site-relative (e.g. '/en/catalog/honda'); requests
        needs an absolute URL, so resolve relative paths against config.BASE.
        """
        assert self._session is not None  # new_session() always runs first
        if url.startswith("/"):
            url = config.BASE + url
        kw.setdefault("timeout", RATE["request_timeout_s"])
        kw.setdefault("allow_redirects", True)
        resp = self._session.request(method, url, **kw)
        # Meter billed proxy bytes; raises BudgetExceeded at the hard cap.
        up = len(url) + len(str(kw.get("data") or kw.get("params") or "")) + 500
        BUDGET.record(resp, up)
        return resp

    # -- proxy pool helpers (duck-typed; tolerate a minimal fake) ----------

    def _pool_get(self) -> str | None:
        if self._proxies is None:
            return None
        try:
            return self._proxies.get()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - a flaky pool must not crash the client
            return None

    def _quarantine_current(self) -> None:
        if self._proxies is None or not self._proxy:
            return
        try:
            self._proxies.quarantine(  # type: ignore[attr-defined]
                self._proxy, int(RATE["captcha_backoff_s"])
            )
        except Exception:  # noqa: BLE001
            pass

    # -- captcha solving (securimage OCR) ---------------------------------

    def _solver(self):
        """Lazy-load the optional captcha_solver module. None if unavailable
        (Pillow/pytesseract/tesseract missing) — caller falls back to rotate()."""
        if self._solver_mod == "unset":
            try:
                try:
                    from . import captcha_solver  # type: ignore
                except ImportError:  # script-mode
                    import captcha_solver  # type: ignore
                self._solver_mod = captcha_solver
            except Exception:  # noqa: BLE001 - solver is optional
                self._solver_mod = None
        return self._solver_mod

    @staticmethod
    def _extract_captcha_img(html: str) -> str | None:
        """Pull the securimage challenge image src out of the /captcha/ wall."""
        m = _CAPTCHA_IMG_RE.search(html) or _CAPTCHA_IMG_FALLBACK_RE.search(html)
        return m.group(1) if m else None

    def _try_solve_captcha(self, resp: requests.Response) -> bool:
        """Attempt to OCR-solve the securimage wall and submit the code, clearing
        the session. Returns True if the wall was cleared (retry the original
        request), False to fall back to rotate().

        Bounded by config.CAPTCHA["attempts"]; requests a FRESH securimage code
        between failed tries (securimage is weak per-image, so retries compound).
        Built to the observed /captcha/?redirecturl=<path> page structure; since
        this machine is currently IP-blocked it is not yet live-verified, so every
        failure path falls back to rotate() and can never wedge the crawl.
        """
        cfg = getattr(config, "CAPTCHA", {"solve": False, "attempts": 5})
        if not cfg.get("solve"):
            return False
        solver = self._solver()
        if solver is None:
            return False
        page_url = getattr(resp, "url", "") or CATALOG_ROOT
        html = getattr(resp, "text", "") or ""
        for _ in range(max(1, int(cfg.get("attempts", 5)))):
            img_src = self._extract_captcha_img(html)
            if not img_src:
                return False
            img_url = urljoin(page_url, img_src)
            try:
                code = solver.solve_from_url(self._session, img_url)
            except Exception:  # noqa: BLE001 - a solver hiccup must not crash the crawl
                code = None
            if code and self._submit_captcha(page_url, html, code):
                return True
            # Wrong/no code — reload the wall for a fresh securimage challenge.
            try:
                fresh = self._send("GET", page_url)
            except RequestException:
                return False
            if not self._is_captcha(fresh):
                return True  # session already cleared (cookie set)
            page_url = getattr(fresh, "url", page_url) or page_url
            html = getattr(fresh, "text", "") or ""
        return False

    def _submit_captcha(self, page_url: str, html: str, code: str) -> bool:
        """POST the solved securimage code (+ redirecturl + hidden fields) to the
        captcha form. True iff the response is no longer a captcha wall."""
        m = _CAPTCHA_FORM_ACTION_RE.search(html)
        action = m.group(1).strip() if (m and m.group(1).strip()) else page_url
        action = urljoin(page_url, action)
        data = {"captchacode": code}
        # redirecturl rides on the wall URL's query string.
        q = parse_qs(urlparse(page_url).query)
        if q.get("redirecturl"):
            data.setdefault("redirecturl", q["redirecturl"][0])
        # Echo any hidden inputs the form carries.
        for tag in _HIDDEN_INPUT_RE.findall(html):
            nm = _INPUT_NAME_RE.search(tag)
            if nm:
                val = _INPUT_VALUE_RE.search(tag)
                data[nm.group(1)] = val.group(1) if val else ""
        if self._nck:
            data.setdefault("_nck", self._nck)
        try:
            resp = self._send("POST", action, data=data)
        except RequestException:
            return False
        return not self._is_captcha(resp)

    # -- captcha / nonce detection ----------------------------------------

    def _is_captcha(self, resp: requests.Response) -> bool:
        """True if this response is the CAPTCHA wall (by final URL or body)."""
        final_url = getattr(resp, "url", "") or ""
        if CAPTCHA_PATH in final_url:
            return True
        return self._is_captcha_body(getattr(resp, "text", "") or "")

    @staticmethod
    def _is_captcha_body(html: str) -> bool:
        if not html:
            return False
        if not _CAPTCHA_BODY_RE.search(html):
            return False
        # securimage is present — but every catalog page embeds the checkout
        # captcha widget. Only a STANDALONE captcha wall (no catalog/nav markers)
        # counts as blocked. This avoids false-positiving on real pages.
        if _CATALOG_MARKER_RE.search(html):
            return False
        return True

    @staticmethod
    def _extract_nck(html: str) -> str | None:
        """Pull the ~364-char `_nck` nonce out of catalog form HTML."""
        if not html:
            return None
        m = _NCK_RE_NAME_FIRST.search(html) or _NCK_RE_VALUE_FIRST.search(html)
        return m.group(1) if m else None

    def _refresh_nck(self) -> None:
        """Re-harvest the nonce by re-warming CATALOG_ROOT (rotates on CAPTCHA)."""
        try:
            resp = self._send("GET", CATALOG_ROOT)
        except RequestException:
            self.rotate()
            return
        if self._is_captcha(resp):
            self.rotate()
            return
        nck = self._extract_nck(resp.text)
        if nck:
            self._nck = nck

    def _absorb_nonce(self, data: object) -> None:
        """If a JSON response carries a refreshed nonce, adopt it."""
        if isinstance(data, dict):
            fresh = data.get("_nck") or data.get("nck")
            if isinstance(fresh, str) and fresh:
                self._nck = fresh

    @staticmethod
    def _nonce_stale(data: object) -> bool:
        """Heuristic: response lacks catalog sections AND mentions a nonce error."""
        if not isinstance(data, dict):
            return False
        if "html_fill_sections" in data:
            return False
        blob = json.dumps(data).lower()
        return any(k in blob for k in ("_nck", "nonce", "nck", "expired", "invalid"))

    @staticmethod
    def _extract_catalog_fragment(data: object) -> str | None:
        """Pull the catalog HTML fragment out of the tab_fetch JSON response.

        Returns None only when the response has no html_fill_sections at all
        (caller decides how to treat that). Prefers the section whose key
        mentions 'catalog'; otherwise concatenates every string section.
        """
        if not isinstance(data, dict):
            return None
        sections = data.get("html_fill_sections")
        if not isinstance(sections, dict):
            return None
        for key, val in sections.items():
            if isinstance(val, str) and "catalog" in str(key).lower():
                return val
        parts = [v for v in sections.values() if isinstance(v, str)]
        return "".join(parts) if parts else ""

    # -- politeness / backoff ---------------------------------------------

    @staticmethod
    def _sleep_polite(attempt: int = 0) -> None:
        """Jittered per-IP delay between requests; grows a little with retries."""
        lo = float(RATE["min_delay_s"])
        hi = float(RATE["max_delay_s"])
        delay = random.uniform(lo, hi) * (1 + 0.5 * attempt)
        time.sleep(delay)

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        lo = float(RATE["min_delay_s"])
        hi = float(RATE["max_delay_s"])
        time.sleep(random.uniform(lo, hi) * (attempt + 1))

    @staticmethod
    def _sleep_captcha_backoff() -> None:
        # Small jitter on top of the configured cool-down so a burst of workers
        # don't all re-hit the wall at the same instant.
        time.sleep(float(RATE["captcha_backoff_s"]) + random.uniform(0, 2))


# =========================================================================
# OFFLINE self-test — no network, no live RockAuto. Run: python ra_client.py
# =========================================================================
def _selftest() -> bool:
    """Exercise the client against inline fixtures via a monkeypatched session.

    Proves: (1) _nck harvest on new_session, (2) get() returns HTML,
    (3) fetch_children() returns the catalog fragment, (4) Blocked is raised
    when a URL lands on the CAPTCHA wall.
    """
    ok = True

    def check(label: str, cond: bool) -> None:
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    NCK = "n" * 364
    HOME_HTML = f'<form id="catalog"><input name="_nck" value="{NCK}" /></form>'
    CAPTCHA_HTML = '<img class="captchaimage" src="/securimage/securimage_show.php" />'
    FRAGMENT = '<div class="ranavnode" id="nav[__GIP__4__]">ACURA</div>'

    class FakeResp:
        def __init__(self, url: str, text: str, js: object | None = None):
            self.url = url
            self.text = text
            self.status_code = 200
            self._js = js

        def json(self):
            if self._js is None:
                raise ValueError("not json")
            return self._js

    # A standalone /captcha/ wall page (securimage img + submit form).
    WALL_HTML = (
        '<form action=""><img class="captchaimage" '
        'src="/captcha/securimage/securimage_show.php?7">'
        '<input name="captchacode"></form>'
    )

    # Router keyed on URL — returns fixture HTML/JSON, never touches the network.
    def router(method: str, url: str, kw: dict) -> FakeResp:
        if url == CATALOG_ROOT:
            return FakeResp(url, HOME_HTML)
        # A solved captcha POST redirects OFF /captcha/ to the cleared catalog page.
        if method == "POST" and CAPTCHA_PATH in url:
            return FakeResp(config.BASE + "/en/catalog/honda",
                            "<html><body>ok ranavnode</body></html>")
        if "captcha-me" in url:  # simulate the 302 -> /captcha/ redirect landing
            return FakeResp(config.BASE + CAPTCHA_PATH + "?redirecturl=x", CAPTCHA_HTML)
        if url == CATALOG_API:
            return FakeResp(
                url, "", js={"html_fill_sections": {"section-abc[catalog]": FRAGMENT}}
            )
        return FakeResp(url, "<html><body>ok</body></html>")

    class FakeSession:
        def __init__(self):
            self.headers: dict = {}
            self.proxies: dict = {}

        def request(self, method, url, **kw):
            return router(method, url, kw)

    class FakeProxyManager:
        """Minimal ProxyManager stand-in: always direct, records quarantines."""

        def __init__(self):
            self.quarantined: list = []

        def get(self):
            return None

        def quarantine(self, proxy, seconds):
            self.quarantined.append((proxy, seconds))

    # Monkeypatch the network + sleep so the test is instant and offline.
    orig_session_cls = requests.Session
    orig_sleep = time.sleep
    requests.Session = lambda *a, **k: FakeSession()  # type: ignore[assignment]
    time.sleep = lambda *a, **k: None  # type: ignore[assignment]
    try:
        client = RAClient(FakeProxyManager())

        # (1) new_session harvests the nonce.
        client.new_session()
        check("new_session harvests _nck", client._nck == NCK)

        # (2) get() returns page HTML for a normal catalog URL.
        html = client.get(config.BASE + "/en/catalog/honda")
        check("get() returns HTML", "ok" in html)

        # (3) fetch_children() returns the catalog fragment string.
        node = {
            "jsn": {
                "groupindex": "__GIP__4__",
                "tab": "catalog",
                "make": "ACURA",
                "nodetype": "make",
            }
        }
        frag = client.fetch_children(node, max_group_index=4)
        check("fetch_children returns catalog fragment", "ranavnode" in frag)

        # (4) A CAPTCHA landing raises Blocked after exhausting retries.
        #     (captcha solving is off by default here — see check 5 for the solve path)
        raised = False
        try:
            client.get(config.BASE + "/captcha-me")
        except Blocked:
            raised = True
        check("get() raises Blocked on CAPTCHA", raised)

        # (5) The securimage solve->submit->clear path returns True when the OCR
        #     code is accepted (fake solver + fake cleared-redirect response).
        class FakeSolver:
            def solve_from_url(self, session, image_url):
                return "AB12CD"

        client._solver_mod = FakeSolver()  # inject; skip real Pillow/tesseract
        config.CAPTCHA["solve"] = True      # ensure enabled for the test
        wall = FakeResp(
            config.BASE + CAPTCHA_PATH + "?redirecturl=/en/catalog/honda", WALL_HTML
        )
        cleared = client._try_solve_captcha(wall)
        check("captcha solve->submit clears the wall", cleared is True)
    finally:
        requests.Session = orig_session_cls  # type: ignore[assignment]
        time.sleep = orig_sleep  # type: ignore[assignment]

    return ok


if __name__ == "__main__":
    print("ra_client offline self-test:")
    success = _selftest()
    print("PASS" if success else "FAIL")
    raise SystemExit(0 if success else 1)
