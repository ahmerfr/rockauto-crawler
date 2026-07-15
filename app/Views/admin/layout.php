<?php
/** @var string $title @var string $content @var array $_user @var string $_active @var ?array $_flash @var \App\Core\Controller $_controller */
$nav = [
  'dashboard'  => ['Dashboard', '/admin'],
  'parts'      => ['Parts', '/admin/parts'],
  'brands'     => ['Brands', '/admin/brands'],
  'categories' => ['Categories', '/admin/categories'],
  'catalog'    => ['Vehicle Catalog', '/admin/catalog'],
  'imports'    => ['Imports', '/admin/imports'],
  'settings'   => ['Pricing', '/admin/settings'],
];
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><?= e($title) ?></title>
  <link rel="stylesheet" href="<?= e($_controller->url('assets/css/app.css')) ?>">
  <link rel="stylesheet" href="<?= e($_controller->url('assets/css/admin.css')) ?>">
  <link rel="icon" href="<?= e($_controller->url('assets/img/favicon.svg')) ?>" type="image/svg+xml">
</head>
<body class="admin">
<header class="adm-top">
  <a class="brand" href="<?= e($_controller->url('/admin')) ?>">
    <svg viewBox="0 0 40 40" width="30" height="30" aria-hidden="true">
      <rect x="1.5" y="1.5" width="37" height="37" rx="7" fill="#0b1e3b"/>
      <path d="M20 6 L32 12 V22 C32 29 27 33 20 35 C13 33 8 29 8 22 V12 Z" fill="#e01f26"/>
      <path d="M20 12.5 l2.4 4.9 5.4 .8 -3.9 3.8 .9 5.4 -4.8-2.5 -4.8 2.5 .9-5.4 -3.9-3.8 5.4-.8 Z" fill="#fff"/>
    </svg>
    <span class="brand-text"><strong>SUPREME</strong><span>ADMIN</span></span>
  </a>
  <div class="adm-top-right">
    <a class="adm-viewsite" href="<?= e($_controller->url('/')) ?>" target="_blank">View store &rarr;</a>
    <span class="adm-user"><?= e($_user['name'] ?? '') ?></span>
    <form method="post" action="<?= e($_controller->url('/admin/logout')) ?>" class="adm-logout">
      <button type="submit">Sign out</button>
    </form>
  </div>
</header>

<div class="adm-shell">
  <nav class="adm-side">
    <?php foreach ($nav as $key => [$label, $path]): ?>
      <a class="<?= $_active === $key ? 'active' : '' ?>" href="<?= e($_controller->url($path)) ?>"><?= e($label) ?></a>
    <?php endforeach; ?>
  </nav>

  <main class="adm-main">
    <?php if ($_flash): ?>
      <div class="flash flash-<?= e($_flash['type']) ?>"><?= e($_flash['msg']) ?></div>
    <?php endif; ?>
    <?= $content ?>
  </main>
</div>
</body>
</html>
