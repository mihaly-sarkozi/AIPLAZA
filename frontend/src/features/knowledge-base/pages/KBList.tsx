import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { GearIcon, TrashIcon, BackpackIcon } from "@radix-ui/react-icons";
import { useTranslation } from "../../../i18n";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  useKbList,
  useCreateKbMutation,
  useUpdateKbMutation,
  useDeleteKbMutation,
  type KbItem,
} from "../hooks/useKb";

export default function KBList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { data: items = [], isLoading: loading, error: listError } = useKbList();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createFormError, setCreateFormError] = useState<string | null>(null);
  const [editFormError, setEditFormError] = useState<string | null>(null);
  const [editingKb, setEditingKb] = useState<KbItem | null>(null);
  const [deleteConfirmKb, setDeleteConfirmKb] = useState<KbItem | null>(null);
  const [deleteTypeName, setDeleteTypeName] = useState("");

  const createKbMutation = useCreateKbMutation();
  const updateKbMutation = useUpdateKbMutation();
  const deleteKbMutation = useDeleteKbMutation();
  const actionLoading =
    createKbMutation.isPending || updateKbMutation.isPending || deleteKbMutation.isPending;

  const [formData, setFormData] = useState({ name: "", description: "" });

  const error = listError ? (getApiErrorMessage(listError) ?? t("kb.errorLoad")) : null;

  useEffect(() => {
    if ((location.state as { openKbCreate?: boolean })?.openKbCreate) {
      setShowCreateModal(true);
      resetForm();
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  const resetForm = () => {
    setFormData({ name: "", description: "" });
    setCreateFormError(null);
    setEditFormError(null);
  };

  const openCreateModal = () => {
    resetForm();
    setShowCreateModal(true);
  };

  const openEditModal = (kb: KbItem) => {
    setEditingKb(kb);
    setEditFormError(null);
    setFormData({ name: kb.name, description: kb.description ?? "" });
  };

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const nameTrim = formData.name?.trim() ?? "";
    setCreateFormError(null);
    if (!nameTrim) {
      setCreateFormError(t("common.fieldRequired"));
      return;
    }
    createKbMutation.mutate(
      { name: nameTrim, description: formData.description?.trim() || undefined },
      {
        onSuccess: () => {
          toast.success(t("profile.saved"));
          setShowCreateModal(false);
          resetForm();
        },
        onError: (err: unknown) => {
          toast.error(getApiErrorMessage(err) ?? t("kb.errorCreate"));
        },
      }
    );
  };

  const handleUpdate = () => {
    if (!editingKb) return;
    const nameTrim = formData.name?.trim() ?? "";
    setEditFormError(null);
    if (!nameTrim) {
      setEditFormError(t("common.fieldRequired"));
      return;
    }
    updateKbMutation.mutate(
      { uuid: editingKb.uuid, name: nameTrim, description: formData.description?.trim() || undefined },
      {
        onSuccess: () => {
          toast.success(t("profile.saved"));
          setEditingKb(null);
          resetForm();
        },
        onError: (err: unknown) => {
          toast.error(getApiErrorMessage(err) ?? t("kb.errorUpdate"));
        },
      }
    );
  };

  const handleDelete = () => {
    if (!deleteConfirmKb) return;
    if (deleteTypeName.trim() !== deleteConfirmKb.name) {
      toast.error(t("kb.deleteConfirmMismatch"));
      return;
    }
    deleteKbMutation.mutate(
      { uuid: deleteConfirmKb.uuid, confirm_name: deleteTypeName.trim() },
      {
        onSuccess: () => {
          toast.success(t("common.delete") + " – OK");
          setDeleteConfirmKb(null);
          setDeleteTypeName("");
        },
        onError: (err: unknown) => {
          toast.error(getApiErrorMessage(err) ?? t("kb.errorDelete"));
        },
      }
    );
  };

  if (loading) {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
        {t("common.loading")}
      </div>
    );
  }

  return (
    <div className="p-6 min-h-full bg-[var(--color-background)]">
      <div className="flex flex-nowrap items-center gap-3 mb-6 min-w-0 w-full">
        <h1 className="min-w-0 flex-1 text-xl sm:text-2xl md:text-3xl font-bold truncate text-[var(--color-foreground)]" title={t("kb.title")}>
          {t("kb.title")}
        </h1>
        <button
          type="button"
          onClick={openCreateModal}
          disabled={actionLoading}
          className="ml-auto shrink-0 bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] px-3 py-2 rounded text-xs sm:text-sm whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {t("kb.newKb")}
        </button>
      </div>

      {error && (
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded mb-4">
          {error}
        </div>
      )}

      {/* Asztop: táblázat */}
      <div className="hidden md:block bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-[var(--color-table-head)]">
            <tr>
              <th className="p-3 text-left text-[var(--color-foreground)]">{t("kb.tableName")}</th>
              <th className="p-3 text-left text-[var(--color-foreground)]">{t("kb.tableDescription")}</th>
              <th className="p-3 text-right text-[var(--color-foreground)] w-0 whitespace-nowrap">{t("kb.tableActions")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((kb) => (
              <tr key={kb.uuid} className="border-t border-[var(--color-border)]">
                <td className="p-3 text-[var(--color-foreground)]">{kb.name}</td>
                <td className="p-3 text-[var(--color-muted)]">{kb.description ?? "—"}</td>
                <td className="p-3 text-right w-0 whitespace-nowrap">
                  <div className="flex gap-2 justify-end items-center">
                    <button
                      type="button"
                      title={t("kb.actionEdit")}
                      className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:opacity-80"
                      onClick={() => openEditModal(kb)}
                      disabled={actionLoading}
                      aria-label={t("kb.actionEdit")}
                    >
                      <GearIcon className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      title={t("kb.actionDelete")}
                      className="p-2 rounded text-white bg-red-500 hover:bg-red-600"
                      onClick={() => {
                        setDeleteConfirmKb(kb);
                        setDeleteTypeName("");
                      }}
                      disabled={actionLoading}
                      aria-label={t("kb.actionDelete")}
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      title={t("kb.actionTrain")}
                      className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:opacity-80"
                      onClick={() => navigate(`/kb/train/${kb.uuid}`)}
                      disabled={actionLoading}
                      aria-label={t("kb.actionTrain")}
                    >
                      <BackpackIcon className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Keskeny: kártyák */}
      <div className="md:hidden space-y-3">
        {items.map((kb) => (
          <div key={kb.uuid} className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-4 space-y-2">
            <div className="font-medium text-[var(--color-foreground)]">{kb.name}</div>
            <div className="text-sm text-[var(--color-muted)]">{kb.description ?? "—"}</div>
            <div className="flex gap-2 justify-end pt-2">
              <button
                type="button"
                title={t("kb.actionEdit")}
                className="p-2 rounded hover:bg-[var(--color-border)] disabled:opacity-50"
                onClick={() => openEditModal(kb)}
                disabled={actionLoading}
                aria-label={t("kb.actionEdit")}
              >
                <GearIcon className="w-4 h-4" />
              </button>
              <button
                type="button"
                title={t("kb.actionDelete")}
                className="p-2 rounded text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30"
                onClick={() => {
                  setDeleteConfirmKb(kb);
                  setDeleteTypeName("");
                }}
                disabled={actionLoading}
                aria-label={t("kb.actionDelete")}
              >
                <TrashIcon className="w-4 h-4" />
              </button>
              <button
                type="button"
                title={t("kb.actionTrain")}
                className="p-2 rounded hover:bg-[var(--color-border)] disabled:opacity-50"
                onClick={() => navigate(`/kb/train/${kb.uuid}`)}
                disabled={actionLoading}
                aria-label={t("kb.actionTrain")}
              >
                <BackpackIcon className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg w-96 shadow-lg">
            <h2 className="text-2xl font-bold mb-4 text-[var(--color-foreground)]">{t("kb.modalNewTitle")}</h2>
            <p className="text-sm text-[var(--color-muted)] mb-4">{t("kb.modalNewHint")}</p>
            {createFormError && (
              <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
                {createFormError}
              </div>
            )}
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("kb.labelName")}{t("common.required")}</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => {
                    setFormData({ ...formData, name: e.target.value });
                    if (createFormError) setCreateFormError(null);
                  }}
                  className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
                  placeholder={t("kb.placeholderName")}
                  maxLength={200}
                  required
                />
              </div>
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("kb.labelDescription")}</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded h-28 resize-y"
                  placeholder={t("kb.placeholderDescription")}
                />
              </div>
              <div className="flex gap-2 mt-6 justify-end">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    resetForm();
                  }}
                  disabled={actionLoading}
                  className="bg-[var(--color-card)] hover:opacity-80 text-[var(--color-foreground)] border border-[var(--color-border)] px-4 py-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] px-4 py-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {actionLoading ? t("common.loading") : t("common.save")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editingKb && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg w-96 shadow-lg">
            <h2 className="text-2xl font-bold mb-4 text-[var(--color-foreground)]">{t("kb.modalEditTitle")}</h2>
            {editFormError && (
              <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
                {editFormError}
              </div>
            )}
            <div className="space-y-4">
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("kb.labelName")}{t("common.required")}</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => {
                    setFormData({ ...formData, name: e.target.value });
                    if (editFormError) setEditFormError(null);
                  }}
                  className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
                  placeholder={t("kb.placeholderName")}
                  maxLength={200}
                  required
                />
              </div>
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("kb.labelDescription")}</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded h-28 resize-y"
                  placeholder={t("kb.placeholderDescription")}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                type="button"
                onClick={() => {
                  setEditingKb(null);
                  resetForm();
                }}
                disabled={actionLoading}
                className="px-4 py-2 rounded text-[var(--color-foreground)] hover:opacity-80 bg-[var(--color-card)] border border-[var(--color-border)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={handleUpdate}
                disabled={actionLoading}
                className="px-4 py-2 rounded bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading ? t("common.loading") : t("common.save")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirm */}
      {deleteConfirmKb && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg w-96 shadow-lg">
            <p className="text-[var(--color-foreground)] mb-2">{t("kb.confirmDelete")}</p>
            <p className="text-sm text-[var(--color-muted)] mb-3">
              {t("kb.confirmDeleteTypeName").replace("{{name}}", deleteConfirmKb.name)}
            </p>
            <input
              type="text"
              value={deleteTypeName}
              onChange={(e) => setDeleteTypeName(e.target.value)}
              placeholder={deleteConfirmKb.name}
              className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded mb-4"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setDeleteConfirmKb(null);
                  setDeleteTypeName("");
                }}
                disabled={actionLoading}
                className="px-4 py-2 rounded text-[var(--color-foreground)] hover:opacity-80 bg-[var(--color-card)] border border-[var(--color-border)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={actionLoading || deleteTypeName.trim() !== deleteConfirmKb.name}
                className="px-4 py-2 rounded bg-red-500 hover:bg-red-600 text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading ? t("common.loading") : t("common.delete")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
