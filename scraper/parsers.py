"""
scraper/parsers.py  —  Agent C (Parsers)

Pure, network-free HTML parsing for the RockAuto pipeline. Everything here takes
raw HTML (already fetched by ra_client.py) and emits the canonical dict shapes
defined in scraper/CONTRACT.md §2:

  * parse_nav(html)        -> list[TreeNode]   (catalog navigation nodes)
  * extract_nck(html)      -> str | None       (the _nck POST nonce)
  * parse_listings(html,ctx) -> list[Listing]  (part rows on a leaf page)
  * is_captcha(html, url)  -> bool             (soft-ban / CAPTCHA detector)

Design rules (see CONTRACT §3):
  * Use BeautifulSoup(lxml).
  * Be DEFENSIVE — RockAuto markup drifts. Try class selectors first, then fall
    back to regex / text / data-* attributes.
  * A single malformed row must be skipped, never raise. One bad part never
    kills the whole page.

Self-test at the bottom runs fully OFFLINE against inline fixtures.
"""
from __future__ import annotations

import html as _htmllib
import json
import re

from bs4 import BeautifulSoup

# BASE is used to absolutise relative image / doc URLs. Imported from config so
# there is one source of truth; falls back to a literal if config is unavailable
# (keeps this module importable in isolation for unit tests).
try:  # pragma: no cover - trivial import guard
    from scraper.config import BASE  # type: ignore
except Exception:  # pragma: no cover
    try:
        from config import BASE  # type: ignore
    except Exception:
        BASE = "https://www.rockauto.com"

CAPTCHA_PATH = "/captcha/"

# A money token like "$1,234.56" or "$ 45.00". Group 1 = numeric (commas kept).
_PRICE_RE = re.compile(r"\$\s*([0-9][0-9,]*\.\d{2})")
# "Name: value" attribute rows.
_ATTR_RE = re.compile(r"^\s*([A-Za-z][\w /&.+'\-]*?)\s*:\s*(.+?)\s*$")


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _soup(html: str) -> BeautifulSoup:
    """Parse with lxml; tolerate empty/None input."""
    return BeautifulSoup(html or "", "lxml")


def _text(node) -> str:
    """Collapsed, stripped text of a bs4 node (or '' for None)."""
    if node is None:
        return ""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _to_int(val) -> int | None:
    """Best-effort int; None on failure/empty."""
    if val is None:
        return None
    try:
        s = str(val).strip()
        if not s:
            return None
        # tolerate "2015.0" and stray non-digits like "2015 "
        m = re.search(r"-?\d+", s)
        return int(m.group(0)) if m else None
    except Exception:
        return None


def _money(text: str) -> float | None:
    """First $-price found in `text` as a float, else None."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def _absolutise(url: str | None) -> str | None:
    """Turn a protocol-relative or root-relative URL into an absolute one."""
    if not url:
        return None
    url = url.strip()
    if not url or url.startswith(("data:", "javascript:")):
        return None
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE.rstrip("/") + url
    return url


def _first_class(node, *keywords) -> object | None:
    """Find first descendant whose class list contains any keyword (substring)."""
    for kw in keywords:
        hit = node.find(class_=re.compile(re.escape(kw)))
        if hit is not None:
            return hit
    return None


# --------------------------------------------------------------------------- #
# _nck nonce
# --------------------------------------------------------------------------- #
def extract_nck(html: str) -> str | None:
    """
    Return the hidden `_nck` POST nonce (~364 chars) if present, else None.
    Tries a cheap regex first, then a bs4 fallback for oddly-ordered attrs.
    """
    if not html:
        return None
    # Fast path: name then value.
    m = re.search(
        r'<input[^>]*\bname=["\']_nck["\'][^>]*\bvalue=["\']([^"\']*)["\']',
        html, re.I,
    )
    if m and m.group(1):
        return _htmllib.unescape(m.group(1))
    # Reversed attribute order: value then name.
    m = re.search(
        r'<input[^>]*\bvalue=["\']([^"\']*)["\'][^>]*\bname=["\']_nck["\']',
        html, re.I,
    )
    if m and m.group(1):
        return _htmllib.unescape(m.group(1))
    # Last-resort bs4 lookup.
    try:
        node = _soup(html).find("input", attrs={"name": "_nck"})
        if node is not None:
            val = node.get("value")
            return _htmllib.unescape(val) if val else None
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------- #
# navigation tree
# --------------------------------------------------------------------------- #
def _nav_container(inp):
    """Walk up from an input#jsn[..] to its <div class=ranavnode id=nav[..]>."""
    for anc in inp.parents:
        try:
            cls = " ".join(anc.get("class", []) or [])
            aid = anc.get("id", "") or ""
        except Exception:
            continue
        if "ranavnode" in cls or aid.startswith("nav["):
            return anc
    return inp.parent


