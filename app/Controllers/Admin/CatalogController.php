<?php
declare(strict_types=1);

namespace App\Controllers\Admin;

class CatalogController extends AdminController
{
    public function index(): void
    {
        $db = $this->db();
        $makes = $db->query(
            "SELECT m.id, m.name, m.slug, m.is_active,
                    (SELECT COUNT(*) FROM models mo WHERE mo.make_id = m.id) AS models,
                    (SELECT COUNT(*) FROM vehicles v WHERE v.make_id = m.id) AS vehicles
               FROM makes m ORDER BY m.name"
        )->fetchAll();

        $q = trim((string) ($_GET['q'] ?? ''));
        $vehicles = [];
        if ($q !== '') {
            $stmt = $db->prepare(
                "SELECT v.slug, v.`year`, v.trim, m.name AS make, mo.name AS model,
                        COALESCE(e.name,'') AS engine
                   FROM vehicles v
                   JOIN makes m   ON m.id = v.make_id
                   JOIN models mo ON mo.id = v.model_id
              LEFT JOIN engines e ON e.id = v.engine_id
                  WHERE m.name LIKE :q OR mo.name LIKE :q OR v.slug LIKE :q
                  ORDER BY m.name, mo.name, v.`year` DESC LIMIT 100"
            );
            $stmt->execute([':q' => '%' . $q . '%']);
            $vehicles = $stmt->fetchAll();
        }

        $this->adminRender('catalog/index',
            ['makes' => $makes, 'vehicles' => $vehicles, 'q' => $q, '_active' => 'catalog'], 'Catalog');
    }
}
