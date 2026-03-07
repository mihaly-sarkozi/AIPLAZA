# Környezeti beállítás

Leírja, **honnan** jönnek a konfigurációs értékek és a titkok, **hol** töltődnek be, és **milyen változókra** van szükség.

---

## 1. Mi történik induláskor? (egy helyen a beállítás)

1. Valahol az alkalmazás **először** importálja a **config**-ot (pl. `from config.settings import settings`). Ekkor betöltődik a **`config/loader.py`**.
2. A **loader** modul betöltésekor a **`load_dotenv(_ENV_PATH)`** lefut: a projekt gyökerében lévő **`.env`** fájl beolvasásra kerül az **`os.environ`**-ba.
3. Ezután a **`load_settings()`** (DevConfig / ProdConfig) az **`os.environ`**-ból tölti ki a pydantic config objektumot. A **config/base.py** (és dev, prod) csak alapértékeket és mezőneveket ad; a tényleges értékek az **`.env` → `os.environ`** útvonalról jönnek.

Összefoglalva: **Egy hely tölti a .env-t: `config/loader.py`.** A többi kód csak a **`config.settings`**-et használja (sem `load_dotenv()`, sem `os.getenv()` a szolgáltatásokban/scriptekben).

---

## 1b. Honnan jön konkrétan az érték: .env vagy config/*.py?

**Egy helyen a .env, egy helyen a struktúra:**

1. **config/loader.py** – a **.env** fájlt **itt** tölti be a `load_dotenv(_ENV_PATH)` (projekt gyökér). Ez feltölti az **`os.environ`**-t. Nincs más `load_dotenv()` a projektben.
2. **config/base.py** (és dev, prod) – **mezőnevek és alapértékek**. Pl. `cors_origins: str = "http://localhost:5173"`. A pydantic ezeket az **`os.environ`**-ból tölti ki (amit a loader már feltöltött).
3. **Végső érték:** ha a `.env`-ben van `CORS_ORIGINS=...`, akkor azt használja; ha nincs, akkor a **config/base.py** alapértékét.

