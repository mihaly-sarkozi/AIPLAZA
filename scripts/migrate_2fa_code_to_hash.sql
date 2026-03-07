-- Migráció: two_factor_codes.code (nyers OTP) -> code_hash (SHA-256 hex)
-- A nyers kódokat nem tudjuk hash-elni, ezért a meglévő sorok code_hash értéke üres (érvénytelen).
-- 2026.03 - 2FA erősítés (secrets + hash tárolás)

-- 1) Új oszlop
ALTER TABLE two_factor_codes ADD COLUMN code_hash VARCHAR(64) NULL;

-- 2) Meglévő sorok: code_hash üres marad → ezek a kódok már nem lesznek érvényesek
UPDATE two_factor_codes SET code_hash = '' WHERE code_hash IS NULL;

-- 3) code_hash NOT NULL
ALTER TABLE two_factor_codes MODIFY COLUMN code_hash VARCHAR(64) NOT NULL;

-- 4) Index törlése (csak SQLAlchemy-created táblánál van ix_2fa_user_code; ha nincs, hiba esetén hagyd ki)
-- ALTER TABLE two_factor_codes DROP INDEX ix_2fa_user_code;
-- 5) Régi oszlop eltávolítása
ALTER TABLE two_factor_codes DROP COLUMN code;

-- 6) Új index a code_hash lekérdezéshez
CREATE INDEX ix_2fa_user_code_hash ON two_factor_codes (user_id, code_hash);
