"""
Frontier queue for the RockAuto crawler (Agent D).

A tiny durable work-queue on top of the `crawl_frontier` table. Every catalog
node the crawler discovers is a row here, so the crawl is fully resumable: kill
the process at any point and re-running continues from whatever is still
`pending` / `in_flight`.

Columns (see database/staging.sql + scrape_schema.sql):
    id, node_type, node_key, href,
    status ENUM('pending','in_flight','done','failed'),
    attempts, batch_id, payload(JSON), updated_at

Idempotency anchor: UNIQUE KEY uq_frontier_node(node_type, node_key).

Every mutating call commits on success so queue state survives a crash. The
caller (crawl.py) passes a live pymysql connection from scraper/db.py.

Contract (CONTRACT.md §3):
    enqueue(conn, node_type, node_key, href=None, payload=None) -> None
    claim_batch(conn, limit=50) -> list[dict]
    complete(conn, id) -> None
    fail(conn, id) -> None
    counts(conn) -> dict
"""
from __future__ import annotations

import json
from typing import Any

try:  # run as `python scraper/crawl.py` (scraper/ on sys.path) OR as package
    import config
except ImportError:  # pragma: no cover - import shim
    from scraper import config  # type: ignore

# The four canonical states, so counts() always returns every key.
_STATUSES = ("pending", "in_flight", "done", "failed")

# Cache of whether the additive `payload` column exists (scrape_schema.sql).
# Keyed by nothing — the schema does not change under a running process.
_PAYLOAD_COL: bool | None = None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _payload_supported(conn) -> bool:
    """True if crawl_frontier has the (additive) `payload` JSON column.

    Lets the module degrade gracefully on a DB where scrape_schema.sql was not
    applied yet, instead of exploding on an unknown column.
    """
    global _PAYLOAD_COL
    if _PAYLOAD_COL is None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'crawl_frontier' "
                "AND COLUMN_NAME = 'payload'"
            )
            row = cur.fetchone()
        _PAYLOAD_COL = bool(row and row["c"])
    return _PAYLOAD_COL


def _encode_payload(payload: Any) -> str | None:
    """dict/list -> compact JSON text; str passes through; None stays None."""
    if payload is None:
        return None
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _decode_payload(value: Any) -> Any:
    """JSON text (as pymysql returns it) -> Python object. Robust to junk."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", "replace")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None
    return None


def _max_attempts() -> int:
    """Per-node retry budget from config.RATE (default 4)."""
    try:
        return int(config.RATE["max_attempts"])
    except Exception:  # noqa: BLE001 - config missing/edited; sane fallback
        return 4


# --------------------------------------------------------------------------- #
# public API (CONTRACT §3)
# --------------------------------------------------------------------------- #
def enqueue(conn, node_type, node_key, href=None, payload=None) -> None:
    """Idempotently add a node to the frontier.

    Safe to call repeatedly for the same (node_type, node_key): the UNIQUE key
    absorbs the duplicate. On a repeat we refresh href/payload *only when a new
    value is supplied* (COALESCE keeps the old one on NULL) and NEVER touch
    `status` or `attempts` — so a node already 'done' stays done and is not
    resurrected on a re-seed. That is what makes re-runs continue instead of
    restart.
    """
    supported = _payload_supported(conn)
    with conn.cursor() as cur:
        if supported:
            cur.execute(
                "INSERT INTO crawl_frontier "
                "  (node_type, node_key, href, status, payload) "
                "VALUES (%s, %s, %s, 'pending', %s) "
                "ON DUPLICATE KEY UPDATE "
                "  href    = COALESCE(VALUES(href), href), "
                "  payload = COALESCE(VALUES(payload), payload)",
                (node_type, node_key, href, _encode_payload(payload)),
            )
        else:
            cur.execute(
                "INSERT INTO crawl_frontier "
                "  (node_type, node_key, href, status) "
                "VALUES (%s, %s, %s, 'pending') "
                "ON DUPLICATE KEY UPDATE "
                "  href = COALESCE(VALUES(href), href)",
                (node_type, node_key, href),
            )
    conn.commit()


def claim_batch(conn, limit=50) -> list[dict]:
    """Atomically move up to `limit` pending nodes -> in_flight and return them.

    Uses `SELECT ... FOR UPDATE` inside the transaction to lock the chosen
    pending rows, flips them to 'in_flight', stamps the current run batch_id
    (config.BATCH_ID, set by crawl.py at startup), then commits to release the
    locks. Returned rows carry the DECODED payload so the caller has the node's
    jsn + accumulated fitment context without a second query.

    Returns [] when the queue has no pending work (crawl termination signal).
    """
    supported = _payload_supported(conn)
    payload_sel = ", payload" if supported else ""
    batch_id = getattr(config, "BATCH_ID", "") or None

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, node_type, node_key, href, attempts" + payload_sel + " "
            "FROM crawl_frontier "
            "WHERE status = 'pending' "
            "ORDER BY id "
            "LIMIT %s "
            "FOR UPDATE",
            (int(limit),),
        )
        rows = list(cur.fetchall())
        if rows:
            ids = [r["id"] for r in rows]
            placeholders = ", ".join(["%s"] * len(ids))
            cur.execute(
                "UPDATE crawl_frontier "
                "SET status = 'in_flight', batch_id = %s "
                "WHERE id IN (" + placeholders + ")",
                [batch_id, *ids],
            )
    conn.commit()

    for r in rows:
        # Guarantee the key exists even on a payload-less schema.
        r["payload"] = _decode_payload(r.get("payload"))
    return rows


def complete(conn, id) -> None:  # noqa: A002 - name mandated by CONTRACT
    """Mark a node fully processed."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE crawl_frontier SET status = 'done' WHERE id = %s",
            (id,),
        )
    conn.commit()


