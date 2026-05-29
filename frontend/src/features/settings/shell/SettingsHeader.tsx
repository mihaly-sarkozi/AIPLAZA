// frontend/src/features/settings/shell/SettingsHeader.tsx
// Feladat: A settings oldal közös fejléce (eyebrow, title, intro) a shell rétegben.
// Sárközi Mihály - 2026.05.29

import PageHeader from "../../../components/ui/PageHeader";

type SettingsHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
};

export default function SettingsHeader({ eyebrow, title, description }: SettingsHeaderProps) {
  return <PageHeader eyebrow={eyebrow} title={title} description={description} />;
}
