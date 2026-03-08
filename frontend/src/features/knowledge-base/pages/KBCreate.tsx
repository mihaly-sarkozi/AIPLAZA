import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { useCreateKbMutation } from "../hooks/useKb";

export default function KBCreate() {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const createKbMutation = useCreateKbMutation();

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    createKbMutation.mutate(
      { name: name.trim(), description: description.trim() || undefined },
      {
        onSuccess: () => {
          toast.success(t("profile.saved"));
          navigate("/kb");
        },
        onError: (err: unknown) => {
          setError(getApiErrorMessage(err) ?? t("kb.errorCreate"));
        },
      }
    );
  };

  return (
    <div className="p-6 min-h-full bg-[var(--color-background)] max-w-xl mx-auto">
      <h1 className="text-xl sm:text-2xl md:text-3xl font-bold mb-6 text-[var(--color-foreground)]">
        {t("kb.createPageTitle")}
      </h1>

      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      <form className="flex flex-col gap-5" onSubmit={handleSave}>
        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("kb.labelName")}{t("common.required")}</label>
          <input
            type="text"
            maxLength={200}
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full p-3 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
          />
        </div>

        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("kb.labelDescription")}</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full p-3 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] h-32 resize-y"
          />
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => navigate("/kb")}
            className="px-4 py-2 rounded text-[var(--color-foreground)] hover:opacity-80 bg-[var(--color-card)] border border-[var(--color-border)]"
          >
            {t("common.cancel")}
          </button>
          <button
            type="submit"
            className="bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] py-3 px-4 rounded disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={createKbMutation.isPending}
          >
            {createKbMutation.isPending ? t("common.loading") : t("common.save")}
          </button>
        </div>
      </form>
    </div>
  );
}
