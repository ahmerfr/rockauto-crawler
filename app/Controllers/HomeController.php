<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Core\Controller;

class HomeController extends Controller
{
    public function index(): void
    {
        // The homepage is the full "Supreme Autos" design — a standalone page
        // with its own head/header/footer, so render it directly (no layout).
        echo $this->capture('home', [
            'base'  => rtrim($this->url(''), '/'),
            'cartN' => \App\Core\Cart::headerCount(),
        ]);
    }

    public function notFound(): void
    {
        $this->notFoundResponse();
    }
}
