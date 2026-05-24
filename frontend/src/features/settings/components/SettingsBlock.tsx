import type { ReactNode } from "react";

export default function SettingsBlock({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm">
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-[var(--color-foreground)]">{title}</h2>
        {description ? <p className="mt-1 text-sm text-[var(--color-muted)]">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}
