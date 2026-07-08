<?php /** @var string $title @var string $content @var \App\Core\Controller $_controller */ ?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><?= e($title) ?></title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="stylesheet" href="<?= e($_controller->url('assets/css/app.css')) ?>">
  <link rel="icon" href="<?= e($_controller->url('assets/img/favicon.svg')) ?>" type="image/svg+xml">
</head>
<body>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="<?= e($_controller->url('/')) ?>" aria-label="Supreme Parts home">
      <svg class="brand-mark" viewBox="0 0 40 40" width="38" height="38" aria-hidden="true">
        <rect x="1.5" y="1.5" width="37" height="37" rx="7" fill="#0b1e3b"/>
        <path d="M20 6 L32 12 V22 C32 29 27 33 20 35 C13 33 8 29 8 22 V12 Z" fill="#e01f26"/>
        <path d="M20 12.5 l2.4 4.9 5.4 .8 -3.9 3.8 .9 5.4 -4.8-2.5 -4.8 2.5 .9-5.4 -3.9-3.8 5.4-.8 Z" fill="#fff"/>
      </svg>
      <span class="brand-text"><strong>SUPREME</strong><span>PARTS</span></span>
    </a>

    <form class="search" action="<?= e($_controller->url('/search')) ?>" method="get" role="search">
      <input type="search" name="q" placeholder="Search part number, name, or brand&hellip;"
             value="<?= e($q ?? '') ?>" aria-label="Search parts">
      <button type="submit" aria-label="Search">
        <svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M10 2a8 8 0 105.3 14l5.4 5.4 1.4-1.4-5.4-5.4A8 8 0 0010 2zm0 2a6 6 0 110 12 6 6 0 010-12z"/></svg>
      </button>
    </form>

    <nav class="header-nav">
      <a href="<?= e($_controller->url('/')) ?>">Vehicle&nbsp;Catalog</a>
      <?php $cartN = \App\Core\Cart::headerCount(); ?>
      <a class="cart" href="<?= e($_controller->url('/cart')) ?>" aria-label="Cart">
        Cart<?php if ($cartN > 0): ?> <span class="cart-badge"><?= $cartN ?></span><?php endif; ?>
      </a>
    </nav>
  </div>
</header>

<main class="wrap main">
  <?= $content ?>
</main>

<footer class="site-footer">
  <div class="wrap footer-inner">
    <div>
      <span class="brand-text foot"><strong>SUPREME</strong><span>PARTS</span></span>
      <p>Auto parts catalog. Fitment data via licensed ACES/PIES feeds &amp; NHTSA vPIC.</p>
    </div>
    <p class="muted">&copy; <?= date('Y') ?> Supreme Parts. Demo build.</p>
  </div>
</footer>
<script src="<?= e($_controller->url('assets/js/app.js')) ?>" defer></script>
</body>
</html>
