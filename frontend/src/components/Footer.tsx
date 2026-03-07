import { useTranslation } from "../i18n";

export default function Footer() {
  const { t } = useTranslation();
  return (
    <footer
      className="mt-auto w-full bg-[var(--color-background)] text-[var(--color-muted)] p-3 text-xs border-t border-[var(--color-border)] flex flex-wrap items-center justify-between gap-2 shrink-0"
      style={{ contentVisibility: "auto" }}
    >
      <span className="text-center sm:text-left lowercase">
        © {new Date().getFullYear()} – {t("footer.rights")}
      </span>
      <span className="font-medium">
        {t("app.name")}
      </span>
    </footer>
  );
}