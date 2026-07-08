<?php
/** @var array $vehicle @var array $category @var array $parts @var \App\Core\Controller $_controller */
$label = trim($vehicle['year'] . ' ' . $vehicle['make'] . ' ' . $vehicle['model']
    . ($vehicle['engine'] ? ' ' . $vehicle['engine'] : ''));
?>
<nav class="crumbs">
  <a href="<?= e($_controller->url('/')) ?>">Home</a> &rsaquo;
  <a href="<?= e($_controller->url('/make/' . $vehicle['make_slug'])) ?>"><?= e($vehicle['make']) ?></a> &rsaquo;
  <a href="<?= e($_controller->url('/vehicle/' . $vehicle['slug'])) ?>"><?= e($vehicle['model']) ?></a> &rsaquo;
  <span><?= e($category['name']) ?></span>
</nav>

<h1 class="page-title"><?= e($category['name']) ?></h1>
<p class="subtitle">For <?= e($label) ?> &mdash; <?= count($parts) ?> part<?= count($parts) == 1 ? '' : 's' ?></p>

<div class="part-list">
  <?php foreach ($parts as $p): ?>
    <article class="part-row">
      <div class="part-thumb">
        <?php if (!empty($p['primary_image_path'])): ?>
          <img src="<?= e($p['primary_image_path']) ?>" alt="<?= e($p['name']) ?>" loading="lazy"
               onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'noimg',textContent:'No image'}))">
        <?php else: ?>
          <div class="noimg">No image</div>
        <?php endif; ?>
      </div>
      <div class="part-main">
        <?php if (!empty($p['brand'])): ?><span class="part-brand"><?= e($p['brand']) ?></span><?php endif; ?>
        <a class="part-name" href="<?= e($_controller->url('/part/' . rawurlencode($p['sku']))) ?>"><?= e($p['name']) ?></a>
        <div class="part-meta">
          <span class="pn">Part #<?= e($p['part_number']) ?></span>
          <?php if (!empty($p['note'])): ?><span class="fit-note"><?= e($p['note']) ?></span><?php endif; ?>
        </div>
      </div>
      <div class="part-buy">
        <div class="price"><?= money($p['price']) ?></div>
        <?php if ((float)$p['core_charge'] > 0): ?>
          <div class="core">+<?= money($p['core_charge']) ?> core</div>
        <?php endif; ?>
        <form method="post" action="<?= e($_controller->url('/cart/add')) ?>">
          <input type="hidden" name="sku" value="<?= e($p['sku']) ?>">
          <button class="btn btn-primary btn-sm" type="submit">Add to cart</button>
        </form>
      </div>
    </article>
  <?php endforeach; ?>
</div>
