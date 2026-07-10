"""
block_probe.py — measure RockAuto's per-IP block behaviour, the ONE fact that
decides whether a paid-IP fleet can ever crawl the full catalog.

Two questions:
  1. How many requests does ONE fresh IP get before RockAuto blocks it? (does a
     slower rate raise that ceiling => rate-limit, or is it a fixed volume cap?)
  2. After the block, does the SAME IP RECOVER after a pause (rate-limit, good)
     or stay dead (hard per-IP cap, fatal for a scrape-the-whole-thing plan)?

Run on a fresh GitHub/Azure IP. Env PROBE_DELAY = seconds between requests.
Prints a JSON verdict line the council/aggregator can read.
"""
from __future__ import annotations
import json
import os
import time

try:
    import config
    from ra_client import RAClient, Blocked
    import parsers
except ImportError:
    from scraper import config, parsers  # type: ignore
    from scraper.ra_client import RAClient, Blocked  # type: ignore

DELAY = float(os.getenv("PROBE_DELAY", "2.0"))
PAUSE = int(os.getenv("PROBE_PAUSE", "900"))       # cool-down to test recovery (15 min)
MAXREQ = int(os.getenv("PROBE_MAXREQ", "1200"))    # stop if we somehow never block


def _walk_urls(client):
    """Yield real catalog URLs to fetch: make pages, then year pages, forever."""
    makes = [n for n in parsers.parse_nav(client.get(config.CATALOG_ROOT))
             if n.get("nodetype") == "make" and n.get("href")]
    for m in makes:
        yield m["href"]
        try:
            yrs = [n for n in parsers.parse_nav(client.get(m["href"]))
                   if n.get("nodetype") == "year" and n.get("href")]
        except Blocked:
            raise
        for y in yrs:
            yield y["href"]


def run() -> dict:
    client = RAClient(None)     # direct: the runner's own fresh IP
    client.new_session()
    ok = 0
    blocked_at = None
    for url in _walk_urls(client):
        try:
            client.get(url)
            ok += 1
        except Blocked:
            blocked_at = ok
            break
        if ok >= MAXREQ:
            break
        time.sleep(DELAY)

    recovered = None
    if blocked_at is not None:
        # Same IP (no rotate): wait, then try ONE request. Works => rate-limit.
        time.sleep(PAUSE)
        try:
            client._session = None  # fresh cookies, SAME IP (no proxy)
            client.new_session()
            client.get(config.CATALOG_ROOT)
            recovered = True
        except Blocked:
            recovered = False

    verdict = {
        "delay_s": DELAY, "requests_before_block": blocked_at,
        "reached_max_no_block": blocked_at is None and ok >= MAXREQ,
        "ok_requests": ok,
        "recovered_after_%ds" % PAUSE: recovered,
        "interpretation": (
            "NO_BLOCK" if blocked_at is None else
            "RATE_LIMIT_recovers" if recovered else
            "HARD_PER_IP_CAP_stays_blocked"),
    }
    print("PROBE_VERDICT " + json.dumps(verdict), flush=True)
    return verdict


if __name__ == "__main__":
    run()
