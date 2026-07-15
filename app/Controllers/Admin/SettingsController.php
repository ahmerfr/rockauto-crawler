<?php
declare(strict_types=1);

namespace App\Controllers\Admin;

use App\Core\Auth;

/** Storefront settings — currently the reseller markup applied to RockAuto costs. */
class SettingsController extends AdminController
{
    public function index(): void
    {
        $pct = $this->db()->query(
            "SELECT `value` FROM settings WHERE `key` = 'reseller_markup_pct'"
        )->fetchColumn();
        $this->adminRender('settings', [
            'markup' => $pct === false ? '0' : (string) $pct,
            'csrf'   => Auth::token(),
            '_active' => 'settings',
        ], 'Pricing');
    }

    public function save(): void
    {
        $this->requireCsrf();
        // Accept 0–100000%. Clamp negatives to 0 so we never sell below cost.
        $raw = str_replace([',', '%', ' '], '', (string) ($_POST['markup_pct'] ?? '0'));
        $pct = is_numeric($raw) ? max(0.0, min(100000.0, (float) $raw)) : 0.0;
        $val = rtrim(rtrim(number_format($pct, 2, '.', ''), '0'), '.'); // tidy: 25.00 -> 25
        $this->db()->prepare(
            "INSERT INTO settings (`key`,`value`) VALUES ('reseller_markup_pct', ?)
             ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)"
        )->execute([$val === '' ? '0' : $val]);
        $this->flash('ok', "Markup saved: RockAuto cost +{$val}%. New adds to cart use it immediately.");
        $this->redirect('/admin/settings');
    }
}
