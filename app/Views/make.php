<?php /** @var array $make @var array $vehicles @var \App\Core\Controller $_controller */ ?>
<nav class="crumbs">
  <a href="<?= e($_controller->url('/')) ?>">Home</a> &rsaquo;
  <span><?= e($make['name']) ?></span>
</nav>

<h1 class="page-title"><?= e($make['name']) ?> Parts Catalog</h1>

<?php if (!$vehicles): ?>
  <p class="empty">No vehicles loaded for <?= e($make['name']) ?> yet.</p>
<?php else: ?>
  <div class="veh-table-wrap">
    <table class="veh-table">
      <thead><tr><th>Year</th><th>Model</th><th>Engine</th><th></th></tr></thead>
      <tbody>
      <?php foreach ($vehicles as $v): ?>
        <tr>
          <td><?= e((string)$v['year']) ?></td>
          <td><?= e($v['model']) ?><?= $v['trim'] ? ' <span class="muted">'.e($v['trim']).'</span>' : '' ?></td>
          <td><?= e($v['engine']) ?></td>
          <td class="right"><a class="btn btn-sm" href="<?= e($_controller->url('/vehicle/' . $v['slug'])) ?>">View parts &rarr;</a></td>
        </tr>
      <?php endforeach; ?>
      </tbody>
    </table>
  </div>
<?php endif; ?>
