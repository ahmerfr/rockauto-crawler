<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Core\Controller;
use App\Core\Cart;
use App\Core\Stripe;

class CheckoutController extends Controller
{
    /** POST /checkout — create pending order, then Stripe Checkout (or mock). */
    public function start(): void
    {
        $cart = new Cart();
        if ($cart->isEmpty()) { $this->redirect('/cart'); }

        $items = $cart->items();
        $totals = $cart->totals();
        [$orderId, $orderNumber] = $this->createPendingOrder($items, $totals);

        $stripe = new Stripe();
        if (!$stripe->enabled()) {
            // MOCK mode: no keys configured — mark paid immediately (local demo only).
            $this->finalizeOrder($orderId, null, 'mock');
            $cart->clear();
            $this->redirect('/checkout/success?order=' . urlencode($orderNumber) . '&mock=1');
        }

        $cur = $stripe->currency();
        $lineItems = [];
        foreach ($items as $it) {
            $lineItems[] = [
                'price_data' => [
                    'currency' => $cur,
                    'product_data' => ['name' => $it['name']],
                    'unit_amount' => (int) round(((float) $it['unit_price']) * 100),
                ],
                'quantity' => (int) $it['quantity'],
            ];
        }
        if ($totals['shipping'] > 0) {
            $lineItems[] = [
                'price_data' => [
                    'currency' => $cur,
                    'product_data' => ['name' => 'Shipping'],
                    'unit_amount' => (int) round($totals['shipping'] * 100),
                ],
                'quantity' => 1,
            ];
        }

        try {
            $session = $stripe->createCheckoutSession([
                'mode' => 'payment',
                'success_url' => $this->absoluteUrl('/checkout/success') . '?session_id={CHECKOUT_SESSION_ID}',
                'cancel_url'  => $this->absoluteUrl('/checkout/cancel'),
                'payment_method_types' => ['card'],
                'billing_address_collection' => 'auto',
                'shipping_address_collection' => ['allowed_countries' => ['US']],
                'metadata' => ['order_id' => (string) $orderId, 'order_number' => $orderNumber],
                'line_items' => $lineItems,
            ]);
        } catch (\Throwable $e) {
            $this->db()->prepare("UPDATE orders SET status='cancelled' WHERE id=?")->execute([$orderId]);
            $this->render('checkout_error', ['message' => $e->getMessage()], 'Checkout error — Supreme Parts');
            return;
        }

        // Record the pending Stripe payment keyed by the session id (idempotency anchor).
        $this->db()->prepare(
            "INSERT INTO payments (order_id, gateway, gateway_txn_id, amount, `status`)
             VALUES (?, 'stripe', ?, ?, 'pending')"
        )->execute([$orderId, $session['id'], $totals['grand']]);

        header('Location: ' . $session['url']);
        exit;
    }

    /** GET /checkout/success */
    public function success(): void
    {
        $cart = new Cart();
        $sessionId = (string) ($_GET['session_id'] ?? '');
        $orderNumber = (string) ($_GET['order'] ?? '');

        if ($sessionId !== '') {
            $stripe = new Stripe();
            try {
                $session = $stripe->retrieveSession($sessionId);
            } catch (\Throwable $e) {
                $this->render('checkout_error', ['message' => 'Could not verify payment: ' . $e->getMessage()], 'Checkout — Supreme Parts');
                return;
            }
            $orderId = (int) ($session['metadata']['order_id'] ?? 0);
            if (($session['payment_status'] ?? '') === 'paid' && $orderId) {
                $this->finalizeOrder($orderId, $session, 'stripe');
                $cart->clear();
                $orderNumber = $session['metadata']['order_number'] ?? '';
            } else {
                $this->render('checkout_error', ['message' => 'Payment was not completed.'], 'Checkout — Supreme Parts');
                return;
            }
        }

        $order = $this->loadOrder($orderNumber);
        if (!$order) { $this->redirect('/'); }
        $this->render('checkout_success', ['order' => $order['order'], 'items' => $order['items']],
            'Order confirmed — Supreme Parts');
    }

    /** GET /checkout/cancel */
    public function cancel(): void
    {
        $this->render('checkout_cancel', [], 'Checkout cancelled — Supreme Parts');
    }

    /** Public entry for the Stripe webhook to finalize an order (idempotent). */
    public function finalizeFromWebhook(int $orderId, array $session): void
    {
        $this->finalizeOrder($orderId, $session, 'stripe');
    }

    // ---- internals ----

