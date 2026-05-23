# 🚀 AIPLAZA Elindítási Útmutató

## Előfeltételek

1. **Python 3.9+** telepítve
2. **Node.js 18+** és **pnpm** (vagy npm) telepítve
3. **PostgreSQL** adatbázis fut
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
database_url=postgresql+psycopg2://postgres:password@localhost:5432/aiplaza
```

## 2️⃣ Adatbázis beállítása

### PostgreSQL adatbázis létrehozása:
```bash
psql -U postgres -c "CREATE DATABASE aiplaza;"
# vagy: createdb -U postgres aiplaza
```

### Táblák inicializálása:
```bash
python backend/scripts/init_db.py
```

## 3️⃣ Backend függőségek telepítése

```bash
# Python virtual environment létrehozása (ajánlott)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# vagy
venv\Scripts\activate  # Windows

# Függőségek telepítése
cd backend
pip install -r requirements.txt
```

## 4️⃣ Frontend függőségek telepítése

```bash
cd frontend
pnpm install
# vagy
npm install
```

## 4️⃣+ Docker indítás

Ha mindent Dockerből szeretnél futtatni:

```bash
docker compose up --build
```

Ez elindítja:
- `postgres` a `5432` porton
- `qdrant` a `6333` porton
- `backend` a `8001` porton
- `frontend` a `5173` porton

A backend induláskor lefuttatja a `backend/scripts/init_db.py` inicializálást is.

Fejlesztői multi-tenant host:
- landing/install: `http://lvh.me:5173`
- tenant példa: `http://misi.lvh.me:5173`

Az `lvh.me` és minden aldomainje automatikusan a `127.0.0.1`-re mutat, ezért nem kell hosts fájlt szerkeszteni.

## 5️⃣ Backend elindítása

A `backend` mappában:

```bash
# Fejlesztési módban (auto-reload)
cd backend
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
A tenant-kompatibilis frontend cím: **http://lvh.me:5173**
A Dockeres backend elérhető lesz: **http://localhost:8001**

## 7️⃣ Ellenőrzés

1. Nyisd meg a böngészőt: **http://localhost:5173**
   Tenant teszthez inkább: **http://lvh.me:5173**
2. Ellenőrizd, hogy a public platform táblák létrejöttek
3. Ellenőrizd a backend API-t: **http://localhost:8010/docs**

## 🔧 Hibaelhárítás

### Backend nem indul el:
- Ellenőrizd, hogy a `.env` fájl létezik és helyes
- Ellenőrizd a PostgreSQL kapcsolatot
- Ellenőrizd, hogy a Qdrant és OpenAI API kulcsok érvényesek

### Frontend nem csatlakozik a backendhez:
- Ellenőrizd a `frontend/.env` fájlt (ha van)
- Ellenőrizd, hogy a `VITE_API_URL` be van állítva: `http://localhost:8010/api`
- Ellenőrizd a CORS beállításokat a `main.py`-ban

### Adatbázis hiba:
- Ellenőrizd, hogy a PostgreSQL fut
- Ellenőrizd a `database_url` értékét a `.env`-ben
- Futtasd újra az `init_db.py` scriptet

### Docker hiba:
- Ellenőrizd, hogy a Docker Desktop vagy a Docker Engine fut
- Ha portütközés van, nézd meg a `docker-compose.yml` portjait
- Frontend proxy gond esetén ellenőrizd a `VITE_DEV_PROXY_TARGET` értéket
- Ha a `postgres` konténer jelszóhibával áll fel, valószínűleg régi Docker volume maradt meg. Ilyenkor:
- A fejlesztői Docker felállásban a compose-os Postgres konténer `trust` host auth-tal indul, és a backend a konténerhálózaton jelszó nélküli DB URL-t használ. Ez csak lokális fejlesztésre való.

```bash
docker compose down -v
docker compose up --build
```

- Ha a backend korábban jelszóhibával (`password authentication failed for user "postgres"`) állt le, a fenti újraindítás után már az új compose beállítással fog indulni.

Ha régi volume maradt:

```bash
docker compose down -v
docker compose up --build
```

- A `-v` törli a korábbi `postgres_data` volume-ot is, így a Postgres az aktuális `docker-compose.yml` szerinti jelszóval inicializálódik újra.

## 📝 Hasznos parancsok

```bash
# Adatbázis inicializálása vagy hiányzó táblák pótlása
python backend/scripts/init_db.py
```

## 🌐 Production mód

Production módban futtatáshoz:

```bash
# .env fájlban
APP_ENV=prod

# Backend
cd backend
uvicorn main:app --host 0.0.0.0 --port 8010

# Frontend build
cd ../frontend
pnpm build
pnpm preview
```



