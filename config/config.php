<?php
// Supreme Parts — app + DB config (XAMPP defaults).
// Change db.pass if your MySQL root has a password.
return [
    'app' => [
        'name'      => 'Supreme Parts',
        'base_path' => '/RockAuto',   // URL prefix under htdocs (folder name)
        'env'       => 'local',
        'debug'     => true,
    ],
    'db' => [
        'host'    => '127.0.0.1',
        'port'    => 3307,   // this XAMPP's MariaDB listens on 3307, not the usual 3306
        'name'    => 'supreme_parts',
        'user'    => 'root',
        'pass'    => '',
        'charset' => 'utf8mb4',
    ],
    // Stripe. Paste TEST keys here (or set env SP_STRIPE_SECRET / SP_STRIPE_PUBLISHABLE
    // / SP_STRIPE_WEBHOOK_SECRET). Leave secret blank to run checkout in MOCK mode
    // (order is marked paid without contacting Stripe — for local demos only).
    'stripe' => [
        'secret'         => getenv('SP_STRIPE_SECRET')       ?: '',   // sk_test_...
        'publishable'    => getenv('SP_STRIPE_PUBLISHABLE')  ?: '',   // pk_test_...
        'webhook_secret' => getenv('SP_STRIPE_WEBHOOK_SECRET') ?: '', // whsec_...
        'currency'       => 'usd',
    ],
    // Shipping rule (simple flat rate, free over threshold).
    'shipping' => ['flat' => 9.95, 'free_over' => 75.00],
    // Part images: when 'base' is set, part photos are served from this CDN
    // (Bunny pull zone) instead of local /RockAuto/assets/parts/. Empty = local.
    // Flip to 'https://supremeautos-parts.b-cdn.net' once the mirror upload is done.
    'cdn' => ['base' => getenv('SP_CDN_BASE') ?: 'https://supremeautos-parts.b-cdn.net'],
];
