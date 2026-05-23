# AIPLAZA Deployment Profiles

Ez a dokumentum a fejlesztői és preprod/prod futtatási mintát választja szét.

## 1. Dev profil

- Fájl: `docker-compose.yml`
- Cél: gyors fejlesztés
- Jellemzők:
  - backend `--reload`
  - frontend Vite dev server
  - lazább lokális beállítások

## 2. Preprod/production-szerű profil

- Fájlok:
  - `docker-compose.preprod.yml`
  - `docker/backend.prod.Dockerfile`
  - `docker/frontend.prod.Dockerfile`
- Cél: release előtti stabil futtatás
- Jellemzők:
  - backend reload nélkül
  - buildelt frontend (`pnpm build` + `pnpm preview`)
  - külön `backend-worker` service konvenció
  - explicit környezeti változók a provider és worker role kezelésére

## 3. Billing provider kapcsoló

- `BILLING_PROVIDER=simulated|stripe_test`
- `STRIPE_TEST_SECRET_KEY=<stripe_test_secret>`
- opcionális:
  - `STRIPE_TEST_CURRENCY=eur`
  - `STRIPE_TEST_PAYMENT_METHOD=pm_card_visa`

## 4. Javasolt minimum release gate

1. `pytest -m release_acceptance`
2. célzott knowledge és billing unit/integration tesztek
3. `pnpm lint` és `pnpm build` a frontendben
4. manuális QA:
   - training run és index build
   - billing settle flow (simulated + stripe_test)
   - login/refresh és role alapú oldalak
