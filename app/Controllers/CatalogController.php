<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Core\Controller;

class CatalogController extends Controller
{
    /** Browse a make: its vehicles grouped by model/year -> vehicle pages. */
    public function make(string $makeSlug): void
    {
        $db = $this->db();
        $stmt = $db->prepare("SELECT id, name, slug FROM makes WHERE slug = ?");
        $stmt->execute([$makeSlug]);
        $make = $stmt->fetch();
        if (!$make) { $this->notFoundResponse(); return; }

        $stmt = $db->prepare(
            "SELECT v.slug, v.`year`, v.trim, mo.name AS model,
                    COALESCE(e.name,'Standard') AS engine
               FROM vehicles v
               JOIN models mo ON mo.id = v.model_id
          LEFT JOIN engines e ON e.id = v.engine_id
              WHERE v.make_id = ?
              ORDER BY mo.name, v.`year` DESC"
        );
        $stmt->execute([$make['id']]);
        $vehicles = $stmt->fetchAll();

        $this->render('make', compact('make', 'vehicles'),
            $make['name'] . ' Parts — Supreme Parts');
    }

    /** A selected vehicle: show the categories that have parts fitting it. */
    public function vehicle(string $slug): void
    {
        $db = $this->db();
        $vehicle = $this->loadVehicle($slug);
        if (!$vehicle) { $this->notFoundResponse(); return; }

        // Leaf part-types fitting this vehicle, with counts, tagged with their
        // RockAuto parent group (e.g. "Wiper & Washer") so the view can group them.
        $stmt = $db->prepare(
            "SELECT c.name, c.slug, COUNT(DISTINCT p.id) AS n,
                    COALESCE(par.name, c.name)               AS group_name,
                    COALESCE(par.position, c.position, 9999) AS group_pos
               FROM part_fitment pf
               JOIN parts p      ON p.id = pf.part_id
               JOIN categories c ON c.id = p.category_id
          LEFT JOIN categories par ON par.id = c.parent_id
              WHERE pf.vehicle_id = :vid
              GROUP BY c.id
              ORDER BY group_pos, group_name, COALESCE(c.position, 9999), c.name"
        );
        $stmt->execute([':vid' => $vehicle['id']]);
        $categories = $stmt->fetchAll();

        $this->render('vehicle', compact('vehicle', 'categories'),
            $this->vehicleLabel($vehicle) . ' Parts — Supreme Parts');
    }

    /** Parts of one category fitting one vehicle. */
    public function vehicleCategory(string $slug, string $catSlug): void
    {
        $db = $this->db();
        $vehicle = $this->loadVehicle($slug);
        if (!$vehicle) { $this->notFoundResponse(); return; }

        $stmt = $db->prepare("SELECT id, name, slug FROM categories WHERE slug = ?");
        $stmt->execute([$catSlug]);
        $category = $stmt->fetch();
        if (!$category) { $this->notFoundResponse(); return; }

        // Each part carries its variant span (RockAuto's inventory-tier / "Choose
        // Type" dropdown) and its style sub-group ("Beam (Standard)", "Winter"...)
        // so the list can surface multiple prices and section like RockAuto.
        $stmt = $db->prepare(
            "SELECT p.sku, p.part_number, p.name, p.price, p.core_charge,
                    p.primary_image_path, b.name AS brand, pf.note,
                    (SELECT COUNT(*)   FROM part_variants v WHERE v.part_id = p.id) AS n_variants,
                    (SELECT MIN(v.price) FROM part_variants v
                        WHERE v.part_id = p.id AND v.price IS NOT NULL) AS vmin,
                    (SELECT MAX(v.price) FROM part_variants v
                        WHERE v.part_id = p.id AND v.price IS NOT NULL) AS vmax,
                    (SELECT a.`value` FROM part_attributes a
                        WHERE a.part_id = p.id AND a.name = 'Style' LIMIT 1) AS style
               FROM part_fitment pf
               JOIN parts p  ON p.id = pf.part_id
          LEFT JOIN brands b ON b.id = p.brand_id
              WHERE pf.vehicle_id = :vid AND p.category_id = :cid
              ORDER BY (style IS NULL), style, (p.price IS NULL), p.price, b.name"
        );
        $stmt->execute([':vid' => $vehicle['id'], ':cid' => $category['id']]);
        $parts = $stmt->fetchAll();

        $this->render('parts', compact('vehicle', 'category', 'parts'),
            $category['name'] . ' — ' . $this->vehicleLabel($vehicle) . ' — Supreme Parts');
    }

    public function search(): void
    {
        $q = trim((string) ($_GET['q'] ?? ''));
        $parts = [];
        if ($q !== '') {
            $like = '%' . $q . '%';
            $stmt = $this->db()->prepare(
                "SELECT p.sku, p.part_number, p.name, p.price, p.primary_image_path,
                        b.name AS brand, COUNT(pf.id) AS fits
                   FROM parts p
              LEFT JOIN brands b ON b.id = p.brand_id
              LEFT JOIN part_fitment pf ON pf.part_id = p.id
                  WHERE p.name LIKE :q1 OR p.part_number LIKE :q2 OR p.sku LIKE :q3
                  GROUP BY p.id
                  ORDER BY (p.part_number = :exact) DESC, fits DESC
                  LIMIT 100"
            );
            // Native PDO prepares can't reuse a named placeholder, so give each
            // LIKE its own (:q1/:q2/:q3) — reusing :q threw HY093 and 500'd search.
            $stmt->execute([':q1' => $like, ':q2' => $like, ':q3' => $like, ':exact' => $q]);
            $parts = $stmt->fetchAll();
        }
        $this->render('search', compact('q', 'parts'),
            ($q !== '' ? "Search: {$q}" : 'Search') . ' — Supreme Parts');
    }

    // ---- helpers ----

    private function loadVehicle(string $slug): ?array
    {
        $stmt = $this->db()->prepare(
            "SELECT v.id, v.slug, v.`year`, v.trim,
                    m.name AS make, m.slug AS make_slug,
                    mo.name AS model, mo.slug AS model_slug,
                    e.name AS engine
               FROM vehicles v
               JOIN makes m   ON m.id = v.make_id
               JOIN models mo ON mo.id = v.model_id
          LEFT JOIN engines e ON e.id = v.engine_id
              WHERE v.slug = ?"
        );
        $stmt->execute([$slug]);
        $v = $stmt->fetch();
        return $v ?: null;
    }

    private function vehicleLabel(array $v): string
    {
        $bits = [$v['year'], $v['make'], $v['model']];
        if (!empty($v['engine'])) $bits[] = $v['engine'];
        if (!empty($v['trim']))   $bits[] = $v['trim'];
        return implode(' ', $bits);
    }
}
