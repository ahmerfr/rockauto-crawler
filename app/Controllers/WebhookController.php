<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Core\Controller;
use App\Core\Stripe;

class WebhookController extends Controller
{
    /** POST /webhook/stripe — confirm payment server-side (source of truth). */
    public function stripe(): void
    {
        $payload = file_get_contents('php://input') ?: '';
        $sig = $_SERVER['HTTP_STRIPE_SIGNATURE'] ?? '';
        $stripe = new Stripe();
        try {
            $event = $stripe->constructEvent($payload, $sig);
        } catch (\Throwable $e) {
            http_response_code(400);
            echo 'Webhook error: ' . $e->getMessage();
            return;
        }

        if (($event['type'] ?? '') === 'checkout.session.completed') {
            $session = $event['data']['object'] ?? [];
            $orderId = (int) ($session['metadata']['order_id'] ?? 0);
            if ($orderId && ($session['payment_status'] ?? '') === 'paid') {
                // Reuse the checkout finalizer (idempotent).
                (new CheckoutController())->finalizeFromWebhook($orderId, $session);
            }
        }

        http_response_code(200);
        echo 'ok';
    }
}
