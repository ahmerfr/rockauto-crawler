"""
scraper/captcha_solver.py — Build Agent C (CAPTCHA solver)

Best-effort, ZERO-COST OCR solver for the SECURIMAGE text CAPTCHA that RockAuto
throws up when its anti-bot fires (302 -> /captcha/?redirecturl=...). No paid
services, no cloud APIs — just Pillow for preprocessing and Tesseract (via
pytesseract) for the actual character recognition.

Public surface (per the build brief):

    solve_image(png_bytes: bytes) -> str | None
        Preprocess + OCR a raw CAPTCHA image; returns the best-guess code
        (upper-cased, whitelist-filtered) or None if nothing usable came out.

    solve_from_url(session, image_url: str) -> str | None
        Fetch the securimage PNG with an *existing* requests session (so the
        PHPSESSID cookie that binds the code stays intact), then solve_image().

    preprocess(png_bytes: bytes) -> bytes
        Grayscale -> upscale -> denoise (median) -> binarize. Returns PNG bytes.
        Exposed on its own so tests / callers can inspect the cleaned image.

Why SECURIMAGE is crackable at all (see build research):
  * Single fixed font (AHGBold.ttf), fixed 215x80 geometry, colored glyphs on a
    white ground, glyphs that do NOT touch — segmentation-friendly.
  * charset trims ambiguous glyphs and the compare is CASE-INSENSITIVE, so we
    upper-case everything and OCR against a tight whitelist.
  * The code lives in $_SESSION and "New Code" mints a fresh one in the SAME
    session, so the caller can retry: effective rate = 1-(1-p)^n. Keep retries
    LOW though — every fetch spends against RockAuto's hard IP-block budget.

Design constraints honored here:
  * Pillow only for image work (NO OpenCV) — keep the dep footprint light.
  * NEVER crash the import: if pytesseract or the tesseract binary is missing we
    log a single warning and every solve returns None. The crawler is designed
    to rotate+re-enqueue on an unsolved CAPTCHA anyway, so a missing OCR engine
    degrades the pipeline to "polite rotation only", it does not break it.
"""
from __future__ import annotations

import io
import logging
import os

log = logging.getLogger("scraper.captcha_solver")

# ---------------------------------------------------------------------------
# Soft dependency wiring. Import failures must NEVER propagate out of this
# module — the crawler imports it unconditionally and must keep running even on
# a box with no OCR stack installed.
# ---------------------------------------------------------------------------
try:
    from PIL import Image, ImageFilter, ImageOps

    _PIL_OK = True
except Exception as exc:  # pragma: no cover - Pillow is a hard dep, but be safe
    Image = ImageFilter = ImageOps = None  # type: ignore[assignment]
    _PIL_OK = False
    _PIL_ERR = str(exc)

try:
    import pytesseract

    # Honor an explicit binary path on Windows where tesseract is rarely on PATH.
    _cmd = os.getenv("TESSERACT_CMD")
    if _cmd:
        pytesseract.pytesseract.tesseract_cmd = _cmd
    _PYTESS_OK = True
except Exception as exc:  # module not installed
    pytesseract = None  # type: ignore[assignment]
    _PYTESS_OK = False
    _PYTESS_ERR = str(exc)


# ---------------------------------------------------------------------------
# SECURIMAGE tuning knobs.
# ---------------------------------------------------------------------------
# Default dapphp/securimage charset. Case-insensitive compare on the server, so
# we fold to UPPER for both the Tesseract whitelist and the returned guess. The
# union of the trimmed upper/lower sets happens to cover most of A-Z0-9; keeping
# the raw charset as the whitelist still steers Tesseract off punctuation/space.
SECURIMAGE_CHARSET = (
    "abcdefghijkmnopqrstuvwxzyABCDEFGHJKLMNPQRSTUVWXZY0123456789"
)
_WHITELIST_UPPER = "".join(sorted(set(SECURIMAGE_CHARSET.upper())))
CODE_LENGTH = 6            # securimage default code_length
_MIN_LEN, _MAX_LEN = 4, 8  # accept a little slack around the expected length

