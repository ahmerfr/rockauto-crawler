"""
dump_listing.py — print RockAuto's RAW markup for one leaf page so we can fix the
parser against ground truth instead of guessing.

Walks make -> year -> model -> carcode -> groupname -> parttype by matching node
labels, then for every listing row on the leaf prints:
  * the part number
  * the price cell's raw HTML  (single $ vs a <select> of inventory options)
  * every <option>: its text and whether it is `selected`  <- decides the headline price
  * every image URL found for that row                     <- decides how many photos exist

Runs on a GitHub runner (our dev IP is blocked). Usage:
    python scraper/dump_listing.py --make ac --year 1962 --model ace \
        --group "Wiper & Washer" --parttype "Wiper Blade" --part 18160
"""
from __future__ import annotations

import argparse
import os
import re
import sys

try:
    import config, parsers
    from ra_client import RAClient
except ImportError:  # pragma: no cover
    from scraper import config, parsers  # type: ignore
    from scraper.ra_client import RAClient  # type: ignore

from bs4 import BeautifulSoup


def _label(n: dict) -> str:
    for k in ("label", "parttype", "groupname", "model", "engine", "make", "year"):
        v = n.get(k)
        if v:
            return str(v)
    return ""


def pick(nodes: list[dict], ntype: str, want: str | None) -> dict | None:
    cands = [n for n in nodes if n.get("nodetype") == ntype]
    print(f"  [{ntype}] {len(cands)} candidates: "
          f"{[_label(c) for c in cands][:12]}", flush=True)
    if not cands:
        return None
    if not want:
        return cands[0]
    w = want.strip().lower()
    for n in cands:
        if w == _label(n).strip().lower():
            return n
    for n in cands:
        if w in _label(n).strip().lower():
            return n
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--make", default="ac")
    ap.add_argument("--year", default="1962")
    ap.add_argument("--model", default="ace")
    ap.add_argument("--engine", default=None)
    ap.add_argument("--group", default="Wiper & Washer")
    ap.add_argument("--parttype", default="Wiper Blade")
    ap.add_argument("--part", default="18160", help="only dump this part number (blank = all)")
    ap.add_argument("--scan", default="", help="comma list of literals to hunt in the RAW page")
    ap.add_argument("--survey", type=int, default=0,
                    help="walk N part-type leaves under the vehicle and report EVERY "
                         "<select> id pattern + option counts (are all dropdowns "
                         "optionchoice[N]? does any listing carry more than one?)")
    args = ap.parse_args()

    client = RAClient(None)
    client.new_session()

    def kids(href):
        return parsers.parse_nav(client.get(href))

    print(f"[walk] make={args.make}", flush=True)
    html = client.get(f"/en/catalog/{args.make}")
    node = pick(parsers.parse_nav(html), "year", args.year)
    if not node:
        print("FAIL: year not found"); return 1

    node = pick(kids(node["href"]), "model", args.model)
    if not node:
        print("FAIL: model not found"); return 1

    node = pick(kids(node["href"]), "carcode", args.engine)
    if not node:
        print("FAIL: carcode not found"); return 1

    carcode_node = node

    # ---- SURVEY: how uniform is the dropdown markup across many leaves? -------
    if args.survey:
        groups = [n for n in kids(carcode_node["href"]) if n.get("nodetype") == "groupname"]
        print(f"\n[survey] {len(groups)} groups under this vehicle", flush=True)
        id_pat: dict[str, int] = {}
        multi_select_rows = 0
        rows_with_select = 0
        rows_total = 0
        max_opts = 0
        leaves_done = 0
        for g in groups:
            if leaves_done >= args.survey:
                break
            for pt in [n for n in kids(g["href"]) if n.get("nodetype") == "parttype"]:
                if leaves_done >= args.survey:
                    break
                leaves_done += 1
                lsoup = BeautifulSoup(client.get(pt["href"]), "lxml")
                row_ids = [re.match(r"^listingtd\[(\d+)\]\[price\]$", e.get("id")).group(1)
                           for e in lsoup.find_all(id=re.compile(r"^listingtd\[\d+\]\[price\]$"))]
                rows_total += len(row_ids)
                for sel in lsoup.find_all("select"):
                    sid = sel.get("id") or "(no-id)"
                    pat = re.sub(r"\d+", "N", sid)
                    id_pat[pat] = id_pat.get(pat, 0) + 1
                    n_opts = len([o for o in sel.find_all("option") if (o.get("value") or "").strip()])
                    max_opts = max(max_opts, n_opts)
                for ridx in row_ids:
                    sels = lsoup.find_all("select", id=re.compile(rf"^optionchoice\[{ridx}\]"))
                    if len(sels) >= 1:
                        rows_with_select += 1
                    if len(sels) > 1:
                        multi_select_rows += 1
                print(f"  [{leaves_done}] {_label(g)} > {_label(pt)}: "
                      f"{len(row_ids)} rows", flush=True)
        print("\n" + "=" * 70, flush=True)
        print(f"[survey] leaves={leaves_done} listing_rows={rows_total}", flush=True)
        print(f"[survey] rows carrying an optionchoice select: {rows_with_select}", flush=True)
        print(f"[survey] rows with MORE THAN ONE optionchoice select: {multi_select_rows}", flush=True)
        print(f"[survey] max options in any select: {max_opts}", flush=True)
        print("[survey] every <select> id pattern seen on these pages:", flush=True)
        for pat, n in sorted(id_pat.items(), key=lambda kv: -kv[1]):
            print(f"    {n:>5}x  {pat}", flush=True)
        print("=" * 70, flush=True)
        return 0

    node = pick(kids(node["href"]), "groupname", args.group)
    if not node:
        print("FAIL: groupname not found"); return 1

    node = pick(kids(node["href"]), "parttype", args.parttype)
    if not node:
        print("FAIL: parttype not found"); return 1

    leaf_url = node["href"]
    print(f"\n[leaf] {leaf_url}\n", flush=True)
    leaf_html = client.get(leaf_url)
    soup = BeautifulSoup(leaf_html, "lxml")

    # --- RAW SCAN: is the JS-rendered data (inventory tiers, extra photos) even
    # present in the server HTML, or fetched later by AJAX? -------------------
    if args.scan:
        print("#" * 78, flush=True)
        print(f"[raw scan] page length = {len(leaf_html)} chars", flush=True)
        for needle in [s for s in args.scan.split(",") if s]:
            hits = [m.start() for m in re.finditer(re.escape(needle), leaf_html, re.I)]
            print(f"\n=== {needle!r}: {len(hits)} hit(s) ===", flush=True)
            for h in hits[:4]:
                lo, hi = max(0, h - 220), min(len(leaf_html), h + 260)
                print(f"  …{leaf_html[lo:hi]!r}…", flush=True)
        # every RockAuto product photo referenced ANYWHERE on the page
        photos = sorted(set(re.findall(r"[^\"'\s]*?/info/[^\"'\s]*?_ra_[a-z]\.jpg", leaf_html, re.I)))
        print(f"\n=== all /info/ *_ra_*.jpg on page: {len(photos)} ===", flush=True)
        for p in photos[:40]:
            print(f"   {p}", flush=True)
        print("#" * 78, flush=True)

    # Every listing row is keyed by an index N appearing in listingtd[N][...] ids.
    idxs = []
    for el in soup.find_all(id=re.compile(r"^listingtd\[(\d+)\]\[price\]$")):
        m = re.match(r"^listingtd\[(\d+)\]\[price\]$", el.get("id"))
        if m:
            idxs.append(m.group(1))
    print(f"[rows] {len(idxs)} listing rows: {idxs}\n", flush=True)

    for idx in idxs:
        # part number for this row
        pn_el = soup.find(id=f"vew_partnumber[{idx}]") or soup.find(id=f"listingtd[{idx}][partnumber]")
        pn = pn_el.get_text(" ", strip=True) if pn_el else "?"
        if args.part and args.part not in (pn or "") and args.part != "":
            # also allow matching anywhere in the row text
            row = soup.find(id=f"listingtd[{idx}][price]")
            rowtxt = row.parent.get_text(" ", strip=True) if row and row.parent else ""
            if args.part not in rowtxt:
                continue

        print("=" * 78, flush=True)
        print(f"ROW idx={idx}  part_number={pn!r}", flush=True)

        pcell = soup.find(id=f"listingtd[{idx}][price]") or soup.find(id=f"dprice[{idx}][td]")
        print("\n--- PRICE CELL RAW HTML ---", flush=True)
        print((str(pcell)[:1500] if pcell else "(none)"), flush=True)

        # The inventory-tier <select> is NOT in the price cell — it's optionchoice[N].
        print("\n--- optionchoice[N] SELECT (selected flag = headline price) ---", flush=True)
        sel = soup.find("select", id=f"optionchoice[{idx}]")
        if sel is None:
            print("(no optionchoice select: single-price part)", flush=True)
        else:
            for opt in sel.find_all("option"):
                print(f"  selected={opt.has_attr('selected')!s:<5} "
                      f"value={opt.get('value')!r:<12} text={opt.get_text(' ', strip=True)!r}",
                      flush=True)

        print("\n--- per-option price/core breakdown inputs ---", flush=True)
        for inp in soup.find_all("input", id=re.compile(
                rf"^(price|core)breakdown\[{re.escape(idx)}\]\[")):
            print(f"  {inp.get('id')} = {inp.get('value')}", flush=True)

        # sibling spans that may hold the displayed headline price
        for extra in (f"dprice[{idx}]", f"dprice[{idx}][v]", f"dprice[{idx}][a]"):
            e = soup.find(id=extra)
            if e is not None:
                print(f"\n--- {extra} --- {e.get_text(' ', strip=True)!r}", flush=True)

        print("\n--- IMAGES for this row ---", flush=True)
        found = parsers._extract_product_images(soup, idx)
        print(f"parser._extract_product_images -> {len(found)} url(s)", flush=True)
        for u in found:
            print(f"   {u}", flush=True)

        # Does the part's "Info" (moreinfo.php) page hold the carousel's other photos?
        info = None
        for a in soup.find_all("a", href=True):
            if "moreinfo.php" in a["href"] and f"[{idx}]" in str(a.parent)[:400]:
                info = a["href"]
                break
        if info is None:
            row = soup.find(id=f"vew_partnumber[{idx}]")
            anc = row.find_parent("tr") if row else None
            if anc:
                a = anc.find("a", href=re.compile("moreinfo.php"))
                info = a["href"] if a else None
        print(f"\n--- moreinfo.php for this row: {info} ---", flush=True)
        if info:
            try:
                ihtml = client.get(info)
                iph = sorted(set(re.findall(r"[^\"'\s]*?/info/[^\"'\s]*?_ra_[a-z]\.jpg", ihtml, re.I)))
                print(f"  moreinfo page length={len(ihtml)}  _ra_ photos={len(iph)}", flush=True)
                for u in iph[:30]:
                    print(f"    {u}", flush=True)
                isoup = BeautifulSoup(ihtml, "lxml")
                srcs = []
                for im in isoup.find_all("img"):
                    for at in ("data-src", "data-original", "src"):
                        if im.get(at):
                            srcs.append(im[at]); break
                print(f"  ALL <img> on moreinfo: {len(srcs)}", flush=True)
                for u in srcs[:25]:
                    print(f"    img: {u}", flush=True)
                anyinfo = sorted(set(re.findall(r"[^\"'\s]{0,60}/info/[^\"'\s]{0,80}", ihtml, re.I)))
                print(f"  any '/info/' strings: {len(anyinfo)}", flush=True)
                for u in anyinfo[:15]:
                    print(f"    info: {u}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  moreinfo fetch failed: {exc}", flush=True)

        # Where does the LEAF page keep the carousel's image list for this row?
        print("\n--- carousel data on the LEAF page for this row ---", flush=True)
        for inp in soup.find_all("input", id=re.compile(rf"^\w*image\w*\[{re.escape(idx)}\]", re.I)):
            print(f"  {inp.get('id')} = {str(inp.get('value'))[:400]}", flush=True)
        for needle in ("imagecounter", "InlineImageManualScroll", "imgurl", "imagecount"):
            hits = [m.start() for m in re.finditer(re.escape(needle) + rf"\[?{re.escape(idx)}?", leaf_html, re.I)]
            if hits:
                h = hits[0]
                print(f"  [{needle}] first ctx: …{leaf_html[max(0,h-160):h+240]!r}…", flush=True)
        for cid in (f"inlineimg_container[{idx}]", f"listing_image_table[{idx}]"):
            cont = soup.find(id=cid)
            if cont is None:
                continue
            print(f"\n  [{cid}] RAW (first 1200 chars):", flush=True)
            print("  " + str(cont)[:1200], flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