def fail(conn, id) -> None:  # noqa: A002 - name mandated by CONTRACT
    """Record a failed attempt.

    attempts++ then: back to 'pending' for another try while attempts <
    RATE.max_attempts, otherwise park it as 'failed'. The +1 in the guard
    matches the freshly incremented value in the same statement, so the row is
    never silently lost — it is always either retryable or explicitly failed.
    """
    max_attempts = _max_attempts()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE crawl_frontier "
            "SET attempts = attempts + 1, "
            "    status = IF(attempts + 1 >= %s, 'failed', 'pending') "
            "WHERE id = %s",
            (max_attempts, id),
        )
    conn.commit()


def counts(conn) -> dict:
    """Snapshot of queue depth by status, e.g.
    {'pending': 12, 'in_flight': 3, 'done': 480, 'failed': 1}.
    Every status key is always present (0 when absent)."""
    out = {s: 0 for s in _STATUSES}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, COUNT(*) AS c FROM crawl_frontier GROUP BY status"
        )
        for row in cur.fetchall():
            out[row["status"]] = int(row["c"])
    return out


def reset(conn, node_key_prefix: str | None = None) -> int:
    """Clear frontier rows (used by `crawl.py --reset`).

    With no prefix: wipe the whole queue for a clean re-crawl. With a prefix:
    only rows whose node_key starts with it (used by the self-test to scrub its
    'selftest:' rows). Returns the number of rows deleted.
    """
    with conn.cursor() as cur:
        if node_key_prefix:
            n = cur.execute(
                "DELETE FROM crawl_frontier WHERE node_key LIKE %s",
                (node_key_prefix + "%",),
            )
        else:
            n = cur.execute("DELETE FROM crawl_frontier")
    conn.commit()
    return int(n)