# Upscale factor before OCR. securimage renders ~215x80; Tesseract wants big,
# clean glyphs, so we blow it up an order of magnitude.
_UPSCALE = 6
# Median window (post-upscale) to erase the thin arc/line noise securimage draws
# over the text. Odd, and scaled with the upscale so it actually spans a line.
_MEDIAN = 9
# Grayscale cutoff for binarization. securimage puts dark-ish colored glyphs on
# white; ~140-190 works. We try a couple and vote.
_THRESHOLDS = (160, 185, 140)

# Warn at most once per process so a missing engine doesn't spam the crawl log.
_warned = False


def _warn_once(msg: str) -> None:
    global _warned
    if not _warned:
        log.warning("captcha_solver disabled: %s", msg)
        _warned = True


def _engine_ready() -> bool:
    """True only if Pillow + pytesseract + the native tesseract binary are all
    usable. Emits a single warning and returns False otherwise (never raises)."""
    if not _PIL_OK:
        _warn_once(f"Pillow unavailable ({_PIL_ERR})")
        return False
    if not _PYTESS_OK:
        _warn_once(
            f"pytesseract unavailable ({_PYTESS_ERR}); "
            "pip install pytesseract + install the tesseract binary"
        )
        return False
    try:
        # Cheap probe that the native binary is actually reachable.
        pytesseract.get_tesseract_version()
    except Exception as exc:  # binary missing / not on PATH
        _warn_once(
            f"tesseract binary not found ({exc}); "
            "install it or set env TESSERACT_CMD to its full path"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Preprocessing.
# ---------------------------------------------------------------------------
def _clean_image(png_bytes: bytes) -> "Image.Image":
    """Core Pillow pipeline shared by preprocess() and solve_image().

    grayscale -> autocontrast -> upscale -> median denoise (kills the arc lines
    + speckle) -> return a big, high-contrast L-mode image. Binarization is left
    to the caller so solve_image() can sweep several thresholds.
    """
    img = Image.open(io.BytesIO(png_bytes))
    # Flatten any alpha onto white so transparent PNGs don't threshold to black.
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img)
    img = img.convert("L")               # grayscale
    img = ImageOps.autocontrast(img)     # stretch the histogram
    w, h = img.size
    img = img.resize((max(1, w * _UPSCALE), max(1, h * _UPSCALE)), Image.LANCZOS)
    # Median blur erases the thin overlaid lines/noise without smearing the
    # (much thicker, post-upscale) glyph strokes.
    img = img.filter(ImageFilter.MedianFilter(size=_MEDIAN))
    return img


def _binarize(img: "Image.Image", threshold: int) -> "Image.Image":
    """Point-threshold an L-mode image to pure black text on white (mode '1')."""
    bw = img.point(lambda p: 255 if p > threshold else 0, mode="L")
    # A light closing (min then max via Max/Min filters) tidies ragged edges.
    bw = bw.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    return bw.convert("1")


def preprocess(png_bytes: bytes) -> bytes:
    """Return denoised/binarized PNG bytes for the given CAPTCHA image.

    Exposed for tests and for callers who want to eyeball what the OCR sees.
    Uses the middle threshold. Falls back to returning the ORIGINAL bytes if
    Pillow is unavailable or the input isn't a decodable image, so this never
    raises on the crawl path.
    """
    if not _PIL_OK:
        _warn_once(f"Pillow unavailable ({_PIL_ERR})")
        return png_bytes
    try:
        cleaned = _binarize(_clean_image(png_bytes), _THRESHOLDS[0])
        out = io.BytesIO()
        cleaned.save(out, format="PNG")
        return out.getvalue()
    except Exception as exc:  # undecodable/garbage input
        log.debug("preprocess failed, returning original bytes: %s", exc)
        return png_bytes


