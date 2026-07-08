<?php /** @var array $makes @var array $stats @var array $letters @var \App\Core\Controller $_controller */ ?>

<div class="catalog-tabs">
  <a class="tab active" href="<?= e($_controller->url('/')) ?>">Part Catalog</a>
  <a class="tab" href="<?= e($_controller->url('/search')) ?>">Part Number Search</a>
  <a class="tab" href="#">Tools &amp; Universal Parts</a>
  <a class="tab tab-cart" href="#">Cart</a>
</div>

<div class="catalog-layout">
  <div class="catalog-main">
    <p class="catalog-intro">
      Click a <strong>make</strong> to choose your vehicle and see parts that fit.
      All prices are for in-stock parts.
    </p>

    <?php if ($letters): ?>
    <div class="az-index" id="azIndex">
      <?php foreach (range('A', 'Z') as $L): $has = in_array($L, $letters, true); ?>
        <button type="button" class="az<?= $has ? '' : ' az-off' ?>" data-letter="<?= $L ?>" <?= $has ? '' : 'disabled' ?>><?= $L ?></button>
      <?php endforeach; ?>
      <button type="button" class="az az-all" data-letter="">All</button>
    </div>
    <?php endif; ?>

    <?php if (!$makes): ?>
      <p class="empty">No vehicles loaded yet. Run <code>python bin/import_vpic.py</code> to populate the catalog.</p>
    <?php else: ?>
      <ul class="tree" id="catalogTree" data-api="<?= e($_controller->url('/api/tree')) ?>"
          data-veh="<?= e($_controller->url('/vehicle')) ?>"
          data-part="<?= e($_controller->url('/part')) ?>"
          data-cart="<?= e($_controller->url('/cart/add')) ?>">
        <?php foreach ($makes as $m): $L = strtoupper($m['name'][0] ?? ''); ?>
          <li class="node node-make" data-level="make" data-make="<?= e($m['slug']) ?>" data-letter="<?= e($L) ?>">
            <div class="node-row">
              <button class="toggle" aria-label="Expand"><span class="tw">+</span></button>
              <span class="node-label"><?= e($m['name']) ?></span>
              <span class="node-count"><?= number_format((int)$m['vehicles']) ?></span>
            </div>
            <ul class="children" hidden></ul>
          </li>
        <?php endforeach; ?>
      </ul>
    <?php endif; ?>
  </div>

  <aside class="catalog-aside">
    <div class="aside-card">
      <h3>Catalog</h3>
      <ul class="aside-stats">
        <li><span><?= number_format((int)$stats['makes']) ?></span> makes</li>
        <li><span><?= number_format((int)$stats['vehicles']) ?></span> vehicles</li>
        <li><span><?= number_format((int)$stats['parts']) ?></span> parts</li>
        <li><span><?= number_format((int)$stats['fitments']) ?></span> fitments</li>
      </ul>
    </div>
    <div class="aside-card aside-note">
      <h3>Fitment guaranteed</h3>
      <p>Every part shown is matched to your exact vehicle by ACES fitment data &mdash; no guessing.</p>
    </div>
  </aside>
</div>
