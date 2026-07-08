<?php /** @var \App\Core\Controller $_controller */ ?>
<section class="checkout-result">
  <h1>Checkout cancelled</h1>
  <p class="subtitle">No charge was made. Your cart is still saved.</p>
  <a class="btn btn-primary" href="<?= e($_controller->url('/cart')) ?>">Back to cart</a>
  <a class="btn" href="<?= e($_controller->url('/')) ?>">Keep shopping</a>
</section>
