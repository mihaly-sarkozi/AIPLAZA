# Kétfaktoros azonosítás (2FA) – mire jó, hogyan működik

## Mire jó a 2FA?

A **kétfaktoros azonosítás** azt jelenti: a belépéshez **két különböző „dolog”** kell, nem csak a jelszó.

- **1. faktor:** valami, amit **tudsz** – pl. jelszó (vagy PIN).
- **2. faktor:** valami, amit **megvan nálad** (telefon, email) vagy **ami te vagy** (ujjlenyomat).

**Miért jó?**

- Ha valaki **ellopja vagy kiköveti a jelszavad**, önmagában a jelszó **nem elég** a belépéshez: kell még a második faktor (pl. a telefonodra/emailre érkező kód).
- Így **csökkenti a kockázatot**, hogy egy kiszivárgott jelszóval belépjenek a fiókodba (phishing, adatbázis szivárgás, keylogger stb. ellen).

Röviden: **2FA = extra réteg: jelszó + egy másik bizonyíték**, hogy tényleg te vagy.

---

## Hogyan működik általában?

1. **Beállítás:** A felhasználó bekapcsolja a 2FA-t (pl. beállításokban). A rendszer tárolja, hogy ehhez a userhez kell második faktor.
2. **Belépés:**
   - A user megadja az **email + jelszót** (1. faktor).
   - Ha ez rendben, a rendszer **kiküldi a 2. faktort** (pl. kódot emailben vagy SMS-ben, vagy push értesítés az alkalmazásban).
   - A user megadja a **kódot** (vagy jóváhagyja a push-t).
   - Ha a kód/approval is jó → belépés sikeres.

A kód általában **egyszer használható** és **rövid ideig érvényes** (pl. 5–10 perc), hogy ne lehessen utólag újra felhasználni.

---

## Hogyan működik az AIPLAZA-ban?

### Beállítás

- A **beállítások** (settings) táblában van egy kulcs: **`two_factor_enabled`** (pl. `"true"` / `"false"`).
- A **SettingsService** ezt olvassa: `is_two_factor_enabled()`.
- A user a **settings** API-n (pl. PUT beállítás) **bekapcsolhatja** a 2FA-t; ekkor a rendszer eltárolja, hogy ehhez a (globális vagy user-specifikus) beállításhoz kell második faktor.

### Belépés (login) folyamat

1. **POST /api/auth/login** – body: `email`, `password`, opcionálisan `two_factor_code`.
2. **LoginService.login():**
   - Megnézi, létezik-e a user, aktív-e, **helyes-e a jelszó**.
   - Ha a jelszó rossz → security log, 401.
   - Ha a jelszó **helyes** és a **2FA be van kapcsolva** (`settings_service.is_two_factor_enabled()`):
     - **Ha nincs `two_factor_code` a kérésben:**  
       A **TwoFactorService** generál egy **6 jegyű kódot**, **eltárolja** (two_factor_codes tábla, lejárat pl. 10 perc), és **emailben kiküldi** a usernek.  
       A login **nem ad vissza** access/refresh tokent, hanem egy válasz, ami jelzi: **„Kétfaktoros kód szükséges”** (pl. `TwoFactorRequiredResp`). A kliens ekkor megkéri a usert a kód megadására, majd **újra hívja a login-t** ugyanazzal az email/jelszóval + a **two_factor_code**-dal.
     - **Ha van `two_factor_code`:**  
       A **TwoFactorService.verify_code(user_id, code)** ellenőrzi: van-e érvényes, nem használt, nem lejárt kód ehhez a userhez. Ha igen, **megjelöli használtként**, és a login tovább fut (session, access + refresh token). Ha nem → security log, 401.
   - Ha a 2FA nincs bekapcsolva, vagy a kód is rendben → **sikeres belépés**: access token + refresh cookie.

### Összefoglalva az appban

| Lépés | Hol történik | Mit csinál |
|-------|--------------|------------|
| 2FA be van kapcsolva? | SettingsService | `is_two_factor_enabled()` → settings tábla `two_factor_enabled` |
| Kód küldése | TwoFactorService | `create_and_send_code()` → új 6 jegyű kód, DB-be mentés, email küldés |
| Kód ellenőrzése | TwoFactorService | `verify_code()` → get_valid_code, majd mark_as_used |
| Login ágak | LoginService | jelszó OK + (2FA ki VAGY 2FA be és kód OK) → token; különben 401 vagy TwoFactorRequired |

A kód **egyszer használatos** (mark_as_used), és **lejár** (expires_at, pl. 10 perc); ezt a **TwoFactorRepository** és a **TwoFactorCode** domain objektum kezeli.

---

## Rövid összefoglaló

- **Mire jó a 2FA:** A jelszó ellopása/kiadása önmagában ne legyen elég a belépéshez; kell egy második bizonyíték (pl. emailre érkező kód).
- **Hogyan működik:** 1. Jelszó ellenőrzése. 2. Ha 2FA be van kapcsolva és nincs kód → kód generálás, mentés, email küldés, válasz: „kód szükséges”. 3. Következő login ugyanazzal a jelszóval + kóddal → kód ellenőrzés, ha OK → belépés.
- **Az AIPLAZA-ban:** A második faktor egy **emailben küldött, 6 jegyű, időkorlátos, egyszer használatos kód**; a bekapcsolás a settings (`two_factor_enabled`) alapján történik, a logika a **LoginService** és a **TwoFactorService** (kód generálás, küldés, ellenőrzés) rétegben van.
