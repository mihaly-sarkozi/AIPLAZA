# scripts/add_superuser_column.py
"""
Migration script: is_superuser oszlop hozzáadása a users táblához.
A beállítások a config.settings-ből jönnek (a loader betölti a .env-t).
"""
import sys
from pathlib import Path

# Projekt gyökér a path-on, hogy a config importálható legyen
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from sqlalchemy import create_engine, text


def main():
    engine = create_engine(settings.database_url, future=True)
    
    with engine.connect() as conn:
        # Ellenőrizzük, hogy létezik-e már az oszlop
        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'users'
            AND COLUMN_NAME = 'is_superuser'
        """))
        
        if result.scalar() > 0:
            print("✅ is_superuser oszlop már létezik.")
            return
        
        # Hozzáadjuk az oszlopot
        conn.execute(text("""
            ALTER TABLE users
            ADD COLUMN is_superuser BOOLEAN DEFAULT FALSE NOT NULL
        """))
        conn.commit()
        print("✅ is_superuser oszlop hozzáadva a users táblához.")
        
        # Opcionális: első user-t superuser-rá állítjuk (ha nincs még superuser)
        result = conn.execute(text("""
            SELECT COUNT(*) FROM users WHERE is_superuser = TRUE
        """))
        
        if result.scalar() == 0:
            # Az első user-t superuser-rá állítjuk
            conn.execute(text("""
                UPDATE users
                SET is_superuser = TRUE, role = 'admin'
                WHERE id = (SELECT id FROM users ORDER BY created_at ASC LIMIT 1)
            """))
            conn.commit()
            print("✅ Az első user superuser-rá állítva.")

if __name__ == "__main__":
    main()

