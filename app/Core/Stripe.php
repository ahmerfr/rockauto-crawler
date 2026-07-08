<?php
declare(strict_types=1);

namespace App\Core;

/**
 * Minimal Stripe REST client over cURL (no SDK dependency). Covers what hosted
 * Checkout needs: create a Checkout Session, retrieve it, and verify webhook
 * signatures. When no secret key is configured, enabled() is false and callers
 * fall back to mock mode.
 */
class Stripe
{
    private array $cfg;

    public function __construct()
    {
        $this->cfg = (require BASE_DIR . '/config/config.php')['stripe'];
    }

    public function enabled(): bool
    {
        return !empty($this->cfg['secret']);
    }

    public function publishableKey(): string
    {
        return (string) ($this->cfg['publishable'] ?? '');
    }

    public function currency(): string
    {
        return (string) ($this->cfg['currency'] ?? 'usd');
    }

    /** Create a Checkout Session. $params is the Stripe form param tree. */
    public function createCheckoutSession(array $params): array
    {
        return $this->request('POST', '/v1/checkout/sessions', $params);
    }

    public function retrieveSession(string $id): array
    {
        return $this->request('GET', '/v1/checkout/sessions/' . rawurlencode($id)
            . '?expand[]=payment_intent', null);
    }

    /** Verify a webhook signature and return the decoded event, or throw. */
    public function constructEvent(string $payload, string $sigHeader): array
    {
        $secret = (string) ($this->cfg['webhook_secret'] ?? '');
        if ($secret === '') {
            throw new \RuntimeException('No webhook secret configured.');
        }
        $t = null; $v1 = [];
        foreach (explode(',', $sigHeader) as $part) {
            [$k, $val] = array_pad(explode('=', trim($part), 2), 2, '');
            if ($k === 't') $t = $val;
            if ($k === 'v1') $v1[] = $val;
        }
        if ($t === null || !$v1) {
            throw new \RuntimeException('Malformed Stripe-Signature header.');
        }
        if (abs(time() - (int) $t) > 300) {
            throw new \RuntimeException('Webhook timestamp outside tolerance.');
        }
        $expected = hash_hmac('sha256', $t . '.' . $payload, $secret);
        $ok = false;
        foreach ($v1 as $sig) { if (hash_equals($expected, $sig)) { $ok = true; break; } }
        if (!$ok) {
            throw new \RuntimeException('Webhook signature mismatch.');
        }
        return json_decode($payload, true) ?: [];
    }

    private function request(string $method, string $path, ?array $params): array
    {
        $ch = curl_init('https://api.stripe.com' . $path);
        $headers = [
            'Authorization: Bearer ' . $this->cfg['secret'],
            'Stripe-Version: 2024-06-20',
        ];
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        if ($method === 'POST') {
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($params ?? [], '', '&'));
        }
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        $body = curl_exec($ch);
        if ($body === false) {
            $err = curl_error($ch);
            curl_close($ch);
            throw new \RuntimeException('Stripe request failed: ' . $err);
        }
        $status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        $data = json_decode((string) $body, true) ?? [];
        if ($status >= 400) {
            $msg = $data['error']['message'] ?? ('HTTP ' . $status);
            throw new \RuntimeException('Stripe error: ' . $msg);
        }
        return $data;
    }
}
