<?php
declare(strict_types=1);

// Shared bootstrap: PSR-4-ish autoloader for App\ + returns config.
// Used by both index.php (web) and bin/*.php (CLI).

if (!defined('BASE_DIR')) {
    define('BASE_DIR', __DIR__);
}

spl_autoload_register(function (string $class): void {
    $prefix = 'App\\';
    if (str_starts_with($class, $prefix)) {
        $relative = substr($class, strlen($prefix));
        $path = BASE_DIR . '/app/' . str_replace('\\', '/', $relative) . '.php';
        if (is_file($path)) {
            require $path;
        }
    }
});

require BASE_DIR . '/app/Core/helpers.php';

return require BASE_DIR . '/config/config.php';