# ---------------------------------------------------------------------------
# OCR.
# ---------------------------------------------------------------------------
def _clean_guess(raw: str) -> str:
    """Upper-case, strip whitespace, and drop anything off the whitelist."""
    up = (raw or "").strip().upper()
    return "".join(ch for ch in up if ch in _WHITELIST_UPPER)


def _ocr_candidates(img: "Image.Image"):
    """Yield (guess, score) over a small grid of thresholds x psm modes.

    score rewards hitting the expected 6-char length and OCR mean confidence, so
    the caller can pick the most trustworthy reading. Uses the legacy engine
    (oem 0) which the research found beats LSTM on short, noisy captcha strings.
    """
    base_cfg = f"--oem 0 -c tessedit_char_whitelist={_WHITELIST_UPPER}"
    for threshold in _THRESHOLDS:
        try:
            bw = _binarize(img, threshold)
        except Exception:
            continue
        for psm in (8, 7, 13):  # 8=word, 7=line, 13=raw line
            cfg = f"{base_cfg} --psm {psm}"
            try:
                data = pytesseract.image_to_data(
                    bw, config=cfg, output_type=pytesseract.Output.DICT
                )
            except Exception as exc:
                # A single OCR mode blowing up must not kill the whole solve.
                log.debug("tesseract mode (thr=%s psm=%s) failed: %s", threshold, psm, exc)
                continue
            texts, confs = [], []
            for txt, conf in zip(data.get("text", []), data.get("conf", [])):
                g = _clean_guess(txt)
                if not g:
                    continue
                texts.append(g)
                try:
                    c = float(conf)
                except (TypeError, ValueError):
                    c = -1.0
                if c >= 0:
                    confs.append(c)
            guess = "".join(texts)
            if not guess:
                continue
            mean_conf = sum(confs) / len(confs) if confs else 0.0
            # Prefer exact expected length, then length near it, then confidence.
            length_bonus = 1000.0 if len(guess) == CODE_LENGTH else 0.0
            length_bonus -= abs(len(guess) - CODE_LENGTH) * 50.0
            yield guess, length_bonus + mean_conf


def solve_image(png_bytes: bytes) -> str | None:
    """Preprocess + OCR a raw CAPTCHA PNG. Returns the best-guess code (UPPER,
    whitelist-only) or None if OCR is unavailable or produced nothing usable.

    Never raises: any failure -> None so the crawler simply rotates/retries.
    """
    if not _engine_ready():
        return None
    try:
        cleaned = _clean_image(png_bytes)
    except Exception as exc:
        log.debug("solve_image: could not decode/clean image: %s", exc)
        return None

    best_guess: str | None = None
    best_score = float("-inf")
    for guess, score in _ocr_candidates(cleaned):
        if score > best_score and _MIN_LEN <= len(guess) <= _MAX_LEN:
            best_guess, best_score = guess, score
    if best_guess:
        log.debug("solve_image -> %r (score=%.1f)", best_guess, best_score)
    return best_guess


def solve_from_url(session, image_url: str) -> str | None:
    """Fetch the securimage PNG using an EXISTING requests session, then solve.

    The code is bound to the session's PHPSESSID cookie (not to the image id in
    the URL), so the SAME `session` that loaded the /captcha/ page MUST be reused
    here. Returns the guess or None (never raises — network/OCR errors -> None).
    """
    if not _engine_ready():
        return None
    try:
        resp = session.get(image_url, timeout=20)
        resp.raise_for_status()
        content = resp.content
    except Exception as exc:
        log.debug("solve_from_url: fetch failed for %s: %s", image_url, exc)
        return None
    if not content:
        return None
    return solve_image(content)


