/* Supreme Parts — expandable catalog tree (RockAuto-style in-place drilldown).
   Make -> Year -> Model -> Engine(vehicle) -> Group -> Part Type -> Parts, lazy-loaded.
   "Group" is RockAuto's category tier (e.g. Brake & Wheel Hub > Brake Fluid). */
(function () {
  var tree = document.getElementById('catalogTree');
  if (!tree) return;
  var API = tree.dataset.api, VEH = tree.dataset.veh, PART = tree.dataset.part, CART = tree.dataset.cart;

  function enc(s) { return encodeURIComponent(s == null ? '' : s); }
  function get(path) {
    return fetch(API + path, { headers: { Accept: 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : []; })
      .catch(function () { return []; });
  }
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }
  function money(n) { return '$' + Number(n).toFixed(2); }

  function childRequest(d) {
    switch (d.level) {
      case 'make':     return { kind: 'year',     url: '/years?make=' + enc(d.make) };
      case 'year':     return { kind: 'model',    url: '/models?make=' + enc(d.make) + '&year=' + enc(d.year) };
      case 'model':    return { kind: 'vehicle',  url: '/vehicles?make=' + enc(d.make) + '&year=' + enc(d.year) + '&model=' + enc(d.model) };
      case 'vehicle':  return { kind: 'group',    url: '/groups?vehicle=' + enc(d.vehicle) };
      case 'group':    return { kind: 'category', url: '/categories?vehicle=' + enc(d.vehicle) + '&group=' + enc(d.group) };
      case 'category': return { kind: 'parts',    url: '/parts?vehicle=' + enc(d.vehicle) + '&category=' + enc(d.category) };
    }
    return null;
  }

  function buildNode(kind, item, parent) {
    var li = document.createElement('li');
    li.className = 'node node-' + kind;
    ['make', 'year', 'model', 'vehicle', 'group', 'category'].forEach(function (k) {
      if (parent[k]) li.dataset[k] = parent[k];
    });
    var label, count = '', jump = '';
    if (kind === 'year')        { li.dataset.level = 'year';     li.dataset.year = item;       label = item; }
    else if (kind === 'model')  { li.dataset.level = 'model';    li.dataset.model = item.slug; label = item.name; }
    else if (kind === 'vehicle'){ li.dataset.level = 'vehicle';  li.dataset.vehicle = item.slug; label = item.label;
                                  jump = ' <a class="node-jump" href="' + VEH + '/' + enc(item.slug) + '">all parts &rarr;</a>'; }
    else if (kind === 'group')  { li.dataset.level = 'group';    li.dataset.group = item.slug; label = item.name; count = item.n; }
    else if (kind === 'category'){ li.dataset.level = 'category'; li.dataset.category = item.slug; label = item.name; count = item.n; }
    li.innerHTML =
      '<div class="node-row">' +
        '<button class="toggle" aria-label="Expand"><span class="tw">+</span></button>' +
        '<span class="node-label">' + esc(label) + '</span>' +
        (count !== '' ? '<span class="node-count">' + esc(count) + '</span>' : '') + jump +
      '</div><ul class="children" hidden></ul>';
    return li;
  }

  function renderParts(ul, parts) {
    if (!parts.length) { ul.innerHTML = '<li class="parts-empty">No parts in this category for this vehicle.</li>'; return; }
    var rows = parts.map(function (p) {
      // price IS NULL => RockAuto shows no price at all: out of stock, not buyable.
      var oos = (p.price === null || p.price === undefined);
      return '<tr' + (oos ? ' class="pm-row-oos"' : '') + '>' +
        '<td class="pm-brand">' + esc(p.brand || '') + '</td>' +
        '<td class="pm-name"><a href="' + PART + '/' + enc(p.sku) + '">' + esc(p.name) + '</a>' +
          '<span class="pm-pn">#' + esc(p.part_number) + (p.note ? ' &middot; ' + esc(p.note) : '') + '</span></td>' +
        '<td class="pm-price">' + (oos ? '<span class="pm-oos">Out of Stock</span>' : money(p.price)) + '</td>' +
        '<td class="pm-buy">' + (oos
          ? '<span class="pm-notify">Notify Me</span>'
          : '<form method="post" action="' + CART + '">' +
            '<input type="hidden" name="sku" value="' + esc(p.sku) + '">' +
            '<button class="btn btn-primary btn-xs" type="submit">Add</button></form>') + '</td>' +
      '</tr>';
    }).join('');
    ul.innerHTML = '<li class="parts-leaf"><table class="parts-mini"><tbody>' + rows + '</tbody></table></li>';
  }

  tree.addEventListener('click', function (ev) {
    if (ev.target.closest('.node-jump')) return;      // let the link navigate
    var hit = ev.target.closest('.toggle, .node-label');
    if (!hit || !tree.contains(hit)) return;
    var node = hit.closest('.node');
    var children = node.querySelector(':scope > .children');
    var open = node.classList.toggle('open');
    node.querySelector('.tw').textContent = open ? '–' : '+';
    if (!open) { children.hidden = true; return; }
    children.hidden = false;
    if (node.dataset.loaded === '1') return;
    node.dataset.loaded = '1';
    var req = childRequest(node.dataset);
    if (!req) return;
    children.innerHTML = '<li class="loading">Loading&hellip;</li>';
    get(req.url).then(function (items) {
      children.innerHTML = '';
      if (req.kind === 'parts') { renderParts(children, items); return; }
      if (!items.length) { children.innerHTML = '<li class="parts-empty">Nothing here yet.</li>'; return; }
      items.forEach(function (it) { children.appendChild(buildNode(req.kind, it, node.dataset)); });
    });
  });

  // A-Z quick filter on top-level makes
  var az = document.getElementById('azIndex');
  if (az) az.addEventListener('click', function (ev) {
    var b = ev.target.closest('.az');
    if (!b || b.disabled) return;
    var L = b.dataset.letter;
    az.querySelectorAll('.az').forEach(function (x) { x.classList.remove('active'); });
    b.classList.add('active');
    tree.querySelectorAll(':scope > .node-make').forEach(function (n) {
      n.style.display = (!L || n.dataset.letter === L) ? '' : 'none';
    });
  });
})();
