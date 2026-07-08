<?php
declare(strict_types=1);

namespace App\Controllers\Admin;

use App\Core\Auth;

/**
 * Import runner: view import_logs and trigger the Python importers.
 * Runs are BOUNDED (small scope) so they complete inside a web request; large
 * catalog pulls should be run from the CLI (documented in the UI).
 */
class ImportController extends AdminController
{
    public function index(): void
    {
        $logs = $this->db()->query(
            "SELECT il.*, a.name AS admin_name
               FROM import_logs il LEFT JOIN admins a ON a.id = il.admin_id
              ORDER BY il.created_at DESC LIMIT 50"
        )->fetchAll();
        $canRun = function_exists('shell_exec');
        $this->adminRender('imports/index',
            ['logs' => $logs, 'csrf' => Auth::token(), 'canRun' => $canRun, '_active' => 'imports'],
            'Imports');
    }

    public function runVpic(): void
    {
        $this->requireCsrf();
        $makes = trim((string) ($_POST['makes'] ?? 'Honda')) ?: 'Honda';
        $from  = (int) ($_POST['from'] ?? 2020);
        $to    = (int) ($_POST['to'] ?? 2021);
        // sanitize: makes = comma list of letters/spaces/hyphens only
        $makes = preg_replace('/[^A-Za-z0-9, \-]/', '', $makes);
        $cmd = sprintf('python bin/import_vpic.py --makes %s --from %d --to %d',
            escapeshellarg($makes), $from, $to);
        $this->runCli($cmd, 'vpic', "makes={$makes} {$from}-{$to}");
        $this->redirect('/admin/imports');
    }

    public function runAcesPies(): void
    {
        $this->requireCsrf();
        $cmd = 'python bin/ingest_acespies.py scraper/sample_aces.xml scraper/sample_pies.xml scraper/reference';
        $this->runCli($cmd, 'aces_pies', 'sample_aces.xml + sample_pies.xml');
        $this->redirect('/admin/imports');
    }

    private function runCli(string $cmd, string $type, string $filename): void
    {
        if (!function_exists('shell_exec')) {
            $this->flash('error', 'shell_exec is disabled; run this importer from the CLI.');
            return;
        }
        @set_time_limit(300);
        $root = BASE_DIR;
        // cd into project root, merge stderr, run.
        $full = 'cd ' . escapeshellarg($root) . ' && ' . $cmd . ' 2>&1';
        $output = (string) shell_exec($full);

        [$ok, $failed] = $this->parseCounts($output, $type);
        $status = ($output === '' ? 'failed' : (stripos($output, 'error') !== false || stripos($output, 'traceback') !== false ? 'error' : 'completed'));

        $user = Auth::user();
        $this->db()->prepare(
            "INSERT INTO import_logs (admin_id, `type`, filename, rows_total, rows_ok, rows_failed, `status`, message)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )->execute([$user['id'] ?? null, $type, $filename, $ok + $failed, $ok, $failed, $status,
            mb_substr($output, 0, 4000)]);

        $this->flash($status === 'completed' ? 'ok' : 'error',
            "Import {$type}: {$status}" . ($ok ? " ({$ok} rows)" : ''));
    }

    /** Best-effort row extraction from importer stdout. */
    private function parseCounts(string $out, string $type): array
    {
        $ok = 0; $failed = 0;
        if (preg_match('/staged\s+(\d+)/i', $out, $m)) { $ok = (int) $m[1]; }
        if (preg_match('/vehicles?\D+(\d+)/i', $out, $m)) { $ok = max($ok, (int) $m[1]); }
        if (preg_match('/fitment[^\d]*(\d+)/i', $out, $m)) { $ok = max($ok, (int) $m[1]); }
        if (preg_match('/(\d+)\s+failed/i', $out, $m)) { $failed = (int) $m[1]; }
        return [$ok, $failed];
    }
}