# --------------------------------------------------------------------------- #
# OFFLINE self-test  (no live RockAuto site; only the local DB)
# --------------------------------------------------------------------------- #
def _selftest() -> bool:
    """Exercise enqueue/claim/complete/fail/counts against the REAL db using a
    throwaway 'selftest:' node_key prefix, then clean up. Non-selftest rows are
    snapshotted and restored so a live frontier is never disturbed. If the DB is
    unreachable, prints SKIP and reports success (nothing to test)."""
    try:  # dual import so the file runs both as script and as package member
        import db
    except ImportError:
        from scraper import db  # type: ignore

    if not db.ping():
        print("SKIP: database unreachable (skipping frontier self-test)")
        return True

    PFX = "selftest:"
    conn = db.connect()
    # Snapshot every non-selftest row so we can restore anything claim_batch
    # happens to flip (claim_batch is global — it does not filter by prefix).
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, status, attempts, batch_id FROM crawl_frontier "
            "WHERE node_key NOT LIKE %s",
            (PFX + "%",),
        )
        snapshot = list(cur.fetchall())

    ok = True

    def check(cond: bool, label: str) -> None:
        nonlocal ok
        flag = "ok  " if cond else "FAIL"
        if not cond:
            ok = False
        print(f"  [{flag}] {label}")

    def st_count(status: str) -> int:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM crawl_frontier "
                "WHERE node_key LIKE %s AND status = %s",
                (PFX + "%", status),
            )
            return int(cur.fetchone()["c"])

    def st_row(node_key: str) -> dict | None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, attempts, payload FROM crawl_frontier "
                "WHERE node_key = %s",
                (node_key,),
            )
            return cur.fetchone()

    try:
        # clean slate for our prefix
        reset(conn, PFX)

        # 1) enqueue is idempotent + stores payload -----------------------
        enqueue(conn, "make", PFX + "honda", "/en/catalog/honda",
                payload={"jsn": {"nodetype": "make"}, "depth": 0})
        enqueue(conn, "make", PFX + "toyota", "/en/catalog/toyota")
        enqueue(conn, "year", PFX + "y2015", "/en/catalog/honda,2015")
        # duplicate enqueue must NOT create a second row
        enqueue(conn, "make", PFX + "honda", "/en/catalog/honda")
        check(st_count("pending") == 3, "enqueue seeded 3 pending, dup ignored")

        r = st_row(PFX + "honda")
        payload = _decode_payload(r["payload"]) if r else None
        check(isinstance(payload, dict) and payload.get("depth") == 0,
              "payload round-trips through the DB as JSON")

        # 2) claim_batch flips pending -> in_flight and decodes payload ----
        batch = claim_batch(conn, limit=50)
        mine = [b for b in batch if b["node_key"].startswith(PFX)]
        check(len(mine) == 3, "claim_batch returned our 3 nodes")
        honda = next((b for b in mine if b["node_key"] == PFX + "honda"), None)
        check(honda is not None
              and isinstance(honda["payload"], dict)
              and honda["payload"].get("jsn", {}).get("nodetype") == "make",
              "claimed row carries decoded payload")
        check(st_count("in_flight") == 3 and st_count("pending") == 0,
              "claimed nodes are now in_flight")

        # 3) complete() finalizes a node ----------------------------------
        complete(conn, honda["id"])
        check(st_row(PFX + "honda")["status"] == "done", "complete -> done")

        # 4) fail() retries then parks as failed after max_attempts -------
        toy = next(b for b in mine if b["node_key"] == PFX + "toyota")
        fail(conn, toy["id"])
        after1 = st_row(PFX + "toyota")
        check(after1["status"] == "pending" and after1["attempts"] == 1,
              "first fail -> back to pending, attempts=1")
        maxa = _max_attempts()
        # burn the remaining budget; after attempts>=maxa it must be 'failed'
        for _ in range(maxa):
            fail(conn, toy["id"])
        final = st_row(PFX + "toyota")
        check(final["status"] == "failed" and final["attempts"] >= maxa,
              f"exhausting {maxa} attempts -> failed")

        # 5) counts() returns all four keys -------------------------------
        c = counts(conn)
        check(all(k in c for k in _STATUSES),
              "counts() returns every status key")

    finally:
        # scrub our rows, then restore any live rows claim_batch touched
        try:
            reset(conn, PFX)
            with conn.cursor() as cur:
                for s in snapshot:
                    cur.execute(
                        "UPDATE crawl_frontier "
                        "SET status = %s, attempts = %s, batch_id = %s "
                        "WHERE id = %s",
                        (s["status"], s["attempts"], s["batch_id"], s["id"]),
                    )
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] cleanup/restore issue: {exc}")
        conn.close()

    print("PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    import sys

    sys.exit(0 if _selftest() else 1)
