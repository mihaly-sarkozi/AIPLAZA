# shared/validation

A `shared/validation` csomag közös backend validációs utility réteg. Email formátum-ellenőrzést és jelszóerősségi policy validációt ad core, admin és app komponenseknek.

## Fő felelősség

Ez a modul olyan bemeneti validációkat tartalmaz, amelyek több funkcionális terület szerződésében is azonosak. Az email validáció best-effort formátum- és hosszellenőrzés, a password validáció pedig `basic`, `standard` és `high` policy szinteket kezel lazy settings olvasással.

## Fájlok

- `__init__.py`: publikus exportfelület az email és password validation contractokhoz.
- `email.py`: `is_valid_email()` és email hosszkorlátok központi használatra.
- `password.py`: `PasswordPolicy`, policy szintek, hosszkorlátok, `get_password_policy()`, `validate_password_policy()` és kompatibilis `validate_password_strength()` alias.

## Kapcsolódás a nagy egészhez

A users request DTO-k az email validációt használják admin user létrehozásnál és módosításnál. A platform admin service a password validációval ellenőrzi bootstrap, meghívási és jelszócsere folyamatok jelszavait. A korábbi `core.modules.auth.domain.password_policy` importútvonal kompatibilitási shimként megmaradt, de a kanonikus implementáció itt található.

## Boundary Értékelés

A shared hely indokolt, mert az email és password szabályok nem egyetlen domain modulhoz tartoznak: tenant user és platform admin folyamatok is ugyanazt a contractot használják. Új validáció csak akkor kerüljön ide, ha több modul közös bemeneti contractja; domain-specifikus üzleti szabály maradjon az adott modul request/service rétegében.

## Sárközi Mihály - 2026.05.21
