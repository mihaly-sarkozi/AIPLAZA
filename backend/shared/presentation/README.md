# shared/presentation

A `shared/presentation` csomag általános backend presentation helper réteg. Jelenleg lokalizált HTTP error detail payload építést ad core és app routerek számára.

## Fő felelősség

A modul célja, hogy a routerek egységes `{code, message}` formátumú, lokalizált error detail választ tudjanak visszaadni. A nyelvet `Accept-Language` alapján választja, az üzenetet pedig a `lang.messages` ErrorCode/get_message contractból kéri le.

## Fájlok

- `__init__.py`: publikus exportfelület a `LocalizedPresenterBase` felé.
- `localized_presenter_base.py`: `lang()`, `detail_for_lang()` és `detail()` helper metódusok HTTP request alapú lokalizált válaszokhoz.

## Kapcsolódás a nagy egészhez

Jelenleg az auth és users routerek használják rate limit, login, password és profile hibák user-facing detail payloadjaihoz. Mivel nem importál auth vagy users domain típust, app routerek is használhatják ugyanarra az ErrorCode alapú formátumra.

## Boundary Értékelés

A modul shared helye indokolt, mert általános presentation utility. Ha később konkrét domain response modellek, user DTO presenter vagy app-specifikus serializer kerülne ide, azt külön modulhoz kell vinni; sharedben csak a közös prezentációs contract/helper maradjon.

## Sárközi Mihály - 2026.05.21
