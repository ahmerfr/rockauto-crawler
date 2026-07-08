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
    /** Format a decimal as USD. */
    function money(int|float|string|null $n): string
    {
        return '$' . number_format((float) $n, 2);
    }
}
