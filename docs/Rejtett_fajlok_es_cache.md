# .env láthatóvá tétele és cache elrejtése Cursorban

Ha nem látod a `.env` fájlt vagy nem tudod beállítani a cache elrejtését, ezekkel lépésről lépésre megoldható.

**Fontos:** A **Cmd +** (Command és a plusz, +) a Cursorban a betűméret növelése. Az alábbi parancsok **más billentyűk**: Command + **P** betű, illetve Command + **vessző (,)**.

---

## 1. .env megnyitása (akkor is, ha nem látszik a fájlfában)

Nem kell a fálfan keresni – nyisd meg közvetlenül:

1. Nyomd meg: **Command + P** (tartsd nyomva a **⌘ Cmd**-t, majd nyomd meg a **P** betűt – nem a pluszt).
2. Gépeld be: **`.env`**
3. Ha megjelenik a listában a **`.env`**, nyomj **Enter** – megnyílik.

Így mindig elérheted a `.env`-et, akár rejtett, akár nem.

---

## 2. Rejtett fájlok (pl. .env) megjelenítése a bal oldali fájlfában

Ha szeretnéd, hogy a **bal oldali fájlfában** is látszódjon a `.env`:

### Cursor beállítás (egy lehetőség)

1. **Command + vessző** – tartsd nyomva a **⌘ Cmd**-t, nyomd meg a **,** (vessző) billentyűt. Megnyílik a Beállítások. (Vagy menü: **File → Preferences → Settings**.)
2. A Beállítások **tetején** van egy **keresőmező** („Search settings”). Oda írd be: **`exclude`** vagy **`explorer exclude`**.
3. A listában keresd meg a **„Explorer: Exclude Git Ignore”** (vagy **„Files: Exclude Git Ignore”**) sort. Ha **be van pipálva** / true, a Cursor **nem mutatja** a `.gitignore`-ban lévő fájlokat – a **`.env`** is ott van. **Kapcsold ki** (távolítsd el a pipát / állítsd false-ra), így a `.env` is megjelenik a bal oldali fájlfában.
4. Ha a **cache** ne jelenjen meg: a keresőmezőbe írd: **`files exclude`**, és ott add hozzá (vagy nézd meg) a **`**/__pycache__`**, **`**/*.pyc`** mintákat.

### Másik lehetőség: Cursorban a fájlfa

- Kattints a **bal oldali Explorer** ikonra (vagy **Cmd + Shift + E** – Command, Shift és az E betű).
- A fájlfa **tetején** van egy **„…”** vagy fogaskerék ikon – nézd meg, van-e **„Show hidden files”** vagy hasonló. Ha igen, kapcsold be.

Ha egyik sem segít, a **Command + P**, majd **.env** módszerrel továbbra is megnyithatod a fájlt.

---

## 3. Python cache (__pycache__, szemét) elrejtése

A projektben van egy **`.vscode/settings.json`** fájl. Ha ez megvan, a Cursor **nem mutatja** a fájlfában a `__pycache__` mappákat és a `.pyc` fájlokat.

### Ha mégsem rejtődnek el – kézi beállítás

1. **Command + vessző (,)** → Settings.
2. Keresd: **`files.exclude`**.
3. Kattints **„Add pattern”** (vagy „Edit in settings.json”).
4. Add hozzá ezeket (ha már van `files.exclude`, bővítsd):

```json
"files.exclude": {
  "**/__pycache__": true,
  "**/*.pyc": true,
  "**/.DS_Store": true
}
```

Mentés után a fájlfában ezek a mappák/fájlok el fognak tűnni.

---

## 4. Rövid összefoglaló

| Cél | Mit csinálj |
|-----|--------------|
| **.env megnyitása** | **Cmd + P** (Command és a P betű) → gépeld: `.env` → Enter. |
| **.env a fájlfában** | Settings (Cmd + vessző) → keresd: `explorer.excludeGitIgnore` → állítsd **false**-ra. |
| **Cache elrejtése** | Használd a projekt `.vscode/settings.json`-t, vagy Settings → `files.exclude` → add: `**/__pycache__`, `**/*.pyc`. |

A legbiztosabb: **Cmd + P** (a P betű, nem a plusz!) → gépeld **`.env`** → Enter. Így mindig megnyitod a `.env`-et.
