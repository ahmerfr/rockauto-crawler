<?php
/** @var ?array $part @var array $brands @var array $categories @var string $csrf @var \App\Core\Controller $_controller */
$isEdit = $part !== null;
$action = $isEdit ? $_controller->url('/admin/parts/' . $part['id']) : $_controller->url('/admin/parts');
$val = fn(string $k, $d = '') => e((string) ($part[$k] ?? $d));
?>
<div class="adm-head-row">
  <h1 class="adm-h1"><?= $isEdit ? 'Edit part' : 'New part' ?></h1>
  <a class="btn" href="<?= e($_controller->url('/admin/parts')) ?>">&larr; Back</a>
</div>

<form class="adm-form" method="post" action="<?= e($action) ?>">
  <input type="hidden" name="_csrf" value="<?= e($csrf) ?>">
  <div class="adm-form-grid">
    <label class="wide">Name<input type="text" name="name" value="<?= $val('name') ?>" required></label>
    <label>Part number<input type="text" name="part_number" value="<?= $val('part_number') ?>" required></label>
    <label>SKU <span class="hint">(blank = part number)</span><input type="text" name="sku" value="<?= $val('sku') ?>"></label>

    <label>Brand
      <select name="brand_id">
        <option value="">— none —</option>
        <?php foreach ($brands as $b): ?>
          <option value="<?= (int)$b['id'] ?>" <?= ($part['brand_id'] ?? null) == $b['id'] ? 'selected' : '' ?>><?= e($b['name']) ?></option>
        <?php endforeach; ?>
      </select>
    </label>
    <label>Category
      <select name="category_id">
        <option value="">— none —</option>
        <?php foreach ($categories as $c): ?>
          <option value="<?= (int)$c['id'] ?>" <?= ($part['category_id'] ?? null) == $c['id'] ? 'selected' : '' ?>><?= e($c['slug']) ?></option>
        <?php endforeach; ?>
      </select>
    </label>

    <label>Price<input type="number" step="0.01" name="price" value="<?= $val('price', '0') ?>"></label>
    <label>Core charge<input type="number" step="0.01" name="core_charge" value="<?= $val('core_charge', '0') ?>"></label>
    <label>Weight<input type="number" step="0.01" name="weight" value="<?= $val('weight') ?>"></label>
    <label>Status
      <select name="status">
        <?php foreach (['active','inactive','discontinued'] as $s): ?>
          <option value="<?= $s ?>" <?= ($part['status'] ?? 'active') === $s ? 'selected' : '' ?>><?= $s ?></option>
        <?php endforeach; ?>
      </select>
    </label>

    <label class="wide">Primary image URL<input type="text" id="primary_image_path" name="primary_image_path" value="<?= $val('primary_image_path') ?>"></label>
    <?php $imgval = $val('primary_image_path'); ?>
    <div class="adm-img-preview" style="margin:-.25rem 0 .5rem;">
      <img id="primary_image_preview" src="<?= $imgval ?>" alt="Part image preview"
           style="max-width:180px;max-height:180px;object-fit:contain;background:#fff;border:1px solid #e2e2e2;border-radius:6px;padding:4px;<?= $imgval ? '' : 'display:none;' ?>"
           onerror="this.style.display='none';">
    </div>
    <script>
      (function () {
        var inp = document.getElementById('primary_image_path');
        var img = document.getElementById('primary_image_preview');
        if (inp && img) inp.addEventListener('input', function () {
          if (this.value) { img.src = this.value; img.style.display = ''; } else { img.style.display = 'none'; }
        });
      })();
    </script>
    <label class="wide">Description<textarea name="description" rows="4"><?= $val('description') ?></textarea></label>
  </div>
  <div class="adm-form-actions">
    <button class="btn btn-primary" type="submit"><?= $isEdit ? 'Save changes' : 'Create part' ?></button>
    <a class="btn" href="<?= e($_controller->url('/admin/parts')) ?>">Cancel</a>
  </div>
</form>
