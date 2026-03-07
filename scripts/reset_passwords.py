# reset_passwords.py
# Bulk jelszó reset – CSAK dev/staging. Productionben tiltva (prod_guard).
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.hash import bcrypt_sha256 as pwd_hasher

from config.settings import settings
from apps.users.infrastructure.db.models import UserORM

from config.prod_guard import reject_if_production


def main():
    reject_if_production("reset_passwords", "bulk jelszó reset")
    engine = create_engine(settings.database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    new_password = "psw123"

    with SessionLocal() as s:
        users = s.query(UserORM).all()
        print(f"{len(users)} felhasználó található az adatbázisban.")

        for u in users:
            u.password_hash = pwd_hasher.hash(new_password)
            print(f" - {u.email} jelszava átírva 'psw123'-ra")

        s.commit()
        print("✅ Minden user jelszava frissítve.")


if __name__ == "__main__":
    main()