<?php /** @var array $categories @var array $parents @var string $csrf @var \App\Core\Controller $_controller */ ?>
<h1 class="adm-h1">Categories <span class="adm-count"><?= count($categories) ?></span></h1>

<form class="adm-inline-add" method="post" action="<?= e($_controller->url('/admin/categories')) ?>">
  <input type="hidden" name="_csrf" value="<?= e($csrf) ?>">
  <input type="text" name="name" placeholder="New category name" required>
  <select name="parent_id">
    <option value="">— top level —</option>
    <?php foreach ($parents as $p): ?>
      <option value="<?= (int)$p['id'] ?>"><?= e($p['slug']) ?></option>
    <?php endforeach; ?>
  </select>
  <input type="number" name="position" value="0" title="Sort position" style="width:70px">
  <button class="btn btn-primary" type="submit">+ Add category</button>
</form>

<table class="adm-table">
  <thead><tr><th>Name</th><th>Parent</th><th>Slug</th><th>Pos</th><th>Parts</th><th>Active</th><th></th></tr></thead>
  <tbody>
    <?php foreach ($categories as $c): $fid = 'cat' . $c['id']; ?>
      <tr>
        <td>
          <form id="<?= $fid ?>" method="post" action="<?= e($_controller->url('/admin/categories/' . $c['id'])) ?>"></form>
          <input type="hidden" name="_csrf" value="<?= e($csrf) ?>" form="<?= $fid ?>">
          <input type="text" name="name" value="<?= e($c['name']) ?>" form="<?= $fid ?>">
        </td>
        <td>
          <select name="parent_id" form="<?= $fid ?>">
            <option value="">—</option>
            <?php foreach ($parents as $p): if ($p['id'] == $c['id']) continue; ?>
              <option value="<?= (int)$p['id'] ?>" <?= $c['parent_id'] == $p['id'] ? 'selected' : '' ?>><?= e($p['slug']) ?></option>
            <?php endforeach; ?>
          </select>
        </td>
        <td class="muted"><?= e($c['slug']) ?></td>
        <td><input type="number" name="position" value="<?= (int)$c['position'] ?>" form="<?= $fid ?>" style="width:56px"></td>
        <td><?= (int)$c['parts'] ?></td>
        <td><input type="checkbox" name="is_active" <?= $c['is_active'] ? 'checked' : '' ?> form="<?= $fid ?>"></td>
        <td class="right nowrap">
          <button class="link" type="submit" form="<?= $fid ?>">Save</button>
          <form method="post" action="<?= e($_controller->url('/admin/categories/' . $c['id'] . '/delete')) ?>"
                onsubmit="return confirm('Delete category <?= e($c['name']) ?>?')" class="inline-form">
            <input type="hidden" name="_csrf" value="<?= e($csrf) ?>">
            <button class="link danger" type="submit">Delete</button>
          </form>
        </td>
      </tr>
    <?php endforeach; ?>
    <?php if (!$categories): ?><tr><td colspan="7" class="muted">No categories yet.</td></tr><?php endif; ?>
  </tbody>
</table>
