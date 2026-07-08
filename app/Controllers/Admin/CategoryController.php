<?php
declare(strict_types=1);

namespace App\Controllers\Admin;

use App\Core\Auth;

class CategoryController extends AdminController
{
    public function index(): void
    {
        $db = $this->db();
        $categories = $db->query(
            "SELECT c.id, c.parent_id, c.name, c.slug, c.position, c.is_active,
                    pc.name AS parent_name,
                    (SELECT COUNT(*) FROM parts p WHERE p.category_id = c.id) AS parts
               FROM categories c
          LEFT JOIN categories pc ON pc.id = c.parent_id
              ORDER BY c.slug"
        )->fetchAll();
        $parents = $db->query("SELECT id, name, slug FROM categories ORDER BY slug")->fetchAll();
        $this->adminRender('categories/index',
            ['categories' => $categories, 'parents' => $parents, 'csrf' => Auth::token(), '_active' => 'categories'],
            'Categories');
    }

    public function store(): void
    {
        $this->requireCsrf();
        $name = trim((string) ($_POST['name'] ?? ''));
        $parent = ($_POST['parent_id'] ?? '') !== '' ? (int) $_POST['parent_id'] : null;
        if ($name === '') { $this->flash('error', 'Category name required.'); $this->redirect('/admin/categories'); }
        try {
            $this->db()->prepare(
                "INSERT INTO categories (parent_id, name, slug, position) VALUES (?, ?, ?, ?)"
            )->execute([$parent, $name, $this->slugify($name, $parent), (int) ($_POST['position'] ?? 0)]);
            $this->flash('ok', 'Category added.');
        } catch (\PDOException $e) {
            $this->flash('error', 'Duplicate slug or invalid category.');
        }
        $this->redirect('/admin/categories');
    }

    public function update(string $id): void
    {
        $this->requireCsrf();
        $name = trim((string) ($_POST['name'] ?? ''));
        $parent = ($_POST['parent_id'] ?? '') !== '' ? (int) $_POST['parent_id'] : null;
        if ($parent === (int) $id) { $parent = null; } // can't be its own parent
        $active = isset($_POST['is_active']) ? 1 : 0;
        if ($name === '') { $this->flash('error', 'Category name required.'); $this->redirect('/admin/categories'); }
        $this->db()->prepare(
            "UPDATE categories SET parent_id = ?, name = ?, position = ?, is_active = ? WHERE id = ?"
        )->execute([$parent, $name, (int) ($_POST['position'] ?? 0), $active, (int) $id]);
        $this->flash('ok', 'Category updated.');
        $this->redirect('/admin/categories');
    }

    public function delete(string $id): void
    {
        $this->requireCsrf();
        $this->db()->prepare("DELETE FROM categories WHERE id = ?")->execute([(int) $id]);
        $this->flash('ok', 'Category deleted.');
        $this->redirect('/admin/categories');
    }

    private function slugify(string $name, ?int $parent): string
    {
        $base = strtolower(trim($name));
        $base = trim(preg_replace('/[^a-z0-9]+/', '-', $base), '-') ?: 'category';
        // categories.slug is globally unique; suffix with parent id to reduce collisions.
        return $parent ? $base . '-' . $parent : $base;
    }
}
