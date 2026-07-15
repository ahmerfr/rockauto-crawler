<?php /** @var string $markup @var string $csrf @var \App\Core\Controller $_controller */ ?>
<h1 class="adm-h1">Pricing</h1>

<div class="adm-card" style="max-width:560px">
  <p class="muted" style="margin-top:0">
    Every customer-facing price is your RockAuto cost multiplied by this markup.
    Costs stay stored as-is; only the displayed and charged price changes. Refundable
    core deposits are never marked up.
  </p>

  <form method="post" action="<?= e($_controller->url('/admin/settings')) ?>" class="adm-form">
    <input type="hidden" name="_csrf" value="<?= e($csrf) ?>">
    <label class="adm-field">
      <span>Reseller markup</span>
      <span class="adm-inline">
        <input type="number" name="markup_pct" value="<?= e($markup) ?>"
               min="0" max="100000" step="0.01" inputmode="decimal"
               style="width:130px" oninput="rmPreview(this.value)"> %
      </span>
    </label>
    <p class="muted" id="rmPreview" style="margin:.25rem 0 1rem">&nbsp;</p>
    <button class="btn btn-primary" type="submit">Save markup</button>
  </form>
</div>

<script>
  function rmPreview(v){
    var pct = parseFloat(v); if (isNaN(pct) || pct < 0) pct = 0;
    var f = 1 + pct/100;
    var ex = [10, 49.99, 250];
    document.getElementById('rmPreview').textContent =
      'Example: ' + ex.map(function(c){
        return '$' + c.toFixed(2) + ' cost → $' + (c*f).toFixed(2);
      }).join('  ·  ');
  }
  rmPreview(document.querySelector('[name=markup_pct]').value);
</script>
