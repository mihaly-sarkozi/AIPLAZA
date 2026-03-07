-- 2FA brute-force védelem: sikertelen próbálkozások (pending token / user / IP alapú limit).
-- 2026.03 - Sárközi Mihály

CREATE TABLE IF NOT EXISTS two_factor_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    scope VARCHAR(20) NOT NULL,
    scope_key VARCHAR(128) NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    window_start_at DATETIME NOT NULL,
    UNIQUE KEY ix_2fa_attempt_scope_key (scope, scope_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
