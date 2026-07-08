<?php
declare(strict_types=1);

namespace App\Controllers;

use App\Core\Controller;

class HomeController extends Controller
{
    public function index(): void
    {
        $db = $this->db();

        // The catalog tree root: every make that has vehicles, alphabetical.
        $makes = $db->query(
            "SELECT m.name, m.slug, COUNT(DISTINCT v.id) AS vehicles
               FROM makes m
               JOIN vehicles v ON v.make_id = m.id
              GROUP BY m.id
              ORDER BY m.name ASC"
        )->fetchAll();

        $stats = $db->query(
            "SELECT
               (SELECT COUNT(*) FROM parts)        AS parts,
               (SELECT COUNT(*) FROM vehicles)      AS vehicles,
               (SELECT COUNT(*) FROM makes)         AS makes,
               (SELECT COUNT(*) FROM part_fitment)  AS fitments"
        )->fetch();

        // A-Z quick-jump letters that actually have makes.
        $letters = [];
        foreach ($makes as $m) {
            $l = strtoupper($m['name'][0] ?? '');
            if ($l !== '' && ctype_alpha($l)) $letters[$l] = true;
        }

        $this->render('home', ['makes' => $makes, 'stats' => $stats, 'letters' => array_keys($letters)],
            'Supreme Parts — All the parts your car will ever need');
    }

    public function notFound(): void
    {
        $this->notFoundResponse();
    }
}
