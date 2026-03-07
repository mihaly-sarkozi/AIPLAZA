# scripts/create_2fa_tables.py
"""
Migrációs script a 2FA táblák létrehozásához.
A beállítások a config.settings-ből jönnek (a loader betölti a .env-t).
"""
import os
import sys
from sqlalchemy import create_engine, text

# Projekt gyökér a path-on, hogy a config importálható legyen
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import settings


def main():
    """Létrehozza a settings és two_factor_codes táblákat."""
    engine = create_engine(settings.database_url, future=True)
    
    with engine.connect() as conn:
        # Settings tábla
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                `key` VARCHAR(100) UNIQUE NOT NULL,
                value VARCHAR(500) NOT NULL,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                updated_by INT,
                FOREIGN KEY (updated_by) REFERENCES users(id),
                INDEX idx_key (`key`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))
        
        # Two factor codes tábla
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS two_factor_codes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                code VARCHAR(6) NOT NULL,
                email VARCHAR(255) NOT NULL,
                expires_at DATETIME NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                INDEX idx_user_expires (user_id, expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))
        
        conn.commit()
        print("✅ Settings és two_factor_codes táblák létrehozva.")


if __name__ == "__main__":
    main()

