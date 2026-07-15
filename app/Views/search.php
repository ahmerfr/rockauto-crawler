<?php /** @var string $q @var array $parts @var \App\Core\Controller $_controller */ ?>
<nav class="crumbs">
  <a href="<?= e($_controller->url('/')) ?>">Home</a> &rsaquo; <span>Search</span>
</nav>

<h1 class="page-title">Search<?= $q !== '' ? ': &ldquo;' . e($q) . '&rdquo;' : '' ?></h1>

<?php if ($q === ''): ?>
  <p class="subtitle">Enter a part number, name, or brand in the search box above.</p>
<?php elseif (!$parts): ?>
  <p class="empty">No parts matched &ldquo;<?= e($q) ?>&rdquo;.</p>
<?php else: ?>
  <p class="subtitle"><?= count($parts) ?> result<?= count($parts) == 1 ? '' : 's' ?></p>
  <div class="part-list">
    <?php foreach ($parts as $p): ?>
      <article class="part-row">
        <div class="part-thumb">
          <?php if (!empty($p['primary_image_path'])): ?>
            <img src="<?= e(img_url($p['primary_image_path'])) ?>" alt="<?= e($p['name']) ?>" loading="lazy"
                 onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'noimg',textContent:'No image'}))">
          <?php else: ?><div class="noimg">No image</div><?php endif; ?>
        </div>
        <div class="part-main">
          <?php if (!empty($p['brand'])): ?><span class="part-brand"><?= e($p['brand']) ?></span><?php endif; ?>
          <a class="part-name" href="<?= e($_controller->url('/part/' . rawurlencode($p['sku']))) ?>"><?= e($p['name']) ?></a>
          <div class="part-meta">
            <span class="pn">Part #<?= e($p['part_number']) ?></span>
            <span class="fit-note"><?= (int)$p['fits'] ?> vehicle<?= $p['fits'] == 1 ? '' : 's' ?></span>
          </div>
        </div>
        <div class="part-buy">
          <div class="price"><?= price_tag($p['price']) ?></div>
          <a class="btn btn-sm" href="<?= e($_controller->url('/part/' . rawurlencode($p['sku']))) ?>">View</a>
        </div>
      </article>
    <?php endforeach; ?>
  </div>
<?php endif; ?>
