<?php
declare(strict_types=1);

namespace App\Controllers\Admin;

class DashboardController extends AdminController
{
    public function index(): void
    {
        $db = $this->db();
        $counts = $db->query(
            "SELECT
               (SELECT COUNT(*) FROM parts)        AS parts,
               (SELECT COUNT(*) FROM part_fitment)  AS fitments,
               (SELECT COUNT(*) FROM vehicles)      AS vehicles,
               (SELECT COUNT(*) FROM makes)         AS makes,
               (SELECT COUNT(*) FROM models)        AS models,
               (SELECT COUNT(*) FROM brands)        AS brands,
               (SELECT COUNT(*) FROM categories)    AS categories,
               (SELECT COUNT(*) FROM orders)        AS orders"
        )->fetch();

        $recentParts = $db->query(
            "SELECT p.sku, p.name, p.price, b.name AS brand, p.updated_at
               FROM parts p LEFT JOIN brands b ON b.id = p.brand_id
              ORDER BY p.updated_at DESC LIMIT 8"
        )->fetchAll();

        $recentImports = $db->query(
            "SELECT `type`, filename, rows_ok, rows_failed, `status`, created_at
               FROM import_logs ORDER BY created_at DESC LIMIT 6"
        )->fetchAll();

        $this->adminRender('dashboard',
            ['counts' => $counts, 'recentParts' => $recentParts, 'recentImports' => $recentImports, '_active' => 'dashboard'],
            'Dashboard');
    }
}
