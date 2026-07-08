"""
Crawl scope + politeness + proxy configuration for the RockAuto pipeline.
Edit SCOPE to widen/narrow what gets crawled. Everything here is read by
crawl.py and the client/proxy modules — no magic numbers elsewhere.
"""
from __future__ import annotations
import os

BASE = "https://www.rockauto.com"
CATALOG_ROOT = f"{BASE}/en/catalog/"
CATALOG_API = f"{BASE}/catalog/catalogapi.php"
CAPTCHA_PATH = "/captcha/"  # redirect target when anti-bot fires

# ---- CRAWL SCOPE ---------------------------------------------------------
# The council's answer to "fast, within ~10h": crawl a bounded-but-broad slice
# first, then widen by editing this. Empty list = ALL (full catalog = weeks).
SCOPE = {
    # Lowercase make slugs as they appear in /en/catalog/<slug>. [] = every make.
    "makes": ["honda", "toyota", "subaru"],
    # Inclusive year range. RockAuto groups everything <2006 behind one filter.
    "year_min": int(os.getenv("SP_YEAR_MIN", "2010")),
    "year_max": int(os.getenv("SP_YEAR_MAX", "2024")),
    # Top-level category names to keep (lowercase substring match). [] = all.
    "categories": [],
    # Markets to include (RockAuto market checkboxes). US only = fewer nodes.
    "markets": ["US"],
}

# ---- POLITENESS / RATE LIMITING -----------------------------------------
RATE = {
    "min_delay_s": float(os.getenv("SP_MIN_DELAY", "1.5")),   # per-IP base delay
    "max_delay_s": float(os.getenv("SP_MAX_DELAY", "4.0")),   # jittered upper bound
    "concurrency": int(os.getenv("SP_CONCURRENCY", "6")),     # parallel workers (each on its own proxy)
    "request_timeout_s": 15,    # fail a blocked/slow request fast so shards turn over
    "max_attempts": 4,          # per-node retry budget before marking 'failed'
    "captcha_backoff_s": 90,    # cool-down for an IP that hit a CAPTCHA
}

# ---- CAPTCHA SOLVING -----------------------------------------------------
# RockAuto's wall is securimage (a weak PHP text-image CAPTCHA). captcha_solver
# cracks it locally with Tesseract OCR. When "solve" is on, ra_client tries to
# solve+submit the code (requesting fresh codes up to "attempts" times) BEFORE
# falling back to rotating the IP. Set SP_SOLVE_CAPTCHA=0 to disable (pure
# rotate-on-block behavior). Needs the tesseract binary (see requirements.txt);
# degrades gracefully to rotate() if it's absent.
CAPTCHA = {
    "solve": os.getenv("SP_SOLVE_CAPTCHA", "1") == "1",
    "attempts": int(os.getenv("SP_CAPTCHA_ATTEMPTS", "5")),
}

# ---- PROXY ROTATION ------------------------------------------------------
# Free proxy list sources (GitHub raw). proxy_manager fetches, health-checks,
# and quarantines. Treat every proxy as disposable. Set SP_USE_PROXIES=0 to
# crawl direct (single IP) for local testing.
PROXY = {
    "enabled": os.getenv("SP_USE_PROXIES", "1") == "1",
    "sources": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    ],
    "health_check_url": "https://www.rockauto.com/en/catalog/",
    "health_timeout_s": 8,
    "min_pool": 10,             # refill when healthy pool drops below this
    "pool_cache": "scraper/.proxy_pool.json",
    "refresh_interval_s": 1800,
}

# Rotating realistic browser identities. client picks one per session.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
]

BATCH_ID = os.getenv("SP_BATCH_ID", "")  # set at runtime by crawl.py if empty