Tehát: **.env** = felülírások (loader tölti); **config/*.py** = mezők + alapértékek; **settings** = ebből a kettőből összeálló objektum, amit mindenhol ezt használjuk.

---

## 1c. Mit érdemes .env-be tenni?

| Prioritás | Változó(k) | Miért |
|-----------|------------|--------|
| **Élesben kötelező** | `JWT_SECRET` | Titok, ne legyen kódban; erős véletlen érték (pl. `openssl rand -hex 64`). |
| **Élesben / biztonság** | `database_url` | Az adatbázis jelszava ne legyen a base.py alapértékében (PostgreSQL). |
| **Élesben / biztonság** | `CORS_ORIGINS` | Élesben a valódi frontend URL(ek); dev-ben lehet localhost. |
| **Ha használod az emailt** | `smtp_user`, `smtp_password` | Belépési adatok, mindig .env-ben. |
| **Opcionális** | `api_port`, `access_ttl_min`, `refresh_ttl_days`, `smtp_*` többi | Környezetenként más érték. |

A **.env.example** ugyanezeket sorolja; másold át a saját `.env`-be és töltsd ki.

---

## 2. Hol van a konfig definiálva?

| Fájl | Szerepe |
|------|--------|
| **`config/base.py`** | Közös alapértékek (API host/port, PostgreSQL database_url, JWT, SMTP, Ollama). Ha egy mezőnek nincs környezeti változó, ezek az alapértelmezések használódnak. |
| **`config/dev.py`** | Dev környezet: **DevConfig** örökli a BaseConfig-et, és **kötelező** mezőket ad (QDRANT_URL, QDRANT_API_KEY, OPENAI_API_KEY). Ezeknek érdemes a `.env`-ben lennie. |
| **`config/prod.py`** | Prod környezet: **ProdConfig** – egyelőre csak override-ok lehetnek, alapértékek a BaseConfig-ből jönnek. |
| **`config/loader.py`** | Az **APP_ENV** környezeti változó alapján dönt: `APP_ENV=prod` → ProdConfig, egyébként → DevConfig. Alapértelmezett: **dev**. |
| **`config/settings.py`** | Egy **`settings`** objektumot exportál: ez a **load_settings()** eredménye (tehát DevConfig vagy ProdConfig példány). Ezt használja az alkalmazás (pl. **`config.settings`** → **`settings`**). |

Tehát a **környezeti beállítás** = `.env` (vagy rendszer környezeti változók) + **config/base.py, dev.py, prod.py, loader.py**, és a végső értékek az **`settings`** objektumban érhetők el.

---

## 3. Milyen változókra van szükség?

### 3.1 Közös (BaseConfig) – alapértelmezéssel

Ezeket **felül lehet írni** a `.env`-ben; ha nincs megadva, az alábbi alapértékek lépnek életbe:

| Változó | Alapérték | Használat |
|---------|-----------|-----------|
| **api_host** | `0.0.0.0` | API szerver bind cím |
| **api_port** | `8010` | API szerver port |
| **cors_origins** | `http://localhost:5173` | CORS engedélyezett origin(ok), vesszővel elválasztva (pl. `http://localhost:5173,https://app.example.com`) |
| **database_url** | `postgresql+psycopg2://postgres:postgres@localhost:5432/aiplaza` | PostgreSQL kapcsolat (SQLAlchemy) |
| **ollama_url** | `http://localhost:11434` | Ollama LLM URL |
| **ollama_model** | `qwen2.5:7b-instruct` | Ollama modell neve |
| **jwt_secret** | (alapértelmezett string) | JWT aláírás/ellenőrzés – **élesben mindig cseréld saját titkosra** |
| **access_ttl_min** | `15` | Access token élettartam (perc) |
| **refresh_ttl_days** | `14` | Refresh token élettartam (nap) |
| **smtp_host**, **smtp_port**, **smtp_user**, **smtp_password**, **smtp_from_email**, **smtp_from_name** | (lásd base.py) | Email küldés (pl. 2FA kód) |

### 3.2 Dev környezet (DevConfig) – kötelező

Ha **APP_ENV** nincs beállítva vagy nem `prod`, a **DevConfig** töltődik. Ebben ezek **kötelezőek** (nincs alapérték):

| Változó | Használat |
|---------|-----------|
| **QDRANT_URL** | Qdrant vektor DB URL (pl. cloud vagy local) |
| **QDRANT_API_KEY** | Qdrant API kulcs |
| **OPENAI_API_KEY** | OpenAI API kulcs (embedding, chat) |

Ezeket a **`.env`** fájlba kell tenni (vagy rendszer környezeti váltoóként megadni), különben a config betöltése hibát dob.

### 3.3 Környezet választó

| Változó | Érték | Hatás |
|---------|--------|--------|
| **APP_ENV** | `dev` (alapértelmezett) vagy nincs | **DevConfig** (QDRANT + OPENAI kötelező) |
| **APP_ENV** | `prod` | **ProdConfig** (jelenleg BaseConfig override-okkal) |

---

## 4. Hol használják a `settings`-t az alkalmazásban?

- **`apps/core/container/app_container.py`**  
  - `settings.database_url` → DB session factory  
  - `settings.jwt_secret`, TTL-ek → token service  
  - `settings.QDRANT_URL`, `settings.QDRANT_API_KEY`, `settings.OPENAI_API_KEY` → Qdrant és embedding  

- **`apps/core/db/dependency.py`**  
  - `settings.database_url` → SessionLocal  

- **`apps/core/email/email_service.py`**  
  - SMTP és egyéb email beállítások (ha van ilyen használat)  

Egyes modulok (pl. **`apps/core/qdrant/service.py`**, **`apps/chat/application/services/chat_service.py`**) még közvetlenül **`os.getenv("...")`**-t is használnak; érdemes hosszú távon ezeket is a **`settings`** felé rendezni, hogy egy helyen legyen a környezeti beállítás.

---

## 5. Gyakorlati lépések

1. A projekt gyökerében hozz létre egy **`.env`** fájlt (ez a `.gitignore` miatt nem kerül verziókövetésbe).
2. Állítsd be legalább a **DevConfig** kötelező változóit: **QDRANT_URL**, **QDRANT_API_KEY**, **OPENAI_API_KEY**.
3. Opcionálisan írd felül: **database_url**, **jwt_secret**, **api_port** stb.
4. Élesben állíts **APP_ENV=prod**-ot, és használj erős **jwt_secret**-et, valamint biztonságos **database_url**-t és Qdrant/OpenAI kulcsokat.

Így a **környezeti beállítás** = a fenti változók a `.env`-ben (vagy környezetben) + a **config** réteg, ami ezekből az **`settings`** objektumot adja az alkalmazásnak.
