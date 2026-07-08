"""
purge_synthetic.py — remove the synthetic 'generated' demo parts so the storefront
shows ONLY real crawled RockAuto data.

Synthetic parts are identified precisely: their sku is reconstructed from the
source='generated' staging rows using the SAME slugify the loader used. Multiple
safety guards protect real data:
  * skus that also came from a real source (rockauto/aces_pies) are NEVER deleted
  * any part with a self-hosted local image is NEVER deleted

Deleting a part CASCADEs its part_images/part_attributes/part_fitment/etc. After
the parts go, orphaned dimensions (vehicles with no fitment, models/makes with no
vehicles, brands/categories with no parts) are cleaned too.

    python bin/purge_synthetic.py            # DRY RUN — shows what would happen
    python bin/purge_synthetic.py --apply    # actually delete
"""
from __future__ import annotations
import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scraper"))
import db          # noqa: E402
import crawl as C  # noqa: E402  (slugify / make_sku — identical to the loader)


def synthetic_skus(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT brand_name, part_number FROM stg_listings WHERE source='generated'")
        gen = {C.make_sku(r["brand_name"], r["part_number"]) for r in cur.fetchall()}
        cur.execute("SELECT brand_name, part_number FROM stg_listings WHERE source IN ('rockauto','aces_pies')")
        real = {C.make_sku(r["brand_name"], r["part_number"]) for r in cur.fetchall()}
    return gen - real  # never delete a sku that also has a real listing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default is dry-run)")
    args = ap.parse_args()
    if not db.ping():
        print("DB unreachable"); return 1
    conn = db.connect()
    try:
        skus = synthetic_skus(conn)
        print(f"synthetic skus reconstructed from staging: {len(skus)}")
        if not skus:
            print("nothing to purge"); return 0

        with conn.cursor() as cur:
            # Parts to delete: sku in the synthetic set AND without a local image (guard).
            cur.execute("CREATE TEMPORARY TABLE _syn (sku VARCHAR(120) PRIMARY KEY)")
            cur.executemany("INSERT IGNORE INTO _syn (sku) VALUES (%s)", [(s,) for s in skus])
            cur.execute(
                "SELECT COUNT(*) n FROM parts p JOIN _syn ON _syn.sku=p.sku "
                "WHERE p.primary_image_path IS NULL OR p.primary_image_path NOT LIKE '/RockAuto/assets/%'")
            to_delete = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) n FROM parts")
            total = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) n FROM parts WHERE primary_image_path LIKE '/RockAuto/assets/%'")
            protected_img = cur.fetchone()["n"]

            print(f"parts total={total}  to_delete={to_delete}  "
                  f"protected(local image)={protected_img}  keeping={total - to_delete}")

            if not args.apply:
                print("\nDRY RUN — re-run with --apply to delete. Nothing changed.")
                return 0

            print("\nAPPLYING…")
            cur.execute(
                "DELETE p FROM parts p JOIN _syn ON _syn.sku=p.sku "
                "WHERE p.primary_image_path IS NULL OR p.primary_image_path NOT LIKE '/RockAuto/assets/%'")
            print(f"  deleted {cur.rowcount} synthetic parts (children cascaded)")
            # Orphan cleanup — order matters (children first).
            cur.execute("DELETE pf FROM part_fitment pf LEFT JOIN parts p ON p.id=pf.part_id WHERE p.id IS NULL")
            cur.execute("DELETE v FROM vehicles v LEFT JOIN part_fitment pf ON pf.vehicle_id=v.id WHERE pf.id IS NULL")
            print(f"  removed {cur.rowcount} orphaned vehicles")
            cur.execute("DELETE m FROM models m LEFT JOIN vehicles v ON v.model_id=m.id WHERE v.id IS NULL")
            print(f"  removed {cur.rowcount} orphaned models")
            cur.execute("DELETE mk FROM makes mk LEFT JOIN vehicles v ON v.make_id=mk.id WHERE v.id IS NULL")
            print(f"  removed {cur.rowcount} orphaned makes")
            cur.execute("DELETE b FROM brands b LEFT JOIN parts p ON p.brand_id=b.id WHERE p.id IS NULL")
            print(f"  removed {cur.rowcount} orphaned brands")
            cur.execute("DELETE c FROM categories c LEFT JOIN parts p ON p.category_id=c.id "
                        "LEFT JOIN categories ch ON ch.parent_id=c.id WHERE p.id IS NULL AND ch.id IS NULL")
            print(f"  removed {cur.rowcount} orphaned leaf categories")
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT (SELECT COUNT(*) FROM parts) p,(SELECT COUNT(*) FROM makes) m,"
                        "(SELECT COUNT(*) FROM vehicles) v")
            r = cur.fetchone()
            print(f"\nDONE. Now: parts={r['p']}  makes={r['m']}  vehicles={r['v']}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
