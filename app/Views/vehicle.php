<?php
/** @var array $vehicle @var array $categories @var \App\Core\Controller $_controller */
$label = trim($vehicle['year'] . ' ' . $vehicle['make'] . ' ' . $vehicle['model']
    . ($vehicle['engine'] ? ' ' . $vehicle['engine'] : '')
    . ($vehicle['trim'] ? ' ' . $vehicle['trim'] : ''));
?>
<nav class="crumbs">
  <a href="<?= e($_controller->url('/')) ?>">Home</a> &rsaquo;
  <a href="<?= e($_controller->url('/make/' . $vehicle['make_slug'])) ?>"><?= e($vehicle['make']) ?></a> &rsaquo;
  <span><?= e($vehicle['model']) ?></span>
</nav>

<h1 class="page-title"><?= e($label) ?></h1>
<p class="subtitle">Select a category to see parts that fit this vehicle.</p>

<?php if (!$categories): ?>
  <p class="empty">No parts are loaded for this vehicle yet. Load an ACES/PIES feed to populate fitment.</p>
<?php else: ?>
  <?php
    // Group leaf part-types under their RockAuto parent group ("Wiper & Washer"...).
    $groups = [];
    foreach ($categories as $c) { $groups[$c['group_name']][] = $c; }
  ?>
  <?php foreach ($groups as $gname => $cats): ?>
    <section class="cat-group">
      <h2 class="cat-group-title"><?= e($gname) ?></h2>
      <div class="cat-grid">
        <?php foreach ($cats as $c): ?>
          <a class="cat-card" href="<?= e($_controller->url('/vehicle/' . $vehicle['slug'] . '/c/' . $c['slug'])) ?>">
            <span class="cat-name"><?= e($c['name']) ?></span>
            <span class="cat-count"><?= (int)$c['n'] ?> part<?= $c['n'] == 1 ? '' : 's' ?></span>
          </a>
        <?php endforeach; ?>
      </div>
    </section>
  <?php endforeach; ?>
<?php endif; ?>
