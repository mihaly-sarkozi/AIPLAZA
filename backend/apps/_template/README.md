# App Module Template

Ez a mappa a hivatalos backend app-modul referencia.

Minimum:
- `module.py`
- `web/module.tsx`

Ajánlott:
- `dependencies.py`
- `router/`
- `service/`

Opcionális:
- `container/`
- `domain/`
- `hooks.py` vagy `tenant_hooks.py`
- `infrastructure.py`
- `models/`
- `policies.py`
- `ports/`
- `repositories/`
- `runtime.py`
- `tests/`
- `workflows.py`

Import szabály:
- `core` felől csak a `apps.contracts.public_api.PUBLIC_CORE_API_PREFIXES` allowlist használható.
- Másik appból csak saját namespace vagy a közös `apps.contracts`, `apps.di`, `apps.state_keys` felületek importálhatók.

Ne használd:
- `core.platform.bootstrap.*`
- `core.platform.*` belső runtime vagy assembly modulok
- másik app `service`, `repository`, `router`, `runtime` implementációját
