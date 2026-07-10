<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Core\Controller;

/**
 * JSON endpoints powering the RockAuto-style cascading vehicle picker.
 * Year -> Make -> Model -> Engine(vehicle). Each step filters vehicles.
 */
class ApiController extends Controller
{
    public function years(): void
    {
        $rows = $this->db()->query(
            "SELECT DISTINCT `year` FROM vehicles ORDER BY `year` DESC"
        )->fetchAll(\PDO::FETCH_COLUMN);
        $this->json(array_map('intval', $rows));
    }

    public function makes(): void
    {
        $year = (int) ($_GET['year'] ?? 0);
        $stmt = $this->db()->prepare(
            "SELECT DISTINCT m.name, m.slug
               FROM makes m JOIN vehicles v ON v.make_id = m.id
              WHERE (:y0 = 0 OR v.`year` = :y1)
              ORDER BY m.name"
        );
        $stmt->execute([':y0' => $year, ':y1' => $year]);
        $this->json($stmt->fetchAll());
    }

    public function models(): void
    {
        $year = (int) ($_GET['year'] ?? 0);
        $make = (string) ($_GET['make'] ?? '');
        $stmt = $this->db()->prepare(
            "SELECT DISTINCT mo.name, mo.slug
               FROM models mo
               JOIN vehicles v ON v.model_id = mo.id
               JOIN makes m    ON m.id = v.make_id
              WHERE m.slug = :make AND (:y0 = 0 OR v.`year` = :y1)
              ORDER BY mo.name"
        );
        $stmt->execute([':make' => $make, ':y0' => $year, ':y1' => $year]);
        $this->json($stmt->fetchAll());
    }

    /** Returns selectable vehicles (engine variants) for make+model+year. */
    public function vehicles(): void
    {
        $year  = (int) ($_GET['year'] ?? 0);
        $make  = (string) ($_GET['make'] ?? '');
        $model = (string) ($_GET['model'] ?? '');
        $stmt = $this->db()->prepare(
            "SELECT v.slug,
                    COALESCE(e.name, 'Standard') AS label,
                    v.trim
               FROM vehicles v
               JOIN makes m  ON m.id = v.make_id
               JOIN models mo ON mo.id = v.model_id
          LEFT JOIN engines e ON e.id = v.engine_id
              WHERE m.slug = :make AND mo.slug = :model
                AND (:y0 = 0 OR v.`year` = :y1)
              ORDER BY label, v.trim"
        );
        $stmt->execute([':make' => $make, ':model' => $model, ':y0' => $year, ':y1' => $year]);
        $rows = $stmt->fetchAll();
        foreach ($rows as &$r) {
            if (!empty($r['trim'])) {
                $r['label'] .= ' — ' . $r['trim'];
            }
            unset($r['trim']);
        }
        $this->json($rows);
    }

    // ---- Catalog tree (RockAuto-style expandable navigation) ----

    /** Level 1: every make that has vehicles, alphabetical, with vehicle counts. */
    public function treeMakes(): void
    {
        $rows = $this->db()->query(
            "SELECT m.name, m.slug, COUNT(DISTINCT v.id) AS n
               FROM makes m JOIN vehicles v ON v.make_id = m.id
              GROUP BY m.id ORDER BY m.name"
        )->fetchAll();
        $this->json($rows);
    }

    /** Level 2: years for a make (newest first). */
    public function treeYears(): void
    {
        $stmt = $this->db()->prepare(
            "SELECT DISTINCT v.`year`
               FROM vehicles v JOIN makes m ON m.id = v.make_id
              WHERE m.slug = ? ORDER BY v.`year` DESC"
        );
        $stmt->execute([(string) ($_GET['make'] ?? '')]);
        $this->json(array_map('intval', $stmt->fetchAll(\PDO::FETCH_COLUMN)));
    }

    /** Level 5: part GROUPS fitting a vehicle (RockAuto's "Brake & Wheel Hub" tier).
     *  Parts hang off a leaf part-type whose parent is the group; a category with no
     *  parent is its own group. */
    public function treeGroups(): void
    {
        $stmt = $this->db()->prepare(
            "SELECT g.name, g.slug, COUNT(DISTINCT p.id) AS n
               FROM vehicles v
               JOIN part_fitment pf ON pf.vehicle_id = v.id
               JOIN parts p         ON p.id = pf.part_id
               JOIN categories c    ON c.id = p.category_id
               JOIN categories g    ON g.id = COALESCE(c.parent_id, c.id)
              WHERE v.slug = ?
              GROUP BY g.id ORDER BY g.name"
        );
        $stmt->execute([(string) ($_GET['vehicle'] ?? '')]);
        $this->json($stmt->fetchAll());
    }

    /** Level 6: part-types inside one group, for a vehicle ("Brake Fluid"). */
    public function treeCategories(): void
    {
        $stmt = $this->db()->prepare(
            "SELECT c.name, c.slug, COUNT(DISTINCT p.id) AS n
               FROM vehicles v
               JOIN part_fitment pf ON pf.vehicle_id = v.id
               JOIN parts p         ON p.id = pf.part_id
               JOIN categories c    ON c.id = p.category_id
               JOIN categories g    ON g.id = COALESCE(c.parent_id, c.id)
              WHERE v.slug = :veh AND g.slug = :grp
              GROUP BY c.id ORDER BY c.name"
        );
        $stmt->execute([':veh' => (string) ($_GET['vehicle'] ?? ''),
                        ':grp' => (string) ($_GET['group'] ?? '')]);
        $this->json($stmt->fetchAll());
    }

    /** Level 7 (leaf): parts of a part-type fitting a vehicle.
     *  Out-of-stock (price IS NULL) sorts last, as RockAuto does. */
    public function treeParts(): void
    {
        $stmt = $this->db()->prepare(
            "SELECT p.sku, p.part_number, p.name, p.price, p.core_charge,
                    p.primary_image_path AS img, b.name AS brand, pf.note
               FROM vehicles v
               JOIN part_fitment pf ON pf.vehicle_id = v.id
               JOIN parts p         ON p.id = pf.part_id
          LEFT JOIN brands b        ON b.id = p.brand_id
              WHERE v.slug = :veh AND p.category_id =
                    (SELECT id FROM categories WHERE slug = :cat)
              ORDER BY (p.price IS NULL), b.name, p.price"
        );
        $stmt->execute([':veh' => (string) ($_GET['vehicle'] ?? ''),
                        ':cat' => (string) ($_GET['category'] ?? '')]);
        $this->json($stmt->fetchAll());
    }
}
