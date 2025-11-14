# reset_passwords.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.hash import bcrypt_sha256 as pwd_hasher

from config.settings import settings
from infrastructure.persistence.mysql.auth_models import UserORM


def main():
    engine = create_engine(settings.mysql_dsn, future=True)
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