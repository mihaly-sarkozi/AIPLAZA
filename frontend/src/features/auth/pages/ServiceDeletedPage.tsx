import { useTranslation } from "../../../i18n";

export default function ServiceDeletedPage() {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div className="max-w-2xl text-center">
        <h1 className="text-2xl md:text-3xl font-semibold mb-4">{t("serviceDeleted.title")}</h1>
        <p className="text-[var(--color-muted-foreground)]">{t("serviceDeleted.description")}</p>
      </div>
    </div>
  );
}
