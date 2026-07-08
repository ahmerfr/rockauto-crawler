<?php
declare(strict_types=1);

namespace App\Controllers\Admin;

use App\Core\Auth;

class BrandController extends AdminController
{
    public function index(): void
    {
        $brands = $this->db()->query(
            "SELECT b.id, b.name, b.slug, b.is_active,
                    (SELECT COUNT(*) FROM parts p WHERE p.brand_id = b.id) AS parts
               FROM brands b ORDER BY b.name"
        )->fetchAll();
        $this->adminRender('brands/index',
            ['brands' => $brands, 'csrf' => Auth::token(), '_active' => 'brands'], 'Brands');
    }

    public function store(): void
    {
        $this->requireCsrf();
        $name = trim((string) ($_POST['name'] ?? ''));
        if ($name === '') { $this->flash('error', 'Brand name required.'); $this->redirect('/admin/brands'); }
        try {
            $this->db()->prepare("INSERT INTO brands (name, slug) VALUES (?, ?)")
                 ->execute([$name, $this->slugify($name)]);
            $this->flash('ok', 'Brand added.');
        } catch (\PDOException $e) {
            $this->flash('error', 'Duplicate or invalid brand.');
        }
        $this->redirect('/admin/brands');
    }

    public function update(string $id): void
    {
        $this->requireCsrf();
        $name = trim((string) ($_POST['name'] ?? ''));
        $active = isset($_POST['is_active']) ? 1 : 0;
        if ($name === '') { $this->flash('error', 'Brand name required.'); $this->redirect('/admin/brands'); }
        $this->db()->prepare("UPDATE brands SET name = ?, slug = ?, is_active = ? WHERE id = ?")
             ->execute([$name, $this->slugify($name), $active, (int) $id]);
        $this->flash('ok', 'Brand updated.');
        $this->redirect('/admin/brands');
    }

    public function delete(string $id): void
    {
        $this->requireCsrf();
        // parts.brand_id is ON DELETE SET NULL, so this won't orphan parts.
        $this->db()->prepare("DELETE FROM brands WHERE id = ?")->execute([(int) $id]);
        $this->flash('ok', 'Brand deleted.');
        $this->redirect('/admin/brands');
    }

    private function slugify(string $s): string
    {
        $s = strtolower(trim($s));
        return trim(preg_replace('/[^a-z0-9]+/', '-', $s), '-') ?: 'brand';
    }
}
