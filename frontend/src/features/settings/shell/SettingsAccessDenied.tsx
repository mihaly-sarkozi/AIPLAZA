// frontend/src/features/settings/shell/SettingsAccessDenied.tsx
// Feladat: Jogosultság hiányában egységes settings tiltott-hozzáférés nézetet ad.
// Sárközi Mihály - 2026.05.29

type SettingsAccessDeniedProps = {
  message: string;
};

export default function SettingsAccessDenied({ message }: SettingsAccessDeniedProps) {
  return (
    <div className="p-6 min-h-full bg-[var(--color-background)]">
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded">
        {message}
      </div>
    </div>
  );
}