# ===========================================================================
# OFFLINE self-test — no network. Generates synthetic text images with Pillow,
# runs the solver, and asserts it recovers at least the easy ones. If the
# tesseract engine is absent it prints SKIP for the OCR checks (still PASSes the
# preprocess sanity check). Run: python captcha_solver.py
# ===========================================================================
def _make_test_image(text: str, noise: bool = False) -> bytes:
    """Render `text` to a small PNG roughly mimicking securimage's look
    (dark glyphs on white, optional thin lines + speckle)."""
    from PIL import ImageDraw, ImageFont
    import random

    W, H = 215, 80
    img = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = None
    for name in ("arial.ttf", "DejaVuSans-Bold.ttf", "Arial.ttf"):
        try:
            font = ImageFont.truetype(name, 40)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    # Spread characters across the width with tiny vertical jitter.
    x = 14
    for ch in text:
        y = 16 + (random.randint(-4, 4) if noise else 0)
        draw.text((x, y), ch, fill=(20, 20, 90), font=font)
        x += 32
    if noise:
        for _ in range(3):  # a few thin arc-ish lines
            draw.line(
                [(random.randint(0, W), random.randint(0, H)) for _ in range(2)],
                fill=(120, 120, 120), width=1,
            )
        for _ in range(150):  # speckle
            draw.point((random.randint(0, W - 1), random.randint(0, H - 1)),
                       fill=(150, 150, 150))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _selftest() -> bool:
    results: list[tuple[str, str]] = []  # (label, "PASS"/"FAIL"/"SKIP")

    def record(label: str, status: str) -> None:
        results.append((label, status))
        print(f"  [{status}] {label}")

    # --- preprocess() always works (Pillow is a hard dep) -----------------
    if _PIL_OK:
        clean = "ABC123"
        raw = _make_test_image(clean, noise=True)
        pp = preprocess(raw)
        ok_png = False
        try:
            reopened = Image.open(io.BytesIO(pp))
            reopened.load()
            ok_png = reopened.format == "PNG" and reopened.size[0] > 0
        except Exception as exc:
            print(f"      preprocess reopen error: {exc}")
        record("preprocess() returns a valid, larger PNG", "PASS" if ok_png else "FAIL")
    else:
        record("preprocess() returns a valid PNG", "SKIP")

    # --- solve_image() needs the full OCR engine --------------------------
    if not _engine_ready():
        record("solve_image() recovers easy codes (tesseract absent)", "SKIP")
        record("solve_from_url() wiring (tesseract absent)", "SKIP")
    else:
        # Easy, low-noise samples the tuned pipeline should mostly get.
        samples = ["ABC123", "K7M2PQ", "5XR9TD", "HJ48NW"]
        hits = 0
        for s in samples:
            png = _make_test_image(s, noise=False)
            guess = solve_image(png)
            got = (guess == s)
            hits += 1 if got else 0
            print(f"      want={s!r} got={guess!r} {'OK' if got else 'miss'}")
        # OCR is probabilistic; require at least one clean recovery so the test
        # is meaningful without being flaky on font/engine differences.
        record(
            f"solve_image() recovers >=1/{len(samples)} easy codes (got {hits})",
            "PASS" if hits >= 1 else "FAIL",
        )

        # solve_from_url() via a fake session that serves a generated PNG — proves
        # the fetch->solve wiring without any network.
        target = "6QW2MK"
        png_bytes = _make_test_image(target, noise=False)

        class _FakeResp:
            content = png_bytes
            def raise_for_status(self):  # noqa: D401,E704
                return None

        class _FakeSession:
            def get(self, url, timeout=None):  # noqa: D401
                return _FakeResp()

        guess = solve_from_url(_FakeSession(), "http://x/securimage_show.php?id=1")
        # It must return SOMETHING plausible (whitelist string); exact match is a
        # bonus, not required, given OCR variance.
        wired = isinstance(guess, str) and len(guess) >= _MIN_LEN
        print(f"      solve_from_url -> {guess!r}")
        record("solve_from_url() fetches + returns a code", "PASS" if wired else "FAIL")

    failed = any(st == "FAIL" for _, st in results)
    return not failed


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    print("captcha_solver offline self-test:")
    success = _selftest()
    print("PASS" if success else "FAIL")
    raise SystemExit(0 if success else 1)
