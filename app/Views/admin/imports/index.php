<?php /** @var array $logs @var string $csrf @var bool $canRun @var \App\Core\Controller $_controller */ ?>
<h1 class="adm-h1">Imports</h1>

<?php if (!$canRun): ?>
  <div class="flash flash-error"><code>shell_exec</code> is disabled in PHP — run importers from the CLI (see commands below).</div>
<?php endif; ?>

<div class="adm-two">
  <section class="adm-panel">
    <div class="adm-panel-head"><h2>Vehicle data (NHTSA vPIC)</h2></div>
    <p class="muted">Pulls real makes/models/years. Bounded run below returns quickly; use the CLI for the full catalog.</p>
    <form method="post" action="<?= e($_controller->url('/admin/imports/vpic')) ?>" class="adm-run-form">
      <input type="hidden" name="_csrf" value="<?= e($csrf) ?>">
      <label>Makes <input type="text" name="makes" value="Honda,Toyota" placeholder="Honda,Toyota"></label>
      <label>From <input type="number" name="from" value="2020" style="width:80px"></label>
      <label>To <input type="number" name="to" value="2021" style="width:80px"></label>
      <button class="btn btn-primary" type="submit" <?= $canRun ? '' : 'disabled' ?>>Run vPIC import</button>
    </form>
    <p class="cli">CLI: <code>python bin/import_vpic.py --makes Honda,Toyota --from 2015 --to 2025</code></p>
  </section>

  <section class="adm-panel">
    <div class="adm-panel-head"><h2>Parts (ACES / PIES feed)</h2></div>
    <p class="muted">Loads the sample ACES+PIES feed. Point at your licensed feed files via the CLI.</p>
    <form method="post" action="<?= e($_controller->url('/admin/imports/acespies')) ?>" class="adm-run-form">
      <input type="hidden" name="_csrf" value="<?= e($csrf) ?>">
      <button class="btn btn-primary" type="submit" <?= $canRun ? '' : 'disabled' ?>>Run sample ACES/PIES import</button>
    </form>
    <p class="cli">CLI: <code>python bin/ingest_acespies.py &lt;aces.xml&gt; &lt;pies.xml&gt; scraper/reference</code></p>
  </section>
</div>

<section class="adm-panel">
  <div class="adm-panel-head"><h2>Import history</h2></div>
  <table class="adm-table">
    <thead><tr><th>When</th><th>Type</th><th>File</th><th>Total</th><th>OK</th><th>Failed</th><th>Status</th><th>By</th></tr></thead>
    <tbody>
      <?php foreach ($logs as $il): ?>
        <tr>
          <td class="nowrap"><?= e($il['created_at']) ?></td>
          <td><?= e($il['type']) ?></td>
          <td class="muted"><?= e($il['filename'] ?? '') ?></td>
          <td><?= (int)$il['rows_total'] ?></td>
          <td><?= (int)$il['rows_ok'] ?></td>
          <td><?= (int)$il['rows_failed'] ?></td>
          <td><span class="badge badge-<?= e($il['status']) ?>"><?= e($il['status']) ?></span></td>
          <td><?= e($il['admin_name'] ?? '—') ?></td>
        </tr>
      <?php endforeach; ?>
      <?php if (!$logs): ?><tr><td colspan="8" class="muted">No imports logged yet.</td></tr><?php endif; ?>
    </tbody>
  </table>
</section>
