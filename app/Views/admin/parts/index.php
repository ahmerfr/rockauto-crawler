<?php
/** @var array $parts @var string $q @var int $page @var int $total @var int $perPage @var \App\Core\Controller $_controller */
$pages = (int) ceil($total / max(1, $perPage));
?>
<div class="adm-head-row">
  <h1 class="adm-h1">Parts <span class="adm-count"><?= number_format($total) ?></span></h1>
  <a class="btn btn-primary" href="<?= e($_controller->url('/admin/parts/create')) ?>">+ New part</a>
</div>

<form class="adm-search" method="get" action="<?= e($_controller->url('/admin/parts')) ?>">
  <input type="search" name="q" value="<?= e($q) ?>" placeholder="Search name, part number, SKU&hellip;">
  <button class="btn" type="submit">Search</button>
  <?php if ($q !== ''): ?><a class="btn" href="<?= e($_controller->url('/admin/parts')) ?>">Clear</a><?php endif; ?>
</form>

<table class="adm-table">
  <thead><tr><th></th><th>Part</th><th>Brand</th><th>Category</th><th class="right">Price</th><th>Fits</th><th>Status</th><th></th></tr></thead>
  <tbody>
    <?php foreach ($parts as $p): ?>
      <tr>
        <td class="adm-thumb-cell">
          <?php if (!empty($p['primary_image_path'])): ?>
            <img src="<?= e($p['primary_image_path']) ?>" alt="" loading="lazy"
                 style="width:44px;height:44px;object-fit:contain;background:#fff;border:1px solid #e2e2e2;border-radius:4px;"
                 onerror="this.style.visibility='hidden'">
          <?php else: ?>
            <span class="muted" style="display:inline-block;width:44px;text-align:center;">—</span>
          <?php endif; ?>
        </td>
        <td><a href="<?= e($_controller->url('/admin/parts/' . $p['id'] . '/edit')) ?>"><?= e($p['name']) ?></a>
            <span class="sub">#<?= e($p['part_number']) ?> · <?= e($p['sku']) ?></span></td>
        <td><?= e($p['brand'] ?? '—') ?></td>
        <td><?= e($p['category'] ?? '—') ?></td>
        <td class="right"><?= money($p['price']) ?></td>
        <td><?= (int)$p['fits'] ?></td>
        <td><span class="badge badge-<?= e($p['status']) ?>"><?= e($p['status']) ?></span></td>
        <td class="right nowrap">
          <a class="link" href="<?= e($_controller->url('/admin/parts/' . $p['id'] . '/edit')) ?>">Edit</a>
          <form method="post" action="<?= e($_controller->url('/admin/parts/' . $p['id'] . '/delete')) ?>"
                onsubmit="return confirm('Delete this part?')" class="inline-form">
            <input type="hidden" name="_csrf" value="<?= e(\App\Core\Auth::token()) ?>">
            <button class="link danger" type="submit">Delete</button>
          </form>
        </td>
      </tr>
    <?php endforeach; ?>
    <?php if (!$parts): ?><tr><td colspan="8" class="muted">No parts found.</td></tr><?php endif; ?>
  </tbody>
</table>

<?php if ($pages > 1): ?>
<div class="adm-pager">
  <?php for ($i = 1; $i <= $pages; $i++): ?>
    <a class="<?= $i === $page ? 'active' : '' ?>"
       href="<?= e($_controller->url('/admin/parts?page=' . $i . ($q !== '' ? '&q=' . urlencode($q) : ''))) ?>"><?= $i ?></a>
  <?php endfor; ?>
</div>
<?php endif; ?>
