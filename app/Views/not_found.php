<?php /** @var \App\Core\Controller $_controller */ ?>
<section class="notfound">
  <h1>404</h1>
  <p>That page or part doesn&rsquo;t exist.</p>
  <a class="btn btn-primary" href="<?= e($_controller->url('/')) ?>">Back to the catalog</a>
</section>
