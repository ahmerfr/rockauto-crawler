<?php
declare(strict_types=1);

namespace App\Core;

use PDO;

/**
 * Session cart backed by the carts / cart_items tables, keyed by an `sp_cart`
 * cookie token so a guest's cart survives across requests. Prices are captured
 * at add-time into cart_items.unit_price.
 */
class Cart
{
    private const COOKIE = 'sp_cart';

    private PDO $db;
    private ?int $cartId = null;

    public function __construct()
    {
        $this->db = Database::connection();
    }

    /** Read-only cart line count from an existing cookie (no cookie is set). */
    public static function headerCount(): int
    {
        if (empty($_COOKIE[self::COOKIE])) return 0;
        $db = Database::connection();
        $stmt = $db->prepare(
            "SELECT COALESCE(SUM(ci.quantity),0) AS n
               FROM carts c JOIN cart_items ci ON ci.cart_id = c.id
              WHERE c.session_token = ?"
        );
        $stmt->execute([$_COOKIE[self::COOKIE]]);
        return (int) $stmt->fetch()['n'];
    }

    private function token(bool $create = true): ?string
    {
        if (!empty($_COOKIE[self::COOKIE])) return $_COOKIE[self::COOKIE];
        if (!$create) return null;
        $token = bin2hex(random_bytes(32));
        $_COOKIE[self::COOKIE] = $token;
        $base = (require BASE_DIR . '/config/config.php')['app']['base_path'] ?: '/';
        setcookie(self::COOKIE, $token, [
            'expires'  => time() + 60 * 60 * 24 * 30,
            'path'     => $base,
            'httponly' => true,
            'samesite' => 'Lax',
        ]);
        return $token;
    }

    private function id(bool $create = true): ?int
    {
        if ($this->cartId !== null) return $this->cartId;
        $token = $this->token($create);
        if ($token === null) return null;
        $stmt = $this->db->prepare("SELECT id FROM carts WHERE session_token = ?");
        $stmt->execute([$token]);
        $row = $stmt->fetch();
        if ($row) return $this->cartId = (int) $row['id'];
        if (!$create) return null;
        $this->db->prepare("INSERT INTO carts (session_token) VALUES (?)")->execute([$token]);
        return $this->cartId = (int) $this->db->lastInsertId();
    }

    /**
     * Add a part (by sku) to the cart; returns true if added.
     * $variantId picks a RockAuto option (part_variants). 0 = the part's default price.
     */
    public function addBySku(string $sku, int $qty = 1, int $variantId = 0): bool
    {
        $qty = max(1, $qty);
        $stmt = $this->db->prepare("SELECT id, price FROM parts WHERE sku = ? AND status = 'active'");
        $stmt->execute([$sku]);
        $part = $stmt->fetch();
        if (!$part) return false;
        $partId = (int) $part['id'];
        $price = $part['price'];

        if ($variantId > 0) {
            // The variant must belong to THIS part — never trust a posted id.
            $vs = $this->db->prepare(
                "SELECT price, oos FROM part_variants WHERE id = ? AND part_id = ?"
            );
            $vs->execute([$variantId, $partId]);
            $variant = $vs->fetch();
            if (!$variant) return false;
            if ($variant['oos']) return false;        // that option is out of stock
            $price = $variant['price'];
        }

        // NULL price = out of stock (RockAuto lists no price). Not purchasable, and
        // cart_items.unit_price is NOT NULL — never let a priceless line into a cart.
        if ($price === null) return false;

        // Capture the CUSTOMER price (RockAuto cost * reseller markup) so the cart,
        // Stripe charge and stored order all bill the marked-up amount. The base cost
        // stays in parts.price; markup lives only in the settings table.
        $sell = \sell_price($price);

        $cartId = $this->id();
        $this->db->prepare(
            "INSERT INTO cart_items (cart_id, part_id, variant_id, quantity, unit_price)
             VALUES (:cart, :part, :variant, :qty, :price)
             ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity),
                                     unit_price = VALUES(unit_price)"
        )->execute([':cart' => $cartId, ':part' => $partId, ':variant' => $variantId,
                    ':qty' => $qty, ':price' => $sell]);
        return true;
    }

    /** A cart line is (part, variant) — the same part in two options is two lines. */
    public function setQty(int $partId, int $qty, int $variantId = 0): void
    {
        $cartId = $this->id(false);
        if ($cartId === null) return;
        if ($qty <= 0) { $this->remove($partId, $variantId); return; }
        $this->db->prepare(
            "UPDATE cart_items SET quantity = ? WHERE cart_id = ? AND part_id = ? AND variant_id = ?"
        )->execute([$qty, $cartId, $partId, $variantId]);
    }

    public function remove(int $partId, int $variantId = 0): void
    {
        $cartId = $this->id(false);
        if ($cartId === null) return;
        $this->db->prepare(
            "DELETE FROM cart_items WHERE cart_id = ? AND part_id = ? AND variant_id = ?"
        )->execute([$cartId, $partId, $variantId]);
    }

    /** @return array<int,array> cart lines with part + chosen-option info */
    public function items(): array
    {
        $cartId = $this->id(false);
        if ($cartId === null) return [];
        $stmt = $this->db->prepare(
            "SELECT ci.part_id, ci.variant_id, ci.quantity, ci.unit_price,
                    p.sku, p.part_number, p.name, p.primary_image_path,
                    b.name AS brand, pv.`type` AS variant_type,
                    (ci.quantity * ci.unit_price) AS line_total
               FROM cart_items ci
               JOIN parts p          ON p.id = ci.part_id
          LEFT JOIN brands b         ON b.id = p.brand_id
          LEFT JOIN part_variants pv ON pv.id = ci.variant_id
              WHERE ci.cart_id = ?
              ORDER BY p.name"
        );
        $stmt->execute([$cartId]);
        return $stmt->fetchAll();
    }

    public function count(): int
    {
        $cartId = $this->id(false);
        if ($cartId === null) return 0;
        $stmt = $this->db->prepare("SELECT COALESCE(SUM(quantity),0) AS n FROM cart_items WHERE cart_id = ?");
        $stmt->execute([$cartId]);
        return (int) $stmt->fetch()['n'];
    }

    /** @return array{subtotal:float,shipping:float,grand:float} */
    public function totals(): array
    {
        $subtotal = 0.0;
        foreach ($this->items() as $it) { $subtotal += (float) $it['line_total']; }
        $ship = (require BASE_DIR . '/config/config.php')['shipping'];
        $shipping = ($subtotal <= 0 || $subtotal >= (float) $ship['free_over']) ? 0.0 : (float) $ship['flat'];
        return ['subtotal' => $subtotal, 'shipping' => $shipping, 'grand' => $subtotal + $shipping];
    }

    public function isEmpty(): bool
    {
        return $this->count() === 0;
    }

    public function clear(): void
    {
        $cartId = $this->id(false);
        if ($cartId === null) return;
        $this->db->prepare("DELETE FROM cart_items WHERE cart_id = ?")->execute([$cartId]);
    }
}
