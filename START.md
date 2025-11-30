# 🚀 AIPLAZA Elindítási Útmutató

## Előfeltételek

1. **Python 3.9+** telepítve
2. **Node.js 18+** és **pnpm** (vagy npm) telepítve
3. **MySQL** adatbázis fut
4. **Qdrant** vektoradatbázis elérhető (cloud vagy local)
5. **OpenAI API kulcs**

## 1️⃣ Környezeti változók beállítása

Hozz létre egy `.env` fájlt a projekt gyökerében:

```bash
# .env fájl
QDRANT_URL=https://your-qdrant-instance.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key
OPENAI_API_KEY=sk-your-openai-api-key

# Opcionális (ha másképp szeretnéd)
APP_ENV=dev
mysql_dsn=mysql+pymysql://root:password@localhost:3306/aiplaza
```

## 2️⃣ Adatbázis beállítása

### MySQL adatbázis létrehozása:
```sql
CREATE DATABASE aiplaza CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Táblák inicializálása:
```bash
python scripts/init_db.py
```

### Teszt felhasználó létrehozása (opcionális):
```bash
python scripts/seed_user.py
```

## 3️⃣ Backend függőségek telepítése

```bash
# Python virtual environment létrehozása (ajánlott)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# vagy
venv\Scripts\activate  # Windows

# Függőségek telepítése
pip install -r requirements.txt
```

## 4️⃣ Frontend függőségek telepítése

```bash
cd frontend
pnpm install
# vagy
npm install
```

## 5️⃣ Backend elindítása

A projekt gyökerében:

```bash
# Fejlesztési módban (auto-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8010

# Vagy ha uvicorn nincs a PATH-ban
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8010
```

A backend elérhető lesz: **http://localhost:8010**
API dokumentáció: **http://localhost:8010/docs**

## 6️⃣ Frontend elindítása

Külön terminálban, a `frontend` mappában:

```bash
cd frontend
pnpm dev
# vagy
npm run dev
```

A frontend elérhető lesz: **http://localhost:5173**

## 7️⃣ Ellenőrzés

1. Nyisd meg a böngészőt: **http://localhost:5173**
2. Próbáld meg bejelentkezni (ha van seed user)
3. Ellenőrizd a backend API-t: **http://localhost:8010/docs**

## 🔧 Hibaelhárítás

### Backend nem indul el:
- Ellenőrizd, hogy a `.env` fájl létezik és helyes
- Ellenőrizd a MySQL kapcsolatot
- Ellenőrizd, hogy a Qdrant és OpenAI API kulcsok érvényesek

### Frontend nem csatlakozik a backendhez:
- Ellenőrizd a `frontend/.env` fájlt (ha van)
- Ellenőrizd, hogy a `VITE_API_URL` be van állítva: `http://localhost:8010/api`
- Ellenőrizd a CORS beállításokat a `main.py`-ban

### Adatbázis hiba:
- Ellenőrizd, hogy a MySQL fut
- Ellenőrizd a `mysql_dsn` értékét a `.env`-ben vagy `config/base.py`-ban
- Futtasd újra az `init_db.py` scriptet

## 📝 Hasznos parancsok

```bash
# Jelszavak resetelése (teszteléshez)
python reset_passwords.py

# Adatbázis újrainicializálása
python scripts/init_db.py
```

## 🌐 Production mód

Production módban futtatáshoz:

```bash
# .env fájlban
APP_ENV=prod

# Backend
uvicorn main:app --host 0.0.0.0 --port 8010

# Frontend build
cd frontend
pnpm build
pnpm preview
```



