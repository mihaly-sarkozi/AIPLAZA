-- Tenant status + config + domain→tenant nyilvántartás (PostgreSQL, public schema).
-- Futtatás: psql $DATABASE_URL -f scripts/tenant_status_config_domains.sql
-- 2026.03 – Sárközi Mihály

-- 1) tenants.is_active (tenant status cache forrás)
ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- 2) tenant_configs – csomag, feature_flags, limits (tenant config cache forrás)
CREATE TABLE IF NOT EXISTS public.tenant_configs (
  id SERIAL PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE UNIQUE,
  package VARCHAR(64) NOT NULL DEFAULT 'free',
  feature_flags JSONB NOT NULL DEFAULT '{}',
  limits JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ix_tenant_configs_tenant_id ON public.tenant_configs(tenant_id);

-- 3) tenant_domains – domain → tenant nyilvántartás (regisztráció/ellenőrzés + domain2tenant cache forrás)
CREATE TABLE IF NOT EXISTS public.tenant_domains (
  id SERIAL PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
  domain VARCHAR(255) NOT NULL,
  verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_domains_domain ON public.tenant_domains(domain);
CREATE INDEX IF NOT EXISTS ix_tenant_domains_tenant_id ON public.tenant_domains(tenant_id);
CREATE INDEX IF NOT EXISTS ix_tenant_domains_domain ON public.tenant_domains(domain);
