import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "../../../api/axiosClient";
import { useTranslation } from "../../../i18n";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";

export default function ConfirmEmailPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = useMemo(() => searchParams.get("token") || "", [searchParams]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setStatus("error");
      setMessage(t("profile.verifyEmailMissingToken"));
      return;
    }
    api
      .post("/auth/confirm-email", undefined, { params: { token } })
      .then(() => {
        if (cancelled) return;
        setStatus("success");
        setMessage(t("profile.verifyEmailSuccess"));
      })
      .catch((error) => {
        if (cancelled) return;
        setStatus("error");
        setMessage(getApiErrorMessage(error) ?? t("profile.verifyEmailMissingToken"));
      });
    return () => {
      cancelled = true;
    };
  }, [t, token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] text-[var(--color-foreground)] px-4">
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-8 rounded-lg shadow-sm w-full max-w-md text-center">
        <h1 className="text-2xl font-bold mb-4">{t("profile.verifyEmailTitle")}</h1>
        <p className="text-sm text-[var(--color-muted)] mb-6">
          {status === "loading" ? t("common.loading") : message}
        </p>
        <Link
          to="/login"
          className="inline-flex w-full justify-center rounded-md bg-[var(--color-primary)] px-4 py-3 font-semibold text-[var(--color-on-primary)] hover:opacity-90"
        >
          {t("forgot.backToLogin")}
        </Link>
      </div>
    </div>
  );
}
