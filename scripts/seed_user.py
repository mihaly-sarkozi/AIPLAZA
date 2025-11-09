from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.hash import bcrypt_sha256 as pwd_hasher


from config.settings import settings
from infrastructure.persistence.mysql.auth_models import AuthBase, UserORM

def main():
    engine = create_engine(settings.mysql_dsn, future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    email = "test@example.com"
    password = "secret"  # csak dev!
    pwd_hash = pwd_hasher.hash(password)

    with SessionLocal() as s:
        # ha már létezik, nem szúrjuk be újra
        if s.query(UserORM).filter(UserORM.email == email).first():
            print("User already exists:", email)
            return
        u = UserORM(email=email, password_hash=pwd_hash, is_active=True)
        s.add(u)
        s.commit()
        print("User created:", email, "password:", password)

if __name__ == "__main__":
    main()