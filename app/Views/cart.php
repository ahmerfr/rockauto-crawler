<?php /** @var array $items @var array $totals @var \App\Core\Controller $_controller */ ?>
<nav class="crumbs"><a href="<?= e($_controller->url('/')) ?>">Home</a> &rsaquo; <span>Cart</span></nav>
<h1 class="page-title">Your Cart</h1>

<?php if (!$items): ?>
  <p class="empty">Your cart is empty. <a href="<?= e($_controller->url('/')) ?>">Browse the catalog &rarr;</a></p>
<?php else: ?>
<div class="cart-wrap">
  <div class="cart-lines">
    <?php foreach ($items as $it): ?>
      <div class="cart-line">
        <div class="part-thumb">
          <?php if (!empty($it['primary_image_path'])): ?>
            <img src="<?= e($it['primary_image_path']) ?>" alt="<?= e($it['name']) ?>"
                 onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'noimg',textContent:'No image'}))">
          <?php else: ?><div class="noimg">No image</div><?php endif; ?>
        </div>
        <div class="cart-line-main">
          <?php if (!empty($it['brand'])): ?><span class="part-brand"><?= e($it['brand']) ?></span><?php endif; ?>
          <a class="part-name" href="<?= e($_controller->url('/part/' . rawurlencode($it['sku']))) ?>"><?= e($it['name']) ?></a>
          <div class="part-meta"><span class="pn">Part #<?= e($it['part_number']) ?></span></div>
        </div>
        <form class="cart-qty" method="post" action="<?= e($_controller->url('/cart/update')) ?>">
          <input type="hidden" name="part_id" value="<?= (int)$it['part_id'] ?>">
          <input type="number" name="qty" value="<?= (int)$it['quantity'] ?>" min="0" aria-label="Quantity">
          <button class="link" type="submit">Update</button>
        </form>
        <div class="cart-line-price"><?= money($it['line_total']) ?><span class="unit"><?= money($it['unit_price']) ?> ea</span></div>
        <form method="post" action="<?= e($_controller->url('/cart/remove')) ?>" class="cart-remove">
          <input type="hidden" name="part_id" value="<?= (int)$it['part_id'] ?>">
          <button class="link danger" type="submit" title="Remove">&times;</button>
        </form>
      </div>
    <?php endforeach; ?>
  </div>

  <aside class="cart-summary">
    <h2>Summary</h2>
    <div class="row"><span>Subtotal</span><span><?= money($totals['subtotal']) ?></span></div>
    <div class="row"><span>Shipping</span><span><?= $totals['shipping'] > 0 ? money($totals['shipping']) : 'FREE' ?></span></div>
    <div class="row total"><span>Total</span><span><?= money($totals['grand']) ?></span></div>
    <form method="post" action="<?= e($_controller->url('/checkout')) ?>">
      <button class="btn btn-primary btn-block" type="submit">Checkout &rarr;</button>
    </form>
    <p class="secure-note">🔒 Secure checkout via Stripe</p>
  </aside>
</div>
<?php endif; ?>
