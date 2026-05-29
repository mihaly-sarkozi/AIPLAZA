// frontend/src/features/settings/components/SettingsSectionTabs.tsx
// Feladat: Legacy settings tab navigáció komponens (visszafelé kompatibilitáshoz megtartva).
// Sárközi Mihály - 2026.05.29

export type SettingsSectionKey = "security" | "preferences" | "billing" | "domains";

type SettingsSectionTabsProps = {
  sections: Array<{ key: SettingsSectionKey; label: string }>;
  activeSection: SettingsSectionKey;
  onChange: (section: SettingsSectionKey) => void;
};

export default function SettingsSectionTabs({ sections, activeSection, onChange }: SettingsSectionTabsProps) {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-2 shadow-sm">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {sections.map((section) => (
          <button
            key={section.key}
            type="button"
            onClick={() => onChange(section.key)}
            className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
              activeSection === section.key
                ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] shadow-sm"
                : "text-[var(--color-muted)] hover:bg-[var(--color-card-muted)] hover:text-[var(--color-foreground)]"
            }`}
          >
            {section.label}
          </button>
        ))}
      </div>
    </div>
  );
}
