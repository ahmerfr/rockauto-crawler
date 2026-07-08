<?php
declare(strict_types=1);

namespace App\Core;

use PDO;

/** Session-based admin authentication + CSRF for the admin panel. */
class Auth
{
    public static function start(): void
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            session_start();
        }
    }

    public static function attempt(string $email, string $password): bool
    {
        $db = Database::connection();
        $stmt = $db->prepare("SELECT * FROM admins WHERE email = ? AND is_active = 1");
        $stmt->execute([$email]);
        $admin = $stmt->fetch();
        if (!$admin || !password_verify($password, $admin['password_hash'])) {
            return false;
        }
        self::start();
        session_regenerate_id(true);
        $_SESSION['admin'] = [
            'id'    => (int) $admin['id'],
            'name'  => $admin['name'],
            'email' => $admin['email'],
        ];
        $db->prepare("UPDATE admins SET last_login_at = NOW() WHERE id = ?")->execute([$admin['id']]);
        return true;
    }

    public static function check(): bool
    {
        self::start();
        return isset($_SESSION['admin']);
    }

    public static function user(): ?array
    {
        self::start();
        return $_SESSION['admin'] ?? null;
    }

    public static function logout(): void
    {
        self::start();
        unset($_SESSION['admin']);
        session_regenerate_id(true);
    }

    // ---- CSRF ----
    public static function token(): string
    {
        self::start();
        if (empty($_SESSION['csrf'])) {
            $_SESSION['csrf'] = bin2hex(random_bytes(32));
        }
        return $_SESSION['csrf'];
    }

    public static function verify(?string $token): bool
    {
        self::start();
        return !empty($_SESSION['csrf']) && is_string($token) && hash_equals($_SESSION['csrf'], $token);
    }
}
