# core/kernel/deps

## Feladat
A `deps` könyvtár a kernel runtime dependency hozzáférési rétege. A runtime során összerakott service-eket, repositorykat és factorykat egy központi registryből teszi elérhetővé stabil facade API-n keresztül.

## Fájlok
- `registry.py`: A tényleges `KernelDependencyRegistry` és a register/get függvények helye. Itt vannak a service, repository és factory dependency factory helper függvények is.
- `facade.py`: A public importfelület. Re-exportálja a registry API-t, és lazy módon továbbadja a tenant HTTP dependencyket a `http/tenant_dependencies.py` modulból.
- `__init__.py`: Kompatibilitási csomagexport, amely a facade API-t teszi elérhetővé rövidebb importútvonalon.

## Kapcsolódás
A `runtime/kernel_di_wiring.py` tölti fel a registryt az AppContainer által összerakott service-ekkel és repositorykkal. Routerek, middleware-ek, core modulok, app modulok és tesztek a `core.kernel.deps.facade` függvényein keresztül kérik le ezeket. A modulregisztráció közben a `bootstrap/modules.py` is ezen keresztül publikál platform service-eket.

## Fontos elv
Új kód lehetőleg a `core.kernel.deps.facade` public API-t használja. A `registry.py` belső tároló és alacsonyabb szintű implementáció; közvetlen importja csak kernel wiring vagy célzott teszt esetén indokolt.

## Sárközi Mihály - 2026.05.21