def _nav_href(inp, jsn: dict) -> str | None:
    """
    Resolve a node's href. Priority:
      1. a sibling element flagged navhref (id^=navhref or class~=navhref),
      2. any <a href> inside the ranavnode container,
      3. jsn['href'].
    """
    cont = _nav_container(inp)
    if cont is not None:
        nh = cont.find(id=re.compile(r"^navhref")) or cont.find(
            class_=re.compile("navhref")
        )
        if nh is not None:
            href = nh.get("href") or nh.get("value")
            if href:
                return _htmllib.unescape(href)
        a = cont.find("a", href=True)
        if a is not None and a.get("href"):
            return _htmllib.unescape(a["href"])
    href = jsn.get("href")
    return _htmllib.unescape(href) if href else None


def _nav_label(inp) -> str | None:
    """The node's human display name from its nav anchor text (e.g. 'Brake Pad',
    'Filter', 'Transmission-Automatic'). This is the ONLY place the part-type name
    lives — a parttype's jsn carries just the numeric id + parent groupname."""
    cont = _nav_container(inp)
    if cont is not None:
        nh = (cont.find(id=re.compile(r"^navhref"))
              or cont.find(class_=re.compile("navlabellink"))
              or cont.find(class_=re.compile("navhref")))
        if nh is not None:
            txt = nh.get_text(" ", strip=True)
            if txt:
                return txt
    return None


def _markets(jsn: dict) -> list[str]:
    """Extract market country codes from jsn.jsdata.markets[].c (or .C)."""
    out: list[str] = []
    jsdata = jsn.get("jsdata")
    markets = None
    if isinstance(jsdata, dict):
        markets = jsdata.get("markets")
    elif isinstance(jsdata, list):
        markets = jsdata  # some payloads inline the list
    if isinstance(markets, list):
        for m in markets:
            if isinstance(m, dict):
                c = m.get("c") or m.get("C")
                if c:
                    out.append(str(c))
            elif isinstance(m, str):
                out.append(m)
    return out


def parse_nav(html: str) -> list[dict]:
    """
    Parse a catalog navigation fragment into TreeNode dicts (CONTRACT §2).

    Finds every <input id="jsn[GIP]" value="{...JSON...}">, json.loads the
    (HTML-unescaped) value, and maps it. A malformed node is skipped, never
    fatal. The _nck nonce, when present in the same HTML, is available via
    extract_nck() (kept separate so this function's return stays a clean
    list[TreeNode] as the contract requires).
    """
    soup = _soup(html)
    nodes: list[dict] = []

    # id="jsn[GIP]" — match the literal bracket form.
    for inp in soup.find_all("input", id=re.compile(r"^jsn\[")):
        try:
            raw = inp.get("value")
            if not raw:
                continue
            # bs4 already decodes entities in attribute values, but decode again
            # defensively (no-op if already clean) so double-escaped payloads
            # still json.loads cleanly.
            try:
                jsn = json.loads(raw)
            except Exception:
                jsn = json.loads(_htmllib.unescape(raw))
            if not isinstance(jsn, dict):
                continue

            # gip: prefer the id attribute's bracket value, fall back to groupindex.
            gip = None
            mid = re.match(r"^jsn\[(.+?)\]$", inp.get("id", ""))
            if mid:
                gip = mid.group(1)
            if not gip:
                gip = jsn.get("groupindex")
            gip = str(gip) if gip is not None else None

            carcode = jsn.get("carcode")
            carcode = str(carcode) if carcode not in (None, "", 0, "0") else None

            node = {
                "gip": gip,
                "nodetype": jsn.get("nodetype"),
                "make": jsn.get("make") or None,
                "year": _to_int(jsn.get("year")),
                "model": jsn.get("model") or None,
                "carcode": carcode,
                "engine": jsn.get("engine") or None,
                "href": _nav_href(inp, jsn),
                "label": _nav_label(inp),
                "jsn": jsn,
                "markets": _markets(jsn),
            }
            nodes.append(node)
        except Exception:
            # One bad node must never sink the whole parse.
            continue

    return nodes


