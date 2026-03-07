# Scriptek: DB és admin user (PostgreSQL)

## 1. Adatbázis beállítása

A `.env` fájlban állítsd be a **PostgreSQL** kapcsolatot (másold a `.env.example`-t `.env`-re, ha még nincs):

```bash
database_url=postgresql+psycopg2://USER:JELSZÓ@localhost:5432/aiplaza
```

Hozz létre egy üres adatbázist (ha még nincs):

```bash
psql -U postgres -c "CREATE DATABASE aiplaza;"
# vagy: createdb -U postgres aiplaza
```

## 2. Táblák létrehozása

A projekt gyökeréből:

```bash
.venv/bin/python scripts/init_db.py
```

Ez létrehozza az auth táblákat (users, sessions, settings, 2FA táblák, stb.).

## 3. Admin felhasználó létrehozása

```bash
.venv/bin/python scripts/seed_user.py
```

Alapértelmezett admin: **admin@example.com** / **admin123** (role: admin, superuser).

Saját email/jelszó (környezeti változókkal):

```bash
ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=saját_jelszó .venv/bin/python scripts/seed_user.py
```

Opcionális: `ADMIN_ROLE=user`, `ADMIN_SUPERUSER=false` – ha nem admint, hanem sima usert akarsz.

## Összefoglalva (copy-paste)

```bash
# 1. .env: database_url=postgresql+psycopg2://user:pass@localhost:5432/aiplaza
# 2. DB és táblák
.venv/bin/python scripts/init_db.py
# 3. Admin user
.venv/bin/python scripts/seed_user.py
```

Ezután be tudsz lépni az alkalmazásban (pl. frontend vagy Swagger) **admin@example.com** / **admin123**-mal.
