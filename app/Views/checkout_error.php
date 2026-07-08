<?php /** @var string $message @var \App\Core\Controller $_controller */ ?>
<section class="checkout-result">
  <h1>Checkout problem</h1>
  <p class="subtitle"><?= e($message) ?></p>
  <a class="btn btn-primary" href="<?= e($_controller->url('/cart')) ?>">Back to cart</a>
</section>