# --------------------------------------------------------------------------- #
# listings (leaf part rows)
# --------------------------------------------------------------------------- #
def _listing_container(el):
    """
    Given an anchor element inside a part row (e.g. the part-number span),
    climb to the smallest sensible per-part container so field extraction is
    scoped to ONE part.
    """
    for anc in el.parents:
        try:
            cls = " ".join(anc.get("class", []) or [])
            aid = anc.get("id", "") or ""
        except Exception:
            continue
        if any(
            k in cls
            for k in (
                "listing-container",
                "listing-inner",
                "listinginner",
                "listing-border",
                "listing-row",
                "listing-final",
            )
        ) and "listing-final-manufacturer" not in cls and "listing-final-partnumber" not in cls:
            return anc
        if aid.startswith("listingcontainer"):
            return anc
    # Fallback: nearest structural row.
    for anc in el.parents:
        if getattr(anc, "name", None) in ("tbody", "tr"):
            return anc
    return el.parent or el


# RockAuto UI chrome that shows up as <img> but is NOT a product photo:
# market flags, the closeout truck, wishlist Heart, help icons, mobile chrome,
# spacers. Real part thumbnails live under /info/ , /thumbs/ , or img.rockauto.com.
_JUNK_IMG_RE = re.compile(
    r"/catalog/images/|/images/mobile/|flag_|heart\.|truck\.|questionmark|"
    r"1pxtransparent|spacer|blank|/icons?/|help",
    re.IGNORECASE,
)


def _extract_product_images(soup, idx: str) -> list[str]:
    """RockAuto puts each part's photo in a SEPARATE structure keyed by the part's
    row index — `#inlineimg_container[N]` / `#listing_image_table[N]` — not inside
    the part's text cell. Real photos are `/info/<n>/..._ra_m.jpg`. Pull those."""
    out: list[str] = []
    seen: set[str] = set()
    for cid in (f"inlineimg_container[{idx}]", f"listing_image_table[{idx}]"):
        cont = soup.find(id=cid)
        if not cont:
            continue
        for img in cont.find_all("img"):
            for attr in ("data-src", "data-original", "data-lazy", "src"):
                u = _absolutise(img.get(attr))
                if u and "/info/" in u.lower() and u not in seen:
                    seen.add(u)
                    out.append(u)
                    break
    return out


def _extract_images(cont) -> list[str]:
    """Product images in a container: data-src preferred over src, deduped.
    Filters out RockAuto UI chrome (flags, truck, Heart, help icons, spacers)."""
    out: list[str] = []
    seen: set[str] = set()
    for img in cont.find_all("img"):
        for attr in ("data-src", "data-original", "data-lazy", "src"):
            v = img.get(attr)
            u = _absolutise(v)
            if u and u not in seen:
                low = u.lower()
                if low.endswith(".gif") or _JUNK_IMG_RE.search(low):
                    continue
                seen.add(u)
                out.append(u)
                break  # one URL per <img>
    return out


