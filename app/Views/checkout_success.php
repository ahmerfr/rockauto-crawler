<?php /** @var array $order @var array $items @var \App\Core\Controller $_controller */ ?>
<section class="checkout-result ok">
  <div class="cr-badge">✓</div>
  <h1>Order confirmed</h1>
  <p class="subtitle">Thank you! Your order <strong><?= e($order['order_number']) ?></strong> has been placed.</p>

  <div class="order-card">
    <div class="order-lines">
      <?php foreach ($items as $it): ?>
        <div class="order-line">
          <span class="ol-name"><?= e($it['name']) ?> <span class="muted">&times;<?= (int)$it['quantity'] ?></span></span>
          <span class="ol-price"><?= money($it['line_total']) ?></span>
        </div>
      <?php endforeach; ?>
    </div>
    <div class="order-totals">
      <div class="row"><span>Subtotal</span><span><?= money($order['subtotal']) ?></span></div>
      <div class="row"><span>Shipping</span><span><?= $order['shipping_total'] > 0 ? money($order['shipping_total']) : 'FREE' ?></span></div>
      <div class="row total"><span>Total paid</span><span><?= money($order['grand_total']) ?></span></div>
    </div>
  </div>

  <?php if (($order['email'] ?? '') !== ''): ?>
    <p class="muted">A confirmation was sent to <?= e($order['email']) ?>.</p>
  <?php endif; ?>
  <a class="btn btn-primary" href="<?= e($_controller->url('/')) ?>">Continue shopping</a>
</section>
