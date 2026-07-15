<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Core\Controller;

class PartController extends Controller
{
    public function show(string $sku): void
    {
        $db = $this->db();

        $stmt = $db->prepare(
            "SELECT p.*, b.name AS brand, b.slug AS brand_slug, c.name AS category, c.slug AS category_slug
               FROM parts p
          LEFT JOIN brands b     ON b.id = p.brand_id
          LEFT JOIN categories c ON c.id = p.category_id
              WHERE p.sku = ?"
        );
        $stmt->execute([$sku]);
        $part = $stmt->fetch();
        if (!$part) { $this->notFoundResponse(); return; }

        // GROUP BY path: RockAuto serves the same photo under carousel-variant URLs
        // that normalize to one local file, so dedupe by path or it renders twice.
        $images = $db->prepare("SELECT path, MIN(alt) AS alt FROM part_images WHERE part_id = ? GROUP BY path ORDER BY MIN(position)");
        $images->execute([$part['id']]);
        $images = $images->fetchAll();

        $attrs = $db->prepare("SELECT name, `value` FROM part_attributes WHERE part_id = ? ORDER BY id");
        $attrs->execute([$part['id']]);
        $attrs = $attrs->fetchAll();

        // RockAuto's option dropdown (inventory tiers / "Choose Type" packs).
        // Default option first, then cheapest; out-of-stock options last.
        $variants = $db->prepare(
            "SELECT id, code, `type`, price, core_charge, oos, is_default, pack_size, pack_total
               FROM part_variants WHERE part_id = ?
              ORDER BY oos ASC, is_default DESC, (price IS NULL), price ASC, position ASC"
        );
        $variants->execute([$part['id']]);
        $variants = $variants->fetchAll();

        // Which vehicles this part fits (the fitment table — RockAuto's core view).
        $fit = $db->prepare(
            "SELECT v.slug, v.`year`, v.trim, m.name AS make, mo.name AS model,
                    COALESCE(e.name,'') AS engine, pf.note
               FROM part_fitment pf
               JOIN vehicles v ON v.id = pf.vehicle_id
               JOIN makes m    ON m.id = v.make_id
               JOIN models mo  ON mo.id = v.model_id
          LEFT JOIN engines e  ON e.id = v.engine_id
              WHERE pf.part_id = ?
              ORDER BY m.name, mo.name, v.`year` DESC
              LIMIT 500"
        );
        $fit->execute([$part['id']]);
        $fitment = $fit->fetchAll();

        $stock = $db->prepare("SELECT SUM(quantity) AS qty FROM inventory WHERE part_id = ?");
        $stock->execute([$part['id']]);
        $stock = (int) ($stock->fetch()['qty'] ?? 0);

        $this->render('part', compact('part', 'images', 'attrs', 'fitment', 'stock', 'variants'),
            $part['name'] . ' — Supreme Parts');
    }
}
