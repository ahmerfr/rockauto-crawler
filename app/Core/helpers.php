<?php
declare(strict_types=1);

// Global view helpers (loaded in bootstrap, available in all templates).

if (!function_exists('e')) {
    /** HTML-escape for safe output in templates. */
    function e(?string $s): string
    {
        return htmlspecialchars($s ?? '', ENT_QUOTES, 'UTF-8');
    }
}

if (!function_exists('img_url')) {
    /** Serve a stored part photo from the CDN when SP_CDN_BASE is configured;
     *  otherwise return the path unchanged. Only rewrites paths under the local
     *  parts prefix — absolute URLs and other assets pass through untouched. */
    function img_url(?string $path): string
    {
        $path = $path ?? '';
        $base = defined('SP_CDN_BASE') ? SP_CDN_BASE : '';
        if ($base === '' || $path === '') return $path;
        $prefix = '/RockAuto/assets/parts/';
        $pos = strpos($path, $prefix);
        if ($pos === false) return $path;
        return rtrim($base, '/') . '/' . ltrim(substr($path, $pos + strlen($prefix)), '/');
    }
}

if (!function_exists('money')) {
    /** Format a decimal as USD. NULL means RockAuto lists no price for the part
     *  (out of stock) — render that, never a fake "$0.00". */
    function money(int|float|string|null $n): string
    {
        if ($n === null) return 'Out of Stock';
        return '$' . number_format((float) $n, 2);
    }
}

if (!function_exists('setting')) {
    /** Read a row from the `settings` key/value table (cached for the request).
     *  Returns $default when the key is absent or the DB is unreachable. */
    function setting(string $key, ?string $default = null): ?string
    {
        static $cache = null;
        if ($cache === null) {
            $cache = [];
            try {
                $rows = \App\Core\Database::connection()
                    ->query("SELECT `key`, `value` FROM settings")->fetchAll();
                foreach ($rows as $r) { $cache[$r['key']] = $r['value']; }
            } catch (\Throwable $e) { $cache = []; }   // table missing / DB down -> defaults
        }
        return $cache[$key] ?? $default;
    }
}

if (!function_exists('markup_factor')) {
    /** Reseller multiplier: 1 + markup%/100. A 25 setting -> 1.25 (RockAuto cost +25%). */
    function markup_factor(): float
    {
        $pct = (float) (setting('reseller_markup_pct', '0') ?? '0');
        return 1.0 + max(0.0, $pct) / 100.0;   // never below cost
    }
}

if (!function_exists('sell_price')) {
    /** Customer price = RockAuto base cost * markup, rounded to the cent. NULL
     *  (out of stock) passes through so it still renders as "Out of Stock". */
    function sell_price(int|float|string|null $base): ?float
    {
        if ($base === null) return null;
        return round((float) $base * markup_factor(), 2);
    }
}

if (!function_exists('price_tag')) {
    /** Formatted customer-facing price: money(sell_price(base)). Use in catalog
     *  views where the raw RockAuto cost comes straight from the DB. */
    function price_tag(int|float|string|null $base): string
    {
        return money(sell_price($base));
    }
}
