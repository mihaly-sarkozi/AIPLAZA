import { useEffect, useState, useMemo, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { SavedModal } from "../../../components/SavedModal";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  useKbList,
  useCreateKbMutation,
  useUpdateKbMutation,
  useDeleteKbMutation,
  useKbPermissions,
  useSetKbPermissionsMutation,
  type KbItem,
  type PersonalDataMode,
} from "../hooks/useKb";
import { useUsers } from "../../users/hooks/useUsers";
import { useAuthStore } from "../../../store/authStore";

const PERM_NONE = "none";
const PERM_USE = "use";
const PERM_TRAIN = "train";

export default function KBList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const currentUserId = useAuthStore((s) => s.user?.id);
  const canManage = useAuthStore((s) => s.user?.role === "admin" || s.user?.role === "owner");
  const isOwner = useAuthStore((s) => s.user?.role === "owner");
  const { data: items = [], isLoading: loading, error: listError } = useKbList();
  const { data: users = [] } = useUsers({ enabled: canManage });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createFormError, setCreateFormError] = useState<string | null>(null);
  const [editFormError, setEditFormError] = useState<string | null>(null);
  const [editingKb, setEditingKb] = useState<KbItem | null>(null);
  const [settingsKb, setSettingsKb] = useState<KbItem | null>(null);
  const [deleteConfirmKb, setDeleteConfirmKb] = useState<KbItem | null>(null);
  const [deleteTypeName, setDeleteTypeName] = useState("");
  const [savedModalOpen, setSavedModalOpen] = useState(false);

  const createKbMutation = useCreateKbMutation();
  const updateKbMutation = useUpdateKbMutation();
  const deleteKbMutation = useDeleteKbMutation();
  const setPermissionsMutation = useSetKbPermissionsMutation();
  const actionLoading =
    createKbMutation.isPending ||
    updateKbMutation.isPending ||
    deleteKbMutation.isPending ||
    setPermissionsMutation.isPending;

  const [formData, setFormData] = useState({ name: "", description: "" });
  /** Create modal: user_id -> permission (none/use/train) */
  const [createPermissions, setCreatePermissions] = useState<Record<number, string>>({});
  /** Beállítás modál: user_id -> permission; API-ból szinkronizálva */
  const [settingsPermissions, setSettingsPermissions] = useState<Record<number, string>>({});
  /** Szerkesztés modál: személyes adat mód (keresés erősség egyelőre nincs a UI-ban, API-nak medium) */
  const [editingPersonalDataMode, setEditingPersonalDataMode] = useState<PersonalDataMode>("no_personal_data");

  const { data: settingsPermsList = [], isLoading: settingsPermsLoading } = useKbPermissions(
    settingsKb?.uuid ?? undefined,
    { enabled: !!settingsKb }
  );
  const settingsPermsSyncedUuid = useRef<string | null>(null);

  useEffect(() => {
    if (!settingsKb || settingsPermsList.length === 0) return;
    if (settingsPermsSyncedUuid.current === settingsKb.uuid) return;
    settingsPermsSyncedUuid.current = settingsKb.uuid;
    const next: Record<number, string> = {};
    for (const p of settingsPermsList) {
      next[p.user_id] = p.permission;
    }
    setSettingsPermissions(next);
  }, [settingsKb?.uuid, settingsPermsList]);


  const usersWithPermsCreate = useMemo(() => {
    return (users as Array<{ id: number; email: string; name?: string | null }>)
      .filter((u) => u.id != null)
      .map((u) => ({
        id: u.id!,
        email: u.email,
        name: u.name ?? null,
        permission: createPermissions[u.id!] ?? PERM_NONE,
      }));
  }, [users, createPermissions]);

  const usersWithPermsSettings = useMemo(() => {
    return settingsPermsList.map((p) => ({
      id: p.user_id,
      email: p.email,
      name: p.name ?? null,
      permission: settingsPermissions[p.user_id] ?? p.permission,
      role: p.role ?? "user",
    }));
  }, [settingsPermsList, settingsPermissions]);

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
    setCreatePermissions({});
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
    setEditingPersonalDataMode((kb.personal_data_mode as PersonalDataMode) ?? "no_personal_data");
  };

  const openSettingsModal = (kb: KbItem) => {
    setSettingsKb(kb);
    setSettingsPermissions({});
  };

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const nameTrim = formData.name?.trim() ?? "";
    setCreateFormError(null);
    if (!nameTrim) {
      setCreateFormError(t("common.fieldRequired"));
      return;
    }
    const permissions = usersWithPermsCreate
      .filter((u) => u.permission && u.permission !== PERM_NONE)
      .map((u) => ({ user_id: u.id, permission: u.permission }));
    createKbMutation.mutate(
      {
        name: nameTrim,
        description: formData.description?.trim() || undefined,
        permissions: permissions.length ? permissions : undefined,
      },
      {
        onSuccess: () => {
          setSavedModalOpen(true);
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
      {
        uuid: editingKb.uuid,
        name: nameTrim,
        description: formData.description?.trim() || undefined,
        personal_data_mode: editingPersonalDataMode,
        personal_data_sensitivity: "medium",
      },
      {
        onSuccess: () => {
          setSavedModalOpen(true);
          setEditingKb(null);
          resetForm();
        },
        onError: (err: unknown) => {
          toast.error(getApiErrorMessage(err) ?? t("kb.errorUpdate"));
        },
      }
    );
  };

  const handleSaveSettings = () => {
    if (!settingsKb) return;
    const permissions = usersWithPermsSettings.map((u) => ({ user_id: u.id, permission: u.permission }));
    setPermissionsMutation.mutate(
      { uuid: settingsKb.uuid, permissions },
      {
        onSuccess: () => {
          setSavedModalOpen(true);
          setSettingsKb(null);
        },
        onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("kb.errorPermissions")),
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
        {isOwner && (
          <button
            type="button"
            onClick={openCreateModal}
            disabled={actionLoading}
            className="ml-auto shrink-0 bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] px-3 py-2 rounded text-xs sm:text-sm whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t("kb.newKb")}
          </button>
        )}
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
              <th className="p-3 text-left text-xs font-normal text-[var(--color-foreground)]">{t("kb.tableName")}</th>
              <th className="p-3 text-left text-xs font-normal text-[var(--color-foreground)]">{t("kb.tableDescription")}</th>
              <th className="p-3 text-right text-xs font-normal text-[var(--color-foreground)] w-0 whitespace-nowrap">{t("kb.tableActions")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((kb) => (
              <tr key={kb.uuid} className="border-t border-[var(--color-border)]">
                <td className="p-3 text-[var(--color-foreground)]">{kb.name}</td>
                <td className="p-3 text-[var(--color-muted)]">{kb.description ?? "—"}</td>
                <td className="p-3 text-right w-0 whitespace-nowrap">
                  <div className="flex gap-2 justify-end items-center">
                    {isOwner && (
                      <button
                        type="button"
                        title={t("kb.actionDelete")}
                        className="p-2 rounded text-white bg-red-500 hover:bg-red-600 mr-8 disabled:opacity-50"
                        onClick={() => {
                          setDeleteConfirmKb(kb);
                          setDeleteTypeName("");
                        }}
                        disabled={actionLoading}
                        aria-label={t("kb.actionDelete")}
                      >
                        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                      </button>
                    )}
                    {canManage && (
                      <button
                        type="button"
                        title={t("kb.actionPermissions")}
                        className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50"
                        onClick={() => openSettingsModal(kb)}
                        disabled={actionLoading}
                        aria-label={t("kb.actionPermissions")}
                      >
                        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
                      </button>
                    )}
                    {kb.can_train && (
                      <button
                        type="button"
                        title={t("kb.actionTrain")}
                        className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50"
                        onClick={() => navigate(`/kb/train/${kb.uuid}`)}
                        disabled={actionLoading}
                        aria-label={t("kb.actionTrain")}
                      >
                        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
                      </button>
                    )}
{canManage && kb.can_train && (
                        <button
                        type="button"
                        title={t("kb.actionEdit")}
                        className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50"
                        onClick={() => openEditModal(kb)}
                        disabled={actionLoading}
                        aria-label={t("kb.actionEdit")}
                      >
                        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                      </button>
                    )}
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
            <div className="flex gap-2 justify-end pt-2 items-center">
              {isOwner && (
                <button
                  type="button"
                  title={t("kb.actionDelete")}
                  className="p-2 rounded text-white bg-red-500 hover:bg-red-600 mr-8 disabled:opacity-50"
                  onClick={() => {
                    setDeleteConfirmKb(kb);
                    setDeleteTypeName("");
                  }}
                  disabled={actionLoading}
                  aria-label={t("kb.actionDelete")}
                >
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                </button>
              )}
              {canManage && (
                <button
                  type="button"
                  title={t("kb.actionPermissions")}
                  className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50"
                  onClick={() => openSettingsModal(kb)}
                  disabled={actionLoading}
                  aria-label={t("kb.actionPermissions")}
                >
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
                </button>
              )}
              {kb.can_train && (
                <button
                  type="button"
                  title={t("kb.actionTrain")}
                  className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50"
                  onClick={() => navigate(`/kb/train/${kb.uuid}`)}
                  disabled={actionLoading}
                  aria-label={t("kb.actionTrain")}
                >
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>
                </button>
              )}
              {canManage && kb.can_train && (
                <button
                  type="button"
                  title={t("kb.actionEdit")}
                  className="p-2 rounded text-[var(--color-foreground)] bg-[var(--color-card)] border border-[var(--color-border)] hover:bg-[var(--color-button-hover)] disabled:opacity-50"
                  onClick={() => openEditModal(kb)}
                  disabled={actionLoading}
                  aria-label={t("kb.actionEdit")}
                >
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-lg">
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
              {canManage && usersWithPermsCreate.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-[var(--color-foreground)] mb-1">{t("kb.permissionsTitle")}</h3>
                  <p className="text-xs text-[var(--color-muted)] mb-2">{t("kb.permissionsHint")}</p>
                  <div className="border border-[var(--color-border)] rounded overflow-hidden max-h-48 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-[var(--color-table-head)]">
                        <tr>
                          <th className="p-2 text-left text-xs font-normal text-[var(--color-foreground)]">{t("roles.tableName")}</th>
                          <th className="p-2 text-left text-xs font-normal text-[var(--color-foreground)]">{t("roles.tableEmail")}</th>
                          <th className="p-2 text-left text-xs font-normal text-[var(--color-foreground)]">{t("kb.tableActions")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {usersWithPermsCreate.map((u) => (
                          <tr key={u.id} className="border-t border-[var(--color-border)]">
                            <td className="p-2 text-[var(--color-foreground)]">{u.name ?? "—"}</td>
                            <td className="p-2 text-[var(--color-muted)]">{u.email}</td>
                            <td className="p-2">
                              <select
                                value={u.permission === PERM_NONE && u.id === currentUserId ? PERM_TRAIN : u.permission}
                                onChange={(e) =>
                                  setCreatePermissions((prev) => ({ ...prev, [u.id]: e.target.value }))
                                }
                                className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-1.5 rounded text-sm"
                              >
                                {u.id !== currentUserId && (
                                  <option value={PERM_NONE}>{t("kb.permissionNone")}</option>
                                )}
                                <option value={PERM_USE}>{t("kb.permissionUse")}</option>
                                <option value={PERM_TRAIN}>{t("kb.permissionTrain")}</option>
                              </select>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              <div className="flex gap-2 mt-6 justify-end">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    resetForm();
                  }}
                  disabled={actionLoading}
                  className="bg-[var(--color-card)] hover:bg-[var(--color-button-hover)] text-[var(--color-foreground)] border border-[var(--color-border)] px-4 py-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
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

      {/* Edit Modal – név, leírás, személyes adat kérdések (egy lépésben) */}
      {editingKb && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg max-w-lg w-full max-h-[90vh] overflow-y-auto shadow-lg">
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
              <div>
                <label className="block mb-1 text-[var(--color-label)]">
                  {t("kb.personalDataModeLabel")}
                </label>
                  <select
                    value={editingPersonalDataMode}
                    onChange={(e) => setEditingPersonalDataMode(e.target.value as PersonalDataMode)}
                    className="w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] text-sm"
                  >
                    <option value="no_personal_data">{t("kb.personalDataModeNo")}</option>
                      <option value="allowed_not_to_ai">{t("kb.personalDataModeAllowed")}</option>
                      <option value="with_confirmation">{t("kb.personalDataModeConfirm")}</option>
                      <option value="no_pii_filter">{t("kb.personalDataModeDisabled")}</option>
                  </select>
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
                className="px-4 py-2 rounded text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)] bg-[var(--color-card)] border border-[var(--color-border)] disabled:opacity-50 disabled:cursor-not-allowed"
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

      {/* Beállítás modál – jogosultságok (csak train joggal nyitható) */}
      {settingsKb && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-lg">
            <p className="text-sm text-[var(--color-muted)] mb-0.5">{t("nav.knowledgeBase")}</p>
            <h2 className="text-2xl font-bold mb-1 text-[var(--color-foreground)]">{settingsKb.name}</h2>
            <p className="text-sm text-[var(--color-muted)] mb-4" style={{ marginTop: 10 }}>{t("kb.settingsUsageHint")}</p>

                <h3 className="text-sm font-semibold text-[var(--color-foreground)] mb-2">
                  {t("kb.permissionsTitle")}
                </h3>
            {settingsPermsLoading ? (
              <p className="text-[var(--color-muted)]">{t("common.loading")}</p>
            ) : (
              <>
                <div className="border border-[var(--color-border)] rounded overflow-hidden max-h-64 overflow-y-auto">
                  <table className="w-full text-sm">
                    <tbody>
                      <tr className="border-b border-[var(--color-border)] bg-[var(--color-table-head)]">
                        <td className="p-2 w-[20px] align-middle">
                          <input
                            type="checkbox"
                            checked={
                              usersWithPermsSettings
                                .filter((u) => u.id !== currentUserId)
                                .every((u) => u.permission === PERM_USE || u.permission === PERM_TRAIN)
                            }
                            onChange={(e) => {
                              const on = e.target.checked;
                              setSettingsPermissions((prev) => {
                                const next = { ...prev };
                                usersWithPermsSettings.forEach((u) => {
                                  if (u.id !== currentUserId) {
                                    next[u.id] = on
                                      ? (u.role === "user" ? PERM_USE : PERM_TRAIN)
                                      : PERM_NONE;
                                  }
                                });
                                return next;
                              });
                            }}
                            className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
                            aria-label={t("kb.everyone")}
                          />
                        </td>
                        <td className="p-2 text-xs text-[var(--color-foreground)] font-normal w-[30%]">{t("roles.tableName")}</td>
                        <td className="p-2 text-xs text-[var(--color-foreground)] font-normal w-[30%]">{t("roles.tableRole")}</td>
                        <td className="p-2 text-xs text-[var(--color-foreground)] font-normal text-center">{t("kb.columnTrainer")}</td>
                      </tr>
                      {usersWithPermsSettings.map((u) => {
                        const isSelf = u.id === currentUserId;
                        const perm = u.permission;
                        const hasPermission = perm === PERM_USE || perm === PERM_TRAIN;
                        const canTrain = perm === PERM_TRAIN;

                        const roleLabel =
                          u.role === "owner"
                            ? t("roles.roleOwner")
                            : u.role === "admin"
                              ? t("roles.roleAdmin")
                              : t("roles.roleUser");
                        const isOwnerRow = u.role === "owner";
                        const nameRoleColor =
                          isOwnerRow
                            ? "text-[var(--color-muted)]"
                            : hasPermission
                              ? "text-[var(--color-foreground)]"
                              : "text-[var(--color-muted)] opacity-70";

                        return (
                          <tr key={u.id} className="border-t border-[var(--color-border)]">
                            <td className="p-2 w-[20px] align-middle">
                              {(isSelf || isOwnerRow) ? (
                                <input
                                  type="checkbox"
                                  checked
                                  readOnly
                                  tabIndex={-1}
                                  className="w-4 h-4 border-[var(--color-border)] bg-[var(--color-border)] cursor-default"
                                />
                              ) : (
                                <input
                                  type="checkbox"
                                  checked={hasPermission}
                                  onChange={(e) =>
                                    setSettingsPermissions((prev) => ({
                                      ...prev,
                                      [u.id]: e.target.checked ? (u.role === "user" ? PERM_USE : PERM_TRAIN) : PERM_NONE,
                                    }))
                                  }
                                  className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
                                />
                              )}
                            </td>
                            <td className="p-3 align-top w-[30%]">
                              <div className={`font-medium ${nameRoleColor}`}>{u.name ?? "—"}</div>
                            </td>
                            <td className="p-3 align-top w-[30%]">
                              <div className={`font-medium ${nameRoleColor}`}>{roleLabel}</div>
                            </td>
                            <td className="p-3 align-middle text-center">
                              {isOwnerRow || (u.role === "admin" && (isSelf || canTrain)) ? (
                                <input
                                  type="checkbox"
                                  checked
                                  readOnly
                                  tabIndex={-1}
                                  className="w-4 h-4 border-[var(--color-border)] bg-[var(--color-border)] cursor-default"
                                />
                              ) : (
                                <>
                                  {isSelf && u.role === "user" ? (
                                    <span className="text-[var(--color-muted)]">
                                      {canTrain ? t("kb.permissionTrain") : perm === PERM_USE ? t("kb.permissionUse") : "—"}
                                    </span>
                                  ) : (
                                    <input
                                      type="checkbox"
                                      checked={canTrain}
                                      disabled={!hasPermission}
                                      onChange={(e) =>
                                        setSettingsPermissions((prev) => ({
                                          ...prev,
                                          [u.id]: e.target.checked ? PERM_TRAIN : PERM_USE,
                                        }))
                                      }
                                      className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
                                    />
                                  )}
                                </>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="flex justify-end gap-2 mt-4">
                  <button
                    type="button"
                    onClick={() => setSettingsKb(null)}
                    disabled={actionLoading}
                    className="px-4 py-2 rounded text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)] bg-[var(--color-card)] border border-[var(--color-border)] disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {t("common.cancel")}
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveSettings}
                    disabled={setPermissionsMutation.isPending}
                    className="px-4 py-2 rounded bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {setPermissionsMutation.isPending
                      ? t("common.loading")
                      : t("common.save")}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      <SavedModal
        open={savedModalOpen}
        onClose={() => setSavedModalOpen(false)}
      />

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
                className="px-4 py-2 rounded text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)] bg-[var(--color-card)] border border-[var(--color-border)] disabled:opacity-50 disabled:cursor-not-allowed"
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