def _extract_price_and_core(cont) -> tuple[float | None, float | None]:
    """
    Price + core charge. Core is identified by a class/label containing 'core';
    the main price comes from .listing-price, else the first non-core $-token.
    """
    core = None
    core_el = _first_class(cont, "listing-core", "core-charge", "corecharge")
    if core_el is None:
        # Text-labelled core ("Core Charge: $12.00").
        for node in cont.find_all(string=re.compile(r"[Cc]ore")):
            m = _PRICE_RE.search(str(node.parent.get_text(" ", strip=True)))
            if m:
                core = float(m.group(1).replace(",", ""))
                break
    else:
        core = _money(_text(core_el))

    price = None
    price_el = _first_class(cont, "listing-price", "listing-final-price")
    if price_el is not None:
        price = _money(_text(price_el))
    if price is None:
        # First $-token in the container that isn't the core amount.
        for m in _PRICE_RE.finditer(cont.get_text(" ", strip=True)):
            val = float(m.group(1).replace(",", ""))
            if core is None or val != core:
                price = val
                break
    return price, core


def _extract_price_by_index(soup, idx: str) -> tuple[float | None, float | None]:
    """RockAuto puts each part's price/core in cells keyed by the part row index,
    OUTSIDE the part's text container: <span id="dprice[N][td]">$18.27</span> and
    a core cell at listingtd[N][core]. Pull them by index."""
    price = core = None
    pe = soup.find(id=f"dprice[{idx}][td]") or soup.find(id=f"listingtd[{idx}][price]")
    if pe is not None:
        price = _money(pe.get_text(" ", strip=True))
    ce = soup.find(id=f"dprice[{idx}][core]") or soup.find(id=f"listingtd[{idx}][core]")
    if ce is not None:
        core = _money(ce.get_text(" ", strip=True))
    return price, core


def _extract_attributes_and_desc(cont, name_el) -> tuple[list[dict], str | None]:
    """
    Walk .listing-text-row rows. Rows shaped 'Name: value' become attributes;
    the rest are joined into a free-text description. The name row is excluded.
    """
    attrs: list[dict] = []
    desc_bits: list[str] = []
    rows = cont.find_all(class_=re.compile("listing-text-row"))
    # Also consider dedicated attribute/spec rows if present.
    rows += cont.find_all(class_=re.compile("listing-attr|listing-spec|spec-row"))
    seen_txt: set[str] = set()
    for row in rows:
        if name_el is not None and row is name_el:
            continue
        txt = _text(row)
        if not txt or txt in seen_txt:
            continue
        seen_txt.add(txt)
        m = _ATTR_RE.match(txt)
        if m:
            attrs.append({"name": m.group(1).strip(), "value": m.group(2).strip()})
        else:
            desc_bits.append(txt)
    description = "; ".join(desc_bits) if desc_bits else None
    return attrs, description


def _extract_warranty(cont) -> str | None:
    """Warranty text — dedicated class, else a row/text mentioning 'warranty'."""
    w = _first_class(cont, "listing-warranty", "warranty")
    if w is not None:
        t = _text(w)
        if t:
            return t
    node = cont.find(string=re.compile(r"[Ww]arrant"))
    if node is not None:
        return _text(node.parent)
    return None


def _extract_interchange(cont) -> list[dict]:
    """
    Interchange / alternate part numbers -> [{brand, number, type:'interchange'}].
    Looks for containers/classes hinting 'interchange' or 'alternate'/'more info'.
    """
    out: list[dict] = []
    holders = cont.find_all(class_=re.compile("interchange|alternate|xref|x-ref"))
    for h in holders:
        # Structured rows: manufacturer + number spans.
        brand_el = h.find(class_=re.compile("manufacturer|brand"))
        num_el = h.find(class_=re.compile("partnumber|part-number|number"))
        if brand_el is not None or num_el is not None:
            brand = _text(brand_el) or None
            number = _text(num_el) or None
            if number:
                out.append({"brand": brand, "number": number, "type": "interchange"})
            continue
        # Fallback: "Brand PARTNO" free text per line.
        txt = _text(h)
        m = re.match(r"^\s*([A-Za-z][\w .&/-]*?)\s+([A-Za-z0-9][\w./\-]{2,})\s*$", txt)
        if m:
            out.append(
                {"brand": m.group(1).strip(), "number": m.group(2).strip(),
                 "type": "interchange"}
            )
    return out


