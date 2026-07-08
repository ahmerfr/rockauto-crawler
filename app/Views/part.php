<?php /** @var array $part @var array $images @var array $attrs @var array $fitment @var int $stock @var \App\Core\Controller $_controller */ ?>
<nav class="crumbs">
  <a href="<?= e($_controller->url('/')) ?>">Home</a> &rsaquo;
  <?php if (!empty($part['category'])): ?><span><?= e($part['category']) ?></span> &rsaquo;<?php endif; ?>
  <span><?= e($part['part_number']) ?></span>
</nav>

<div class="part-detail">
  <div class="pd-gallery">
    <?php $main = $images[0]['path'] ?? $part['primary_image_path'] ?? ''; ?>
    <div class="pd-main-img">
      <?php if ($main): ?>
        <img src="<?= e($main) ?>" alt="<?= e($part['name']) ?>"
             onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'noimg lg',textContent:'No image'}))">
      <?php else: ?><div class="noimg lg">No image</div><?php endif; ?>
    </div>
    <?php if (count($images) > 1): ?>
      <div class="pd-thumbs">
        <?php foreach ($images as $img): ?>
          <img src="<?= e($img['path']) ?>" alt="<?= e($img['alt'] ?? '') ?>" loading="lazy"
               onerror="this.style.display='none'">
        <?php endforeach; ?>
      </div>
    <?php endif; ?>
  </div>

  <div class="pd-info">
    <?php if (!empty($part['brand'])): ?><div class="pd-brand"><?= e($part['brand']) ?></div><?php endif; ?>
    <h1 class="pd-name"><?= e($part['name']) ?></h1>
    <div class="pd-pn">Part&nbsp;#<strong><?= e($part['part_number']) ?></strong> &nbsp;·&nbsp; SKU <?= e($part['sku']) ?></div>

    <?php if (!empty($part['description'])): ?>
      <p class="pd-desc"><?= e($part['description']) ?></p>
    <?php endif; ?>

    <div class="pd-buybox">
      <div class="pd-price"><?= money($part['price']) ?>
        <?php if ((float)$part['core_charge'] > 0): ?><span class="core">+<?= money($part['core_charge']) ?> core</span><?php endif; ?>
      </div>
      <div class="pd-stock <?= $stock > 0 ? 'in' : 'out' ?>">
        <?= $stock > 0 ? 'In stock (' . (int)$stock . ')' : 'Backordered' ?>
      </div>
      <form method="post" action="<?= e($_controller->url('/cart/add')) ?>">
        <input type="hidden" name="sku" value="<?= e($part['sku']) ?>">
        <button class="btn btn-primary" type="submit">Add to cart</button>
      </form>
    </div>

    <?php if ($attrs): ?>
      <h3 class="pd-sub">Specifications</h3>
      <table class="spec-table">
        <?php foreach ($attrs as $a): ?>
          <tr><th><?= e($a['name']) ?></th><td><?= e($a['value']) ?></td></tr>
        <?php endforeach; ?>
      </table>
    <?php endif; ?>
  </div>
</div>

<section class="block">
  <h2 class="block-title">Fits these vehicles <span class="count">(<?= count($fitment) ?>)</span></h2>
  <?php if (!$fitment): ?>
    <p class="empty">No fitment data for this part yet.</p>
  <?php else: ?>
    <div class="veh-table-wrap">
      <table class="veh-table">
        <thead><tr><th>Year</th><th>Make</th><th>Model</th><th>Engine</th><th>Notes</th><th></th></tr></thead>
        <tbody>
        <?php foreach ($fitment as $f): ?>
          <tr>
            <td><?= e((string)$f['year']) ?></td>
            <td><?= e($f['make']) ?></td>
            <td><?= e($f['model']) ?><?= $f['trim'] ? ' <span class="muted">'.e($f['trim']).'</span>' : '' ?></td>
            <td><?= e($f['engine']) ?></td>
            <td><?= e($f['note'] ?? '') ?></td>
            <td class="right"><a class="link" href="<?= e($_controller->url('/vehicle/' . $f['slug'])) ?>">Parts &rarr;</a></td>
          </tr>
        <?php endforeach; ?>
        </tbody>
      </table>
    </div>
  <?php endif; ?>
</section>
