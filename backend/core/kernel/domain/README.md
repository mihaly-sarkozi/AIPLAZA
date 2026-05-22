# core/kernel/domain

A `domain` kernel könyvtár a platform domain routing és custom domain kezelés központi rétege. Azért került ki a `core/modules` alól, mert nem önálló üzleti modul, hanem a tenant routing, tenant lifecycle és HTTP host feloldás köré épülő kernel szintű platform képesség.

## Fő felelősség

Ez a réteg a tenant elsődleges platform domainjét és custom domainjeit kezeli. Nem saját domain táblát vezet, hanem a tenant repository és verification szolgáltatásaira épít, miközben egységes policyt, service-t, routert és service registry bekötést ad a kernel runtime-nak.

## Fájlok

- `module.py`: `DomainCoreModule`, amely összerakja és platform service kulcsokon regisztrálja a domain komponenseket.
- `runtime.py`: kényelmi exportfelület a domain runtime importjaihoz.
- `dto.py`: HTTP request/response DTO-k domain rekordokhoz és overview-hoz.
- `errors.py`: typed domain service hibák.
- `ports.py`: repository és verification Protocol szerződések.
- `policies.py`: domain normalizálás, primary host és tenant lifecycle ellenőrzési policy.
- `repositories.py`: adapter a tenant repository domain műveletei fölött.
- `services.py`: custom domain application service.
- `router.py`: FastAPI endpointok `/api/platform/domain` útvonalakon.

## Kapcsolódás a nagy egészhez

Az `AppManifest` tölti be a `DomainCoreModule`-t a kötelező core komponensek közé. A domain kernel a tenant lifecycle policyre, tenant repositoryra és `TenantDomainVerificationService`-re épít, majd `PLATFORM_DOMAIN_*` service kulcsokon publikálja a routing policyt, policyt, repositoryt, verification service-t és domain service-t.

## Core/Framework Jelleg

Ez core/kernel komponens. A domain host routing, platform elsődleges domain és custom domain életciklus olyan technikai keretrendszer-funkció, amelyre több platform modul támaszkodhat, ezért nem app feature-ként van a `core/modules` alatt.

## Sárközi Mihály - 2026.05.21
