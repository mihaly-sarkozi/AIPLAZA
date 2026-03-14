import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  useKbList,
  useUpdateKbMutation,
  type PersonalDataMode,
  type PersonalDataSensitivity,
} from "../hooks/useKb";

const PERSONAL_DATA_MODES: PersonalDataMode[] = [
  "no_personal_data",
  "allowed_not_to_ai",
  "with_confirmation",
  "no_pii_filter",
];
const PERSONAL_DATA_SENSITIVITIES: PersonalDataSensitivity[] = ["weak", "medium", "strong"];

export default function KBEdit() {
  const { t } = useTranslation();
  const { uuid } = useParams();
  const navigate = useNavigate();
  const { data: kbList = [], isLoading: kbListLoading } = useKbList();
  const updateKbMutation = useUpdateKbMutation();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [personalDataMode, setPersonalDataMode] = useState<PersonalDataMode>("no_personal_data");
  const [personalDataSensitivity, setPersonalDataSensitivity] =
    useState<PersonalDataSensitivity>("medium");
  const [error, setError] = useState("");

  const kb = uuid ? kbList.find((x) => x.uuid === uuid) : null;

  useEffect(() => {
    if (!uuid) return;
    if (!kbListLoading && !kb) {
      navigate("/kb");
      return;
    }
    if (kb) {
      setName(kb.name);
      setDescription(kb.description ?? "");
      setPersonalDataMode(
        (kb.personal_data_mode as PersonalDataMode) ?? "no_personal_data"
      );
      setPersonalDataSensitivity(
        (kb.personal_data_sensitivity as PersonalDataSensitivity) ?? "medium"
      );
    }
  }, [kb, kbListLoading, uuid, navigate]);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!uuid) return;
    setError("");
    updateKbMutation.mutate(
      {
        uuid,
        name: name.trim(),
        description: description.trim() || undefined,
        personal_data_mode: personalDataMode,
        personal_data_sensitivity: personalDataSensitivity,
      },
      {
        onSuccess: () => {
          toast.success(t("profile.saved"));
          navigate("/kb");
        },
        onError: (err: unknown) => {
          setError(getApiErrorMessage(err) ?? t("kb.errorUpdate"));
        },
      }
    );
  };

  return (
    <div className="p-6 min-h-full bg-[var(--color-background)] max-w-xl mx-auto">
      <h1 className="text-xl sm:text-2xl md:text-3xl font-bold mb-6 text-[var(--color-foreground)]">
        {t("kb.editPageTitle")}
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

        <div className="p-3 rounded bg-[var(--color-card)] border border-[var(--color-border)] text-sm text-[var(--color-muted)]">
          {t("kb.personalDataDescription")}
        </div>

        <div>
          <label className="block mb-1 text-[var(--color-label)]">
            {t("kb.personalDataModeLabel")}{t("common.required")}
          </label>
          <select
            required
            value={personalDataMode}
            onChange={(e) => setPersonalDataMode(e.target.value as PersonalDataMode)}
            className="w-full p-3 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
          >
            <option value="no_personal_data">{t("kb.personalDataModeNo")}</option>
            <option value="allowed_not_to_ai">{t("kb.personalDataModeAllowed")}</option>
            <option value="with_confirmation">{t("kb.personalDataModeConfirm")}</option>
            <option value="no_pii_filter">{t("kb.personalDataModeDisabled")}</option>
          </select>
        </div>

        <div>
          <label className="block mb-1 text-[var(--color-label)]">
            {t("kb.personalDataSensitivityLabel")}{t("common.required")}
          </label>
          <select
            required
            value={personalDataSensitivity}
            onChange={(e) =>
              setPersonalDataSensitivity(e.target.value as PersonalDataSensitivity)
            }
            className="w-full p-3 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
          >
            <option value="weak">{t("kb.personalDataSensitivityWeak")}</option>
            <option value="medium">{t("kb.personalDataSensitivityMedium")}</option>
            <option value="strong">{t("kb.personalDataSensitivityStrong")}</option>
          </select>
          <p className="mt-1 text-xs text-[var(--color-muted)]">
            {t("kb.personalDataSensitivityHelp")}
          </p>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => navigate("/kb")}
            className="px-4 py-2 rounded text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)] bg-[var(--color-card)] border border-[var(--color-border)]"
          >
            {t("common.cancel")}
          </button>
          <button
            type="submit"
            className="bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] py-3 px-4 rounded disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={updateKbMutation.isPending}
          >
            {updateKbMutation.isPending ? t("common.loading") : t("common.save")}
          </button>
        </div>
      </form>
    </div>
  );
}
