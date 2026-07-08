<?php
declare(strict_types=1);

namespace App\Core;

class Router
{
    /** @var array<string, array<int, array{regex:string, params:string[], handler:string}>> */
    private array $routes = ['GET' => [], 'POST' => []];

    public function __construct(private string $basePath = '')
    {
        $this->basePath = rtrim($basePath, '/');
    }

    public function get(string $path, string $handler): void
    {
        $this->add('GET', $path, $handler);
    }

    public function post(string $path, string $handler): void
    {
        $this->add('POST', $path, $handler);
    }

    /**
     * Register a route. Supports {param} segments, e.g. /vehicle/{slug}/c/{category}.
     * Params are passed to the controller action in declaration order.
     */
    private function add(string $method, string $path, string $handler): void
    {
        $path = $this->normalize($path);
        $params = [];
        $regex = preg_replace_callback('#\{([a-zA-Z_][a-zA-Z0-9_]*)\}#', function ($m) use (&$params) {
            $params[] = $m[1];
            return '([^/]+)';
        }, $path);
        $this->routes[$method][] = [
            'regex'   => '#^' . $regex . '$#',
            'params'  => $params,
            'handler' => $handler,
        ];
    }

    private function normalize(string $path): string
    {
        $path = '/' . trim($path, '/');
        return $path === '/' ? '/' : rtrim($path, '/');
    }

    public function dispatch(string $method, string $uri): void
    {
        $path = parse_url($uri, PHP_URL_PATH) ?: '/';

        // Strip the app's base path (/RockAuto) so routes are declared clean.
        if ($this->basePath !== '' && str_starts_with($path, $this->basePath)) {
            $path = substr($path, strlen($this->basePath));
        }
        $path = $this->normalize(rawurldecode($path));

        foreach ($this->routes[$method] ?? [] as $route) {
            if (preg_match($route['regex'], $path, $matches)) {
                array_shift($matches); // drop full match
                [$controller, $action] = explode('@', $route['handler']);
                $class = 'App\\Controllers\\' . $controller;
                (new $class())->{$action}(...$matches);
                return;
            }
        }

        http_response_code(404);
        (new \App\Controllers\HomeController())->notFound();
    }
}
