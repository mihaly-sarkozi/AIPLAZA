import { useTranslation } from "../i18n";
import { useLocation } from "react-router-dom";

export default function Footer({ suppressChatWarning = false }: { suppressChatWarning?: boolean }) {
  const { t } = useTranslation();
  const location = useLocation();
  const isChat = location.pathname === "/chat";
  const showChatWarning = isChat && !suppressChatWarning;
  return (
    <footer
      className="mt-auto w-full bg-[var(--color-background)] text-[var(--color-muted)] p-3 text-xs flex flex-col items-center justify-center gap-1 shrink-0 sm:flex-row sm:justify-between sm:gap-2"
      style={{ contentVisibility: "auto" }}
    >
      {showChatWarning ? (
        <span className="order-1 text-center sm:order-2">
          {t("chat.footerWarning")}
        </span>
      ) : null}
      <span className={`${showChatWarning ? "order-2 sm:order-1" : "order-1"} text-center lowercase sm:text-left`}>
        © {new Date().getFullYear()} – {t("footer.rights")}
      </span>
      <span className={`${showChatWarning ? "order-3" : "order-2"} font-medium`}>
        {t("app.name")}
      </span>
    </footer>
  );
}