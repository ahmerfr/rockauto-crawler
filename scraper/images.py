"""
images.py — self-host RockAuto part thumbnails.

Your local IP is blocked by RockAuto, so hotlinked images can't load in your
browser. The GitHub crawl runner ISN'T blocked, so it downloads each part's
thumbnail during the crawl; the files ride along in the artifact and land under
assets/parts/ locally, served by your own Apache at /RockAuto/assets/parts/...

A RockAuto photo URL like  https://www.rockauto.com/info/111/854059-FRO__ra_m.jpg
maps to the stable relative path  111/854059-FRO__ra_m.jpg  (preserving RockAuto's
/info/<n>/ sharding so filenames never collide), stored at
  assets/parts/111/854059-FRO__ra_m.jpg
and referenced on the storefront as  /RockAuto/assets/parts/111/854059-FRO__ra_m.jpg
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

WEB_PREFIX = "/RockAuto/assets/parts/"
_INFO_RE = re.compile(r"/info/(.+)$")


def rel_path_for(url: str) -> str | None:
    """Stable relative path (e.g. '111/854059-FRO__ra_m.jpg') for a RockAuto
    /info photo URL, or None if the URL isn't a recognisable part photo."""
    if not url:
        return None
    path = urlparse(url).path
    m = _INFO_RE.search(path)
    if not m:
        return None
    tail = m.group(1)
    # Sanitise to a safe on-disk path (keep the /<n>/ sharding).
    tail = re.sub(r"[^A-Za-z0-9._/-]", "_", tail)
    return tail.lstrip("/")


def web_path(rel: str) -> str:
    """Storefront URL for a stored image rel-path."""
    return WEB_PREFIX + rel.replace(os.sep, "/")


def download(session, url: str, dest_root: str, timeout: int = 20) -> str | None:
    """Download one thumbnail into dest_root/<rel>, returning its storefront web
    path (or None on any failure). Idempotent: skips a file already on disk."""
    rel = rel_path_for(url)
    if rel is None:
        return None
    dest = os.path.join(dest_root, rel.replace("/", os.sep))
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return web_path(rel)
    try:
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 200 and resp.content:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            tmp = dest + ".part"
            with open(tmp, "wb") as fh:
                fh.write(resp.content)
            os.replace(tmp, dest)
            return web_path(rel)
    except Exception:  # noqa: BLE001 - a single bad image never breaks the crawl
        pass
    return None


def _selftest() -> bool:
    ok = True

    def chk(label, cond):
        nonlocal ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    chk("rel_path_for maps /info url",
        rel_path_for("https://www.rockauto.com/info/111/854059-FRO__ra_m.jpg")
        == "111/854059-FRO__ra_m.jpg")
    chk("rel_path_for rejects non-info", rel_path_for("https://x/flag_us.png") is None)
    chk("web_path", web_path("111/x.jpg") == "/RockAuto/assets/parts/111/x.jpg")
    print("PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if _selftest() else 1)
