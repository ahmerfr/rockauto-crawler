<?php /** @var string $title @var string $content @var \App\Core\Controller $_controller */
$url = fn(string $p) => e($_controller->url($p));
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><?= e($title) ?></title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
  <?php $cssv = @filemtime(dirname(__DIR__, 2) . '/assets/css/app.css') ?: date('YmdHis'); ?>
  <link rel="stylesheet" href="<?= $url('assets/css/app.css') ?>?v=<?= $cssv ?>">
  <link rel="icon" href="<?= $url('assets/img/favicon.svg') ?>" type="image/svg+xml">
</head>
<body>
<div class="util"><div class="wrap">
  <span class="hidem usp"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M4 13a8 8 0 0 1 16 0M8 21a4 4 0 0 1-4-4v-3M20 14v3a4 4 0 0 1-4 4"/></svg>Need help finding a part?</span>
  <a class="hidem" href="tel:+18005550110"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M5 4h4l2 5-3 2a12 12 0 0 0 5 5l2-3 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/></svg><span class="accent">1-800-555-0110</span></a>
  <a class="hidem" href="mailto:parts@supremeautos.com"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></svg>parts@supremeautos.com</a>
  <span class="sp"></span>
  <span class="hidem usp"><svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M3 7h11v8H3zM14 10h4l3 3v2h-7z"/><circle cx="7.5" cy="18" r="1.5"/><circle cx="17.5" cy="18" r="1.5"/></svg>Free shipping over $99</span>
  <a href="<?= $url('/') ?>">Track Order</a>
</div></div>

<header class="site-header" id="hdr">
  <div class="wrap header-inner">
    <a class="brand" href="<?= $url('/') ?>" aria-label="Supreme Autos home">
      <svg class="mk" viewBox="0 0 40 40" fill="none" aria-hidden="true"><rect width="40" height="40" rx="10" fill="#0B1E3B"/><path d="M11 26c1-6 4-9 7-9h4c3 0 6 3 7 9" stroke="#fff" stroke-width="2.3" stroke-linecap="round"/><path d="M20 8l3 5h-6l3-5Z" fill="#E01F26"/><circle cx="15" cy="27" r="3.4" fill="#fff"/><circle cx="25" cy="27" r="3.4" fill="#fff"/><circle cx="15" cy="27" r="1.4" fill="#0B1E3B"/><circle cx="25" cy="27" r="1.4" fill="#0B1E3B"/></svg>
      <span class="brand-text"><strong>SUPREME AUTOS</strong><span>QUALITY VEHICLE PARTS</span></span>
    </a>

    <form class="search" action="<?= $url('/search') ?>" method="get" role="search">
      <input type="search" name="q" placeholder="Search part number, name, or brand&hellip;"
             value="<?= e($q ?? '') ?>" aria-label="Search parts">
      <button type="submit" aria-label="Search">
        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m21 21-4-4"/></svg>
      </button>
    </form>

    <nav class="header-nav">
      <a href="<?= $url('/') ?>">Vehicle&nbsp;Catalog</a>
      <?php $cartN = \App\Core\Cart::headerCount(); ?>
      <a class="cart" href="<?= $url('/cart') ?>" aria-label="Cart">
        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" viewBox="0 0 24 24"><path d="M6 6h15l-1.6 9H7.5z"/><circle cx="9.5" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M6 6 5 3H2"/></svg>
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
    <div class="fbrand">
      <a class="brand" href="<?= $url('/') ?>">
        <svg class="mk" viewBox="0 0 40 40" fill="none" aria-hidden="true"><rect width="40" height="40" rx="10" fill="#E01F26"/><path d="M11 26c1-6 4-9 7-9h4c3 0 6 3 7 9" stroke="#fff" stroke-width="2.3" stroke-linecap="round"/><path d="M20 8l3 5h-6l3-5Z" fill="#0B1E3B"/><circle cx="15" cy="27" r="3.4" fill="#fff"/><circle cx="25" cy="27" r="3.4" fill="#fff"/></svg>
        <span class="brand-text"><strong>SUPREME AUTOS</strong><span>QUALITY VEHICLE PARTS</span></span>
      </a>
      <p>Quality replacement and performance parts matched to your exact vehicle. Trusted by DIYers and professional shops nationwide.</p>
    </div>
    <div><h5>Shop</h5><ul>
      <li><a href="<?= $url('/') ?>">Vehicle Catalog</a></li>
      <li><a href="<?= $url('/search?q=brake') ?>">Brakes</a></li>
      <li><a href="<?= $url('/search?q=filter') ?>">Filters</a></li>
      <li><a href="<?= $url('/search?q=wiper') ?>">Wiper Blades</a></li>
    </ul></div>
    <div><h5>Customer Service</h5><ul>
      <li><a href="<?= $url('/') ?>">Contact Us</a></li>
      <li><a href="<?= $url('/') ?>">Shipping Info</a></li>
      <li><a href="<?= $url('/') ?>">Returns</a></li>
      <li><a href="<?= $url('/') ?>">Warranty</a></li>
    </ul></div>
    <div><h5>Company</h5><ul>
      <li><a href="<?= $url('/') ?>">About Us</a></li>
      <li><a href="<?= $url('/') ?>">Our Brands</a></li>
      <li><a href="<?= $url('/') ?>">Privacy Policy</a></li>
      <li><a href="<?= $url('/') ?>">Terms</a></li>
    </ul></div>
  </div>
  <div class="footer-base"><div class="wrap">
    <span>&copy; <?= date('Y') ?> Supreme Autos. Fitment data via licensed ACES/PIES feeds &amp; NHTSA vPIC.</span>
    <span class="sp"></span>
    <div class="fpay"><span>VISA</span><span>MC</span><span>AMEX</span><span>PAYPAL</span></div>
  </div></div>
</footer>
<script>
  // subtle shadow on the sticky header once scrolled, matching the homepage
  (function(){var h=document.getElementById('hdr');if(!h)return;
   var f=function(){h.classList.toggle('stuck',window.scrollY>8)};f();
   window.addEventListener('scroll',f,{passive:true});})();
</script>
<script src="<?= $url('assets/js/app.js') ?>" defer></script>
</body>
</html>
