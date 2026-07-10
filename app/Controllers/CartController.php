<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Core\Controller;
use App\Core\Cart;

class CartController extends Controller
{
    public function add(): void
    {
        $cart = new Cart();
        $sku = (string) ($_POST['sku'] ?? '');
        $qty = max(1, (int) ($_POST['qty'] ?? 1));
        $variantId = max(0, (int) ($_POST['variant_id'] ?? 0));   // 0 = default price
        if ($sku !== '') { $cart->addBySku($sku, $qty, $variantId); }
        // Return to where they were, or the cart.
        $back = $_POST['back'] ?? ($_SERVER['HTTP_REFERER'] ?? '');
        if ($back && str_contains($back, ($_SERVER['HTTP_HOST'] ?? ''))) {
            header('Location: ' . $back);
        } else {
            $this->redirect('/cart');
        }
        exit;
    }

    public function view(): void
    {
        $cart = new Cart();
        $this->render('cart', [
            'items'  => $cart->items(),
            'totals' => $cart->totals(),
        ], 'Cart — Supreme Parts');
    }

    public function update(): void
    {
        $cart = new Cart();
        $cart->setQty((int) ($_POST['part_id'] ?? 0), (int) ($_POST['qty'] ?? 0),
                      max(0, (int) ($_POST['variant_id'] ?? 0)));
        $this->redirect('/cart');
    }

    public function remove(): void
    {
        $cart = new Cart();
        $cart->remove((int) ($_POST['part_id'] ?? 0),
                      max(0, (int) ($_POST['variant_id'] ?? 0)));
        $this->redirect('/cart');
    }
}
