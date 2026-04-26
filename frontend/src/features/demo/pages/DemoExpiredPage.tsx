import { useMemo } from "react";
import { Link } from "react-router-dom";

import { getTenantBaseDomain } from "../../../utils/domain";

function demoUrl(): string {
  const scheme = window.location.protocol || "http:";
  const host = getTenantBaseDomain();
  const port = window.location.port ? `:${window.location.port}` : "";
  return `${scheme}//${host}${port}/demo`;
}

export default function DemoExpiredPage() {
  const continueUrl = useMemo(() => demoUrl(), []);

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
      <header className="border-b border-[var(--color-border)] px-4 py-4">
        <Link to="/demo" className="text-sm text-[var(--color-muted-foreground)] hover:underline">
          ← Vissza a demo oldalra
        </Link>
      </header>
      <main className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-lg w-full text-center space-y-4">
          <h1 className="text-3xl font-bold">A Demo verzió véget ért</h1>
          <p className="text-[var(--color-muted-foreground)]">
            Ha szeretnéd folytatni, kattints a gombra.
          </p>
          <a
            href={continueUrl}
            className="inline-flex items-center justify-center rounded bg-[var(--color-primary)] px-6 py-3 font-medium text-white"
          >
            Szeretném folytatni
          </a>
        </div>
      </main>
    </div>
  );
}
