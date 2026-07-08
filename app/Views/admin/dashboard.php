<?php /** @var array $counts @var array $recentParts @var array $recentImports @var \App\Core\Controller $_controller */ ?>
<h1 class="adm-h1">Dashboard</h1>

<div class="adm-cards">
  <?php
  $cards = [
    ['Parts', $counts['parts'], '/admin/parts'],
    ['Fitments', $counts['fitments'], null],
    ['Vehicles', $counts['vehicles'], '/admin/catalog'],
    ['Makes', $counts['makes'], '/admin/catalog'],
    ['Models', $counts['models'], null],
    ['Brands', $counts['brands'], '/admin/brands'],
    ['Categories', $counts['categories'], '/admin/categories'],
    ['Orders', $counts['orders'], null],
  ];
  foreach ($cards as [$label, $n, $link]): ?>
    <?php if ($link): ?><a class="adm-card" href="<?= e($_controller->url($link)) ?>"><?php else: ?><div class="adm-card"><?php endif; ?>
      <span class="adm-card-n"><?= number_format((int)$n) ?></span>
      <span class="adm-card-l"><?= e($label) ?></span>
    <?php if ($link): ?></a><?php else: ?></div><?php endif; ?>
  <?php endforeach; ?>
</div>

<div class="adm-two">
  <section class="adm-panel">
    <div class="adm-panel-head"><h2>Recently updated parts</h2><a href="<?= e($_controller->url('/admin/parts')) ?>">All parts</a></div>
    <table class="adm-table">
      <thead><tr><th>Part</th><th>Brand</th><th class="right">Price</th></tr></thead>
      <tbody>
        <?php foreach ($recentParts as $p): ?>
          <tr>
            <td><a href="<?= e($_controller->url('/admin/parts/')) ?>"><?= e($p['name']) ?></a><span class="sub"><?= e($p['sku']) ?></span></td>
            <td><?= e($p['brand'] ?? '—') ?></td>
            <td class="right"><?= money($p['price']) ?></td>
          </tr>
        <?php endforeach; ?>
        <?php if (!$recentParts): ?><tr><td colspan="3" class="muted">No parts yet.</td></tr><?php endif; ?>
      </tbody>
    </table>
  </section>

  <section class="adm-panel">
    <div class="adm-panel-head"><h2>Recent imports</h2><a href="<?= e($_controller->url('/admin/imports')) ?>">Imports</a></div>
    <table class="adm-table">
      <thead><tr><th>Type</th><th>OK</th><th>Failed</th><th>Status</th></tr></thead>
      <tbody>
        <?php foreach ($recentImports as $il): ?>
          <tr>
            <td><?= e($il['type']) ?><span class="sub"><?= e($il['filename'] ?? '') ?></span></td>
            <td><?= (int)$il['rows_ok'] ?></td>
            <td><?= (int)$il['rows_failed'] ?></td>
            <td><span class="badge badge-<?= e($il['status']) ?>"><?= e($il['status']) ?></span></td>
          </tr>
        <?php endforeach; ?>
        <?php if (!$recentImports): ?><tr><td colspan="4" class="muted">No imports logged yet.</td></tr><?php endif; ?>
      </tbody>
    </table>
  </section>
</div>
