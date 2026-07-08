<?php
declare(strict_types=1);

namespace App\Controllers\Admin;

use App\Core\Controller;
use App\Core\Auth;

/** Login / logout. Extends Controller directly so it is NOT behind the auth guard. */
class AuthController extends Controller
{
    public function showLogin(): void
    {
        Auth::start();
        if (Auth::check()) { $this->redirect('/admin'); }
        $this->renderLogin();
    }

    public function login(): void
    {
        Auth::start();
        if (!Auth::verify($_POST['_csrf'] ?? null)) {
            $this->renderLogin('Session expired — please try again.');
            return;
        }
        $email = trim((string) ($_POST['email'] ?? ''));
        $password = (string) ($_POST['password'] ?? '');
        if (Auth::attempt($email, $password)) {
            $this->redirect('/admin');
        }
        $this->renderLogin('Incorrect email or password.');
    }

    public function logout(): void
    {
        Auth::logout();
        $this->redirect('/admin/login');
    }

    private function renderLogin(?string $error = null): void
    {
        $data = [
            'title'   => 'Admin Sign In — Supreme Parts',
            'error'   => $error,
            'csrf'    => Auth::token(),
            '_controller' => $this,
        ];
        echo $this->capture('admin/login', $data);
    }
}
