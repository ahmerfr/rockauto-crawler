<?php /** @var ?string $error @var string $csrf @var \App\Core\Controller $_controller */ ?>
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
<body class="admin adm-login-body">
  <form class="adm-login" method="post" action="<?= e($_controller->url('/admin/login')) ?>">
    <div class="adm-login-brand">
      <svg viewBox="0 0 40 40" width="42" height="42" aria-hidden="true">
        <rect x="1.5" y="1.5" width="37" height="37" rx="7" fill="#0b1e3b"/>
        <path d="M20 6 L32 12 V22 C32 29 27 33 20 35 C13 33 8 29 8 22 V12 Z" fill="#e01f26"/>
        <path d="M20 12.5 l2.4 4.9 5.4 .8 -3.9 3.8 .9 5.4 -4.8-2.5 -4.8 2.5 .9-5.4 -3.9-3.8 5.4-.8 Z" fill="#fff"/>
      </svg>
      <div class="brand-text"><strong>SUPREME</strong><span>ADMIN</span></div>
    </div>
    <h1>Sign in</h1>
    <?php if ($error): ?><div class="flash flash-error"><?= e($error) ?></div><?php endif; ?>
    <input type="hidden" name="_csrf" value="<?= e($csrf) ?>">
    <label>Email<input type="email" name="email" required autofocus></label>
    <label>Password<input type="password" name="password" required></label>
    <button type="submit" class="btn btn-primary">Sign in</button>
  </form>
</body>
</html>
