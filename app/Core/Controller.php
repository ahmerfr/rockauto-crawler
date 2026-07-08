<?php
declare(strict_types=1);

namespace App\Core;

use PDO;

abstract class Controller
{
    protected function db(): PDO
    {
        return Database::connection();
    }

    /** URL helper: prefix a path with the app base path (/RockAuto). */
    public function url(string $path = ''): string
    {
        $cfg = (require BASE_DIR . '/config/config.php')['app'];
        $base = rtrim($cfg['base_path'], '/');
        return $base . '/' . ltrim($path, '/');
    }

    /** Absolute URL (scheme://host + base path + path) — needed for Stripe redirects. */
    public function absoluteUrl(string $path = ''): string
    {
        $https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') || ($_SERVER['SERVER_PORT'] ?? '') == 443;
        $scheme = $https ? 'https' : 'http';
        $host = $_SERVER['HTTP_HOST'] ?? 'localhost';
        return $scheme . '://' . $host . $this->url($path);
    }

    /** Render a view inside the main layout and echo it. */
    protected function render(string $view, array $data = [], ?string $title = null): void
    {
        $data['title'] = $title ?? 'Supreme Parts';
        $data['_controller'] = $this;
        $content = $this->capture($view, $data);
        $data['content'] = $content;
        echo $this->capture('layout', $data);
    }

    /** Render a view with no layout (partials / raw pages). */
    protected function capture(string $view, array $data = []): string
    {
        $data['_controller'] = $data['_controller'] ?? $this;
        extract($data, EXTR_SKIP);
        ob_start();
        require BASE_DIR . '/app/Views/' . $view . '.php';
        return (string) ob_get_clean();
    }

    protected function json(mixed $payload, int $status = 200): void
    {
        http_response_code($status);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode($payload, JSON_UNESCAPED_SLASHES);
    }

    protected function redirect(string $path): void
    {
        header('Location: ' . $this->url($path));
        exit;
    }

    protected function notFoundResponse(): void
    {
        http_response_code(404);
        $this->render('not_found', [], 'Not Found — Supreme Parts');
    }
}
