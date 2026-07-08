<?php /** @var array $brands @var string $csrf @var \App\Core\Controller $_controller */ ?>
<h1 class="adm-h1">Brands <span class="adm-count"><?= count($brands) ?></span></h1>

<form class="adm-inline-add" method="post" action="<?= e($_controller->url('/admin/brands')) ?>">
  <input type="hidden" name="_csrf" value="<?= e($csrf) ?>">
  <input type="text" name="name" placeholder="New brand name" required>
  <button class="btn btn-primary" type="submit">+ Add brand</button>
</form>

<table class="adm-table">
  <thead><tr><th>Name</th><th>Slug</th><th>Parts</th><th>Active</th><th></th></tr></thead>
  <tbody>
    <?php foreach ($brands as $b): $fid = 'brand' . $b['id']; ?>
      <tr>
        <td>
          <form id="<?= $fid ?>" method="post" action="<?= e($_controller->url('/admin/brands/' . $b['id'])) ?>"></form>
          <input type="hidden" name="_csrf" value="<?= e($csrf) ?>" form="<?= $fid ?>">
          <input type="text" name="name" value="<?= e($b['name']) ?>" form="<?= $fid ?>">
        </td>
        <td class="muted"><?= e($b['slug']) ?></td>
        <td><?= (int)$b['parts'] ?></td>
        <td><input type="checkbox" name="is_active" <?= $b['is_active'] ? 'checked' : '' ?> form="<?= $fid ?>"></td>
        <td class="right nowrap">
          <button class="link" type="submit" form="<?= $fid ?>">Save</button>
          <form method="post" action="<?= e($_controller->url('/admin/brands/' . $b['id'] . '/delete')) ?>"
                onsubmit="return confirm('Delete brand <?= e($b['name']) ?>?')" class="inline-form">
            <input type="hidden" name="_csrf" value="<?= e($csrf) ?>">
            <button class="link danger" type="submit">Delete</button>
          </form>
        </td>
      </tr>
    <?php endforeach; ?>
    <?php if (!$brands): ?><tr><td colspan="5" class="muted">No brands yet.</td></tr><?php endif; ?>
  </tbody>
</table>
