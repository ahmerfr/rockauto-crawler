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

if (!function_exists('money')) {
    /** Format a decimal as USD. NULL means RockAuto lists no price for the part
     *  (out of stock) — render that, never a fake "$0.00". */
    function money(int|float|string|null $n): string
    {
        if ($n === null) return 'Out of Stock';
        return '$' . number_format((float) $n, 2);
    }
}