    private function createPendingOrder(array $items, array $totals): array
    {
        $db = $this->db();
        $orderNumber = $this->makeOrderNumber();
        $db->prepare(
            "INSERT INTO orders (order_number, email, `status`, subtotal, shipping_total, tax_total, grand_total, currency)
             VALUES (?, '', 'pending', ?, ?, 0, ?, 'USD')"
        )->execute([$orderNumber, $totals['subtotal'], $totals['shipping'], $totals['grand']]);
        $orderId = (int) $db->lastInsertId();

        $stmt = $db->prepare(
            "INSERT INTO order_items (order_id, part_id, part_number, name, quantity, unit_price, line_total)
             VALUES (?, ?, ?, ?, ?, ?, ?)"
        );
        foreach ($items as $it) {
            $stmt->execute([$orderId, (int) $it['part_id'], $it['part_number'], $it['name'],
                (int) $it['quantity'], $it['unit_price'], $it['line_total']]);
        }
        return [$orderId, $orderNumber];
    }

    /** Idempotently mark an order paid + record payment, address, inventory. */
    private function finalizeOrder(int $orderId, ?array $session, string $mode): void
    {
        $db = $this->db();
        $stmt = $db->prepare("SELECT id, `status` FROM orders WHERE id = ?");
        $stmt->execute([$orderId]);
        $order = $stmt->fetch();
        if (!$order || $order['status'] === 'paid' || $order['status'] === 'completed') {
            return; // already finalized — idempotent
        }

        $email = '';
        $ship = null;
        $txn = $mode === 'mock' ? ('mock_' . $orderId) : ($session['payment_intent']['id'] ?? $session['payment_intent'] ?? $session['id'] ?? null);
        if ($session) {
            $email = $session['customer_details']['email'] ?? ($session['customer_email'] ?? '');
            $ship = $session['shipping_details'] ?? ($session['shipping'] ?? null);
        }

        $db->beginTransaction();
        try {
            $db->prepare("UPDATE orders SET `status`='paid', email = CASE WHEN ?='' THEN email ELSE ? END WHERE id = ?")
               ->execute([$email, $email, $orderId]);

            // payment: update the pending stripe row if present, else insert.
            $upd = $db->prepare("UPDATE payments SET `status`='captured', gateway_txn_id = COALESCE(?, gateway_txn_id) WHERE order_id = ?");
            $upd->execute([$txn, $orderId]);
            if ($upd->rowCount() === 0) {
                $amt = $db->prepare("SELECT grand_total FROM orders WHERE id = ?");
                $amt->execute([$orderId]);
                $db->prepare(
                    "INSERT INTO payments (order_id, gateway, gateway_txn_id, amount, `status`)
                     VALUES (?, ?, ?, ?, 'captured')"
                )->execute([$orderId, $mode === 'mock' ? 'mock' : 'stripe', $txn, (float) $amt->fetch()['grand_total']]);
            }

            // shipping address from Stripe, if provided.
            if ($ship && !empty($ship['address'])) {
                $a = $ship['address'];
                $db->prepare(
                    "INSERT INTO order_addresses (order_id, `type`, name, line1, line2, city, state, postal_code, country)
                     VALUES (?, 'shipping', ?, ?, ?, ?, ?, ?, ?)"
                )->execute([$orderId, $ship['name'] ?? null, $a['line1'] ?? '', $a['line2'] ?? null,
                    $a['city'] ?? '', $a['state'] ?? '', $a['postal_code'] ?? '', $a['country'] ?? 'US']);
            }

            // decrement inventory (MAIN warehouse) for each line.
            $lines = $db->prepare("SELECT part_id, quantity FROM order_items WHERE order_id = ?");
            $lines->execute([$orderId]);
            $dec = $db->prepare(
                "UPDATE inventory SET quantity = GREATEST(0, quantity - ?) WHERE part_id = ? AND warehouse_code = 'MAIN'"
            );
            foreach ($lines->fetchAll() as $l) {
                $dec->execute([(int) $l['quantity'], (int) $l['part_id']]);
            }

            $db->commit();
        } catch (\Throwable $e) {
            $db->rollBack();
            throw $e;
        }
    }

    private function loadOrder(string $orderNumber): ?array
    {
        if ($orderNumber === '') return null;
        $db = $this->db();
        $stmt = $db->prepare("SELECT * FROM orders WHERE order_number = ?");
        $stmt->execute([$orderNumber]);
        $order = $stmt->fetch();
        if (!$order) return null;
        $items = $db->prepare("SELECT * FROM order_items WHERE order_id = ?");
        $items->execute([$order['id']]);
        return ['order' => $order, 'items' => $items->fetchAll()];
    }

    private function makeOrderNumber(): string
    {
        return 'SP-' . date('Ymd') . '-' . strtoupper(bin2hex(random_bytes(3)));
    }
}
