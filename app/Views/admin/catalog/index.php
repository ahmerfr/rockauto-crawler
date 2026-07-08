<?php /** @var array $makes @var array $vehicles @var string $q @var \App\Core\Controller $_controller */ ?>
<h1 class="adm-h1">Vehicle Catalog</h1>
<p class="muted">Vehicles are populated by the importers (vPIC / ACES). Manage them via <a href="<?= e($_controller->url('/admin/imports')) ?>">Imports</a>.</p>

<div class="adm-two">
  <section class="adm-panel">
    <div class="adm-panel-head"><h2>Makes</h2></div>
    <table class="adm-table">
      <thead><tr><th>Make</th><th>Models</th><th>Vehicles</th></tr></thead>
      <tbody>
        <?php foreach ($makes as $m): ?>
          <tr>
            <td><a href="<?= e($_controller->url('/make/' . $m['slug'])) ?>" target="_blank"><?= e($m['name']) ?></a></td>
            <td><?= (int)$m['models'] ?></td>
            <td><?= (int)$m['vehicles'] ?></td>
          </tr>
        <?php endforeach; ?>
        <?php if (!$makes): ?><tr><td colspan="3" class="muted">No makes yet — run an import.</td></tr><?php endif; ?>
      </tbody>
    </table>
  </section>

  <section class="adm-panel">
    <div class="adm-panel-head"><h2>Find a vehicle</h2></div>
    <form class="adm-search" method="get" action="<?= e($_controller->url('/admin/catalog')) ?>">
      <input type="search" name="q" value="<?= e($q) ?>" placeholder="Make, model, or slug&hellip;">
      <button class="btn" type="submit">Search</button>
    </form>
    <?php if ($q !== ''): ?>
      <table class="adm-table">
        <thead><tr><th>Year</th><th>Make</th><th>Model</th><th>Engine</th><th></th></tr></thead>
        <tbody>
          <?php foreach ($vehicles as $v): ?>
            <tr>
              <td><?= e((string)$v['year']) ?></td>
              <td><?= e($v['make']) ?></td>
              <td><?= e($v['model']) ?><?= $v['trim'] ? ' <span class="muted">'.e($v['trim']).'</span>' : '' ?></td>
              <td><?= e($v['engine']) ?></td>
              <td class="right"><a class="link" href="<?= e($_controller->url('/vehicle/' . $v['slug'])) ?>" target="_blank">View &rarr;</a></td>
            </tr>
          <?php endforeach; ?>
          <?php if (!$vehicles): ?><tr><td colspan="5" class="muted">No matches.</td></tr><?php endif; ?>
        </tbody>
      </table>
    <?php endif; ?>
  </section>
</div>