def _extract_docs(cont) -> list[dict]:
    """
    Info / PDF links -> [{type, label, url}]. PDFs get type='pdf'; other
    info/spec/instruction links get type='info'.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for a in cont.find_all("a", href=True):
        href = _htmllib.unescape(a["href"])
        label = _text(a) or (a.get("title") or "").strip()
        low_href = href.lower()
        low_label = label.lower()
        is_pdf = low_href.endswith(".pdf") or ".pdf?" in low_href
        is_info = any(
            k in low_href or k in low_label
            for k in ("moreinfo", "more info", "info", "install", "instruction",
                      "spec", "manual", "datasheet", "warranty")
        )
        if not (is_pdf or is_info):
            continue
        url = _absolutise(href)
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(
            {"type": "pdf" if is_pdf else "info",
             "label": label or ("PDF" if is_pdf else "Info"),
             "url": url}
        )
    return out


def _extract_weight(cont) -> float | None:
    """Shipping weight if surfaced as 'Weight: 3.5 lbs' style text."""
    node = cont.find(string=re.compile(r"[Ww]eight"))
    if node is not None:
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(node.parent.get_text(" ", strip=True)))
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return None
    return None


def _extract_fitment_note(cont) -> str | None:
    """A per-part fitment caveat ('Fits ...'/'Note: ...') if present."""
    fn = _first_class(cont, "listing-fitment", "fitment-note", "fitnote")
    if fn is not None:
        t = _text(fn)
        if t:
            return t
    node = cont.find(string=re.compile(r"^\s*(Note|Fits|Fitment)\b", re.I))
    if node is not None:
        return _text(node.parent)
    return None


def _base_listing(ctx: dict) -> dict:
    """The ctx-derived, part-independent half of a Listing (CONTRACT §2)."""
    return {
        "source": "rockauto",
        "source_url": ctx.get("source_url") or ctx.get("href"),
        "make_name": ctx.get("make_name") or ctx.get("make"),
        "model_name": ctx.get("model_name") or ctx.get("model"),
        "year": _to_int(ctx.get("year")),
        "engine_name": ctx.get("engine_name") or ctx.get("engine"),
        "liters": ctx.get("liters"),
        "cylinders": ctx.get("cylinders"),
        "fuel_type": ctx.get("fuel_type"),
        "aspiration": ctx.get("aspiration"),
        "trim": ctx.get("trim"),
        "category_path": ctx.get("category_path") or "",
        "warehouse_code": ctx.get("warehouse_code"),
        "quantity": ctx.get("quantity"),
    }


def parse_listings(html: str, ctx: dict) -> list[dict]:
    """
    Parse a leaf catalog page's part rows into Listing dicts (CONTRACT §2).

    `ctx` supplies the fitment context (make/model/year/engine/carcode/
    category_path/source_url) which is merged into every row. Each part row is
    extracted defensively and independently — a malformed row is skipped, never
    fatal.
    """
    ctx = ctx or {}
    soup = _soup(html)
    base = _base_listing(ctx)
    listings: list[dict] = []

    # Anchor on the part-number element (one per part); fall back to
    # manufacturer elements if RockAuto renamed things.
    anchors = soup.find_all(class_=re.compile("listing-final-partnumber"))
    if not anchors:
        anchors = soup.find_all(class_=re.compile("listing-final-manufacturer"))
    if not anchors:
        # Last-ditch: whole listing containers.
        anchors = soup.find_all(class_=re.compile("listing-container|listing-inner"))

    seen_containers: list[int] = []
    for anchor in anchors:
        try:
            cont = _listing_container(anchor)
            # De-dup: two anchors may resolve to the same container.
            if id(cont) in seen_containers:
                continue
            seen_containers.append(id(cont))

            # Brand + part number.
            brand_el = _first_class(cont, "listing-final-manufacturer")
            pn_el = _first_class(cont, "listing-final-partnumber")
            brand_name = _text(brand_el) or None
            part_number = _text(pn_el) or None

            # Name (description link) + long description / attributes.
            name_el = _first_class(cont, "span-link-out-desc")
            name = _text(name_el) or None
            attributes, description = _extract_attributes_and_desc(cont, name_el)
            if not name:
                # Fall back to part number for a human-facing name.
                name = part_number or brand_name or "Part"

            # RockAuto lays out each part as a row keyed by an index (e.g.
            # vew_partnumber[8]); its price, core charge and photo sit in SEPARATE
            # cells under that same index, NOT inside the part's text container.
            # Resolve the index once and pull those index-keyed fields.
            idx = None
            m_idx = re.search(r"\[(\d+)\]", (pn_el.get("id") if pn_el else "") or "")
            if not m_idx:
                lc = anchor.find_parent(id=re.compile(r"listingcontainer\[\d+\]"))
                if lc:
                    m_idx = re.search(r"\[(\d+)\]", lc.get("id", "") or "")
            if m_idx:
                idx = m_idx.group(1)

            # Price + core: index-keyed cells first, container fallback second.
            price = core_charge = None
            if idx:
                price, core_charge = _extract_price_by_index(soup, idx)
            if price is None:
                p2, c2 = _extract_price_and_core(cont)
                price = p2
                if core_charge is None:
                    core_charge = c2

            # Product photo (index-keyed structure), else container-scoped images.
            image_urls = _extract_product_images(soup, idx) if idx else []
            if not image_urls:
                image_urls = _extract_images(cont)
            warranty = _extract_warranty(cont)
            interchange = _extract_interchange(cont)
            doc_urls = _extract_docs(cont)
            weight = _extract_weight(cont)
            fitment_note = _extract_fitment_note(cont)

            # A row with neither brand nor part number is noise — skip it.
            if not brand_name and not part_number:
                continue

            listing = dict(base)
            listing.update(
                {
                    "brand_name": brand_name,
                    "part_number": part_number,
                    "name": name,
                    "description": description,
                    "price": price,
                    "core_charge": core_charge,
                    "weight": weight,
                    "image_urls": image_urls,
                    "attributes": attributes,
                    "fitment_note": fitment_note,
                    "warranty": warranty,
                    "interchange": interchange or None,
                    "doc_urls": doc_urls or None,
                }
            )
            listings.append(listing)
        except Exception:
            # Never let one broken row abort the page.
            continue

    return listings


# --------------------------------------------------------------------------- #
# CAPTCHA / soft-ban detection
# --------------------------------------------------------------------------- #
def is_captcha(html: str, final_url: str) -> bool:
    """
    True when the response is a CAPTCHA / soft-ban page:
      * final_url contains '/captcha/', OR
      * body has an <img class="captchaimage"> or references 'securimage'.
    """
    if final_url and CAPTCHA_PATH in final_url:
        return True
    if not html:
        return False
    low = html.lower()
    # Cheap substring checks cover class="captchaimage" and securimage.php refs.
    if "securimage" in low or "captchaimage" in low:
        return True
    return False


# --------------------------------------------------------------------------- #
# OFFLINE self-test  —  no network, inline fixtures only
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # ---- Fixture 1: navigation fragment (2 jsn nodes, one with a carcode) ----
    NAV_HTML = """
    <html><body>
      <form>
        <input type="hidden" name="_nck" value="abc123DEF456nonce&amp;tok">
      </form>
      <div class="ranavnode" id="nav[2015]">
        <input id="jsn[2015]" value='{"groupindex":"2015","nodetype":"year",
          "make":"Honda","year":"2015","model":null,"carcode":null,"engine":null,
          "jsdata":{"markets":[{"c":"US"},{"c":"CA"}]},"href":"/en/catalog/honda,2015"}'>
        <a class="navlabellink" href="/en/catalog/honda,2015">2015</a>
      </div>
      <div class="ranavnode" id="nav[3309958]">
        <input id="jsn[3309958]" value='{"groupindex":"3309958","nodetype":"carcode",
          "make":"Honda","year":"2015","model":"Accord","carcode":3309958,
          "engine":"2.4L L4","jsdata":{"markets":[{"c":"US"}]},
          "href":"/en/catalog/honda,2015,accord,2.4l+l4,3309958"}'>
      </div>
      <div class="ranavnode" id="nav[bad]">
        <input id="jsn[bad]" value='{this is not valid json}'>
      </div>
    </body></html>
    """

    nodes = parse_nav(NAV_HTML)
    check(len(nodes) == 2, f"parse_nav: expected 2 good nodes, got {len(nodes)}")

    by_type = {n["nodetype"]: n for n in nodes}
    year_node = by_type.get("year")
    car_node = by_type.get("carcode")

    check(year_node is not None, "parse_nav: missing year node")
    check(car_node is not None, "parse_nav: missing carcode node")

    if year_node:
        check(year_node["gip"] == "2015", f"year gip wrong: {year_node['gip']}")
        check(year_node["make"] == "Honda", "year make wrong")
        check(year_node["year"] == 2015 and isinstance(year_node["year"], int),
              f"year->int failed: {year_node['year']!r}")
        check(year_node["carcode"] is None, "year carcode should be None")
        check(year_node["markets"] == ["US", "CA"],
              f"year markets wrong: {year_node['markets']}")
        check(year_node["href"] == "/en/catalog/honda,2015",
              f"year href wrong: {year_node['href']}")
        check(isinstance(year_node["jsn"], dict), "year jsn not a dict")

    if car_node:
        check(car_node["carcode"] == "3309958",
              f"carcode should be str '3309958', got {car_node['carcode']!r}")
        check(car_node["engine"] == "2.4L L4", "carcode engine wrong")
        check(car_node["model"] == "Accord", "carcode model wrong")
        check(car_node["markets"] == ["US"], "carcode markets wrong")

    # Verify the TreeNode has EXACTLY the contract keys.
    EXPECTED_NODE_KEYS = {
        "gip", "nodetype", "make", "year", "model", "carcode",
        "engine", "href", "label", "jsn", "markets",
    }
    if nodes:
        check(set(nodes[0].keys()) == EXPECTED_NODE_KEYS,
              f"TreeNode key mismatch: {set(nodes[0].keys()) ^ EXPECTED_NODE_KEYS}")

    # ---- _nck ----
    nck = extract_nck(NAV_HTML)
    check(nck == "abc123DEF456nonce&tok", f"extract_nck wrong: {nck!r}")
    check(extract_nck("<html>no nonce here</html>") is None,
          "extract_nck should be None when absent")

    # ---- Fixture 2: listing block (2 fake parts, prices + images) ----
    LISTING_HTML = """
    <html><body>
    <table>
      <tbody class="listing-container-border" id="listingcontainer[1]">
        <tr><td>
          <span class="listing-final-manufacturer">Bosch</span>
          <span class="listing-final-partnumber">BC905</span>
          <a class="span-link-out-desc" href="/x">QuietCast Ceramic Brake Pad Set</a>
          <div class="listing-text-row">Position: Front</div>
          <div class="listing-text-row">Includes hardware and shims</div>
          <span class="listing-price">$45.79</span>
          <span class="listing-core-price">Core Charge: $12.00</span>
          <div class="listing-warranty">Warranty: 2 Years / 24,000 Miles</div>
          <img class="listing-inline-image" data-src="/thumbs/bc905.jpg" src="/spacer.gif">
          <div class="listing-interchange">
            <span class="manufacturer">Wagner</span>
            <span class="partnumber">ZD905</span>
          </div>
          <a href="/info/bc905_install.pdf">Installation Instructions</a>
        </td></tr>
      </tbody>
      <tbody class="listing-container-border" id="listingcontainer[2]">
        <tr><td>
          <span class="listing-final-manufacturer">Denso</span>
          <span class="listing-final-partnumber">234-4209</span>
          <a class="span-link-out-desc" href="/y">Oxygen Sensor</a>
          <div class="listing-text-row">Location: Upstream</div>
          <span class="listing-price">$62.00</span>
          <img data-src="//img.rockauto.com/denso2344209.jpg">
        </td></tr>
      </tbody>
      <tbody class="listing-container-border">
        <tr><td>
          <!-- malformed row: no brand, no part number -> must be skipped -->
          <div class="listing-text-row">Just some noise</div>
        </td></tr>
      </tbody>
    </table>
    </body></html>
    """

    CTX = {
        "make": "Honda", "model": "Accord", "year": "2015",
        "engine": "2.4L L4", "carcode": "3309958",
        "category_path": "Brake & Wheel Hub>Brake Pad",
        "source_url": "https://www.rockauto.com/en/catalog/honda,2015,accord,2.4l+l4,3309958",
    }

    parts = parse_listings(LISTING_HTML, CTX)
    check(len(parts) == 2, f"parse_listings: expected 2 parts, got {len(parts)}")

    EXPECTED_LISTING_KEYS = {
        "source", "source_url", "make_name", "model_name", "year",
        "engine_name", "liters", "cylinders", "fuel_type", "aspiration", "trim",
        "category_path", "brand_name", "part_number", "name", "description",
        "price", "core_charge", "weight", "image_urls", "attributes",
        "warehouse_code", "quantity", "fitment_note", "warranty",
        "interchange", "doc_urls",
    }

    if parts:
        p0 = parts[0]
        check(set(p0.keys()) == EXPECTED_LISTING_KEYS,
              f"Listing key mismatch: {set(p0.keys()) ^ EXPECTED_LISTING_KEYS}")
        check(p0["source"] == "rockauto", "source wrong")
        check(p0["brand_name"] == "Bosch", f"brand wrong: {p0['brand_name']}")
        check(p0["part_number"] == "BC905", f"partno wrong: {p0['part_number']}")
        check(p0["name"] == "QuietCast Ceramic Brake Pad Set",
              f"name wrong: {p0['name']}")
        check(p0["price"] == 45.79, f"price wrong: {p0['price']}")
        check(p0["core_charge"] == 12.00, f"core wrong: {p0['core_charge']}")
        check(p0["year"] == 2015 and isinstance(p0["year"], int),
              "ctx year->int failed")
        check(p0["make_name"] == "Honda", "ctx make merge failed")
        check(p0["category_path"] == "Brake & Wheel Hub>Brake Pad",
              "category_path merge failed")
        check(p0["source_url"] == CTX["source_url"], "source_url merge failed")
        check("https://www.rockauto.com/thumbs/bc905.jpg" in p0["image_urls"],
              f"image not absolutised: {p0['image_urls']}")
        check({"name": "Position", "value": "Front"} in p0["attributes"],
              f"attribute parse failed: {p0['attributes']}")
        check(p0["warranty"] and "2 Years" in p0["warranty"],
              f"warranty wrong: {p0['warranty']}")
        check(p0["interchange"] and p0["interchange"][0]["brand"] == "Wagner"
              and p0["interchange"][0]["number"] == "ZD905"
              and p0["interchange"][0]["type"] == "interchange",
              f"interchange wrong: {p0['interchange']}")
        check(p0["doc_urls"] and any(d["type"] == "pdf" for d in p0["doc_urls"]),
              f"doc_urls wrong: {p0['doc_urls']}")

    if len(parts) > 1:
        p1 = parts[1]
        check(p1["brand_name"] == "Denso", "part2 brand wrong")
        check(p1["part_number"] == "234-4209", "part2 partno wrong")
        check(p1["price"] == 62.00, f"part2 price wrong: {p1['price']}")
        check(p1["image_urls"] == ["https://img.rockauto.com/denso2344209.jpg"],
              f"part2 protocol-relative image failed: {p1['image_urls']}")
        check(p1["core_charge"] is None, "part2 core should be None")
        check(p1["interchange"] is None, "part2 interchange should be None")

    # ---- CAPTCHA detection ----
    check(is_captcha("", "https://www.rockauto.com/captcha/?redirecturl=x") is True,
          "is_captcha: /captcha/ url not detected")
    check(is_captcha('<img class="captchaimage" src="securimage_show.php">', "x") is True,
          "is_captcha: captchaimage body not detected")
    check(is_captcha("<html>normal page</html>",
                     "https://www.rockauto.com/en/catalog/honda") is False,
          "is_captcha: false positive on normal page")

    # ---- verdict ----
    if failures:
        print("FAIL")
        for f in failures:
            print("  -", f)
        raise SystemExit(1)
    else:
        print("PASS")
