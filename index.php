<?php
declare(strict_types=1);

use App\Core\Router;

$config = require __DIR__ . '/bootstrap.php';

$router = new Router($config['app']['base_path']);

// Storefront
$router->get('/', 'HomeController@index');
$router->get('/search', 'CatalogController@search');

// JSON API for the cascading vehicle picker
$router->get('/api/years', 'ApiController@years');
$router->get('/api/makes', 'ApiController@makes');
$router->get('/api/models', 'ApiController@models');
$router->get('/api/vehicles', 'ApiController@vehicles');

// JSON API for the expandable catalog tree
$router->get('/api/tree/makes', 'ApiController@treeMakes');
$router->get('/api/tree/years', 'ApiController@treeYears');
$router->get('/api/tree/models', 'ApiController@models');
$router->get('/api/tree/vehicles', 'ApiController@vehicles');
$router->get('/api/tree/groups', 'ApiController@treeGroups');
$router->get('/api/tree/categories', 'ApiController@treeCategories');
$router->get('/api/tree/parts', 'ApiController@treeParts');

// Browse
$router->get('/make/{makeSlug}', 'CatalogController@make');
$router->get('/vehicle/{slug}', 'CatalogController@vehicle');
$router->get('/vehicle/{slug}/c/{catSlug}', 'CatalogController@vehicleCategory');
$router->get('/part/{sku}', 'PartController@show');

// ---- Cart + checkout ----
$router->get('/cart', 'CartController@view');
$router->post('/cart/add', 'CartController@add');
$router->post('/cart/update', 'CartController@update');
$router->post('/cart/remove', 'CartController@remove');
$router->post('/checkout', 'CheckoutController@start');
$router->get('/checkout/success', 'CheckoutController@success');
$router->get('/checkout/cancel', 'CheckoutController@cancel');
$router->post('/webhook/stripe', 'WebhookController@stripe');

// ---- Admin panel ----
$router->get('/admin/login', 'Admin\AuthController@showLogin');
$router->post('/admin/login', 'Admin\AuthController@login');
$router->post('/admin/logout', 'Admin\AuthController@logout');

$router->get('/admin', 'Admin\DashboardController@index');

$router->get('/admin/parts', 'Admin\PartController@index');
$router->get('/admin/parts/create', 'Admin\PartController@create');
$router->post('/admin/parts', 'Admin\PartController@store');
$router->get('/admin/parts/{id}/edit', 'Admin\PartController@edit');
$router->post('/admin/parts/{id}', 'Admin\PartController@update');
$router->post('/admin/parts/{id}/delete', 'Admin\PartController@delete');

$router->get('/admin/brands', 'Admin\BrandController@index');
$router->post('/admin/brands', 'Admin\BrandController@store');
$router->post('/admin/brands/{id}', 'Admin\BrandController@update');
$router->post('/admin/brands/{id}/delete', 'Admin\BrandController@delete');

$router->get('/admin/categories', 'Admin\CategoryController@index');
$router->post('/admin/categories', 'Admin\CategoryController@store');
$router->post('/admin/categories/{id}', 'Admin\CategoryController@update');
$router->post('/admin/categories/{id}/delete', 'Admin\CategoryController@delete');

$router->get('/admin/catalog', 'Admin\CatalogController@index');

$router->get('/admin/imports', 'Admin\ImportController@index');
$router->post('/admin/imports/vpic', 'Admin\ImportController@runVpic');
$router->post('/admin/imports/acespies', 'Admin\ImportController@runAcesPies');

$router->get('/admin/settings', 'Admin\SettingsController@index');
$router->post('/admin/settings', 'Admin\SettingsController@save');

$router->dispatch($_SERVER['REQUEST_METHOD'], $_SERVER['REQUEST_URI']);
