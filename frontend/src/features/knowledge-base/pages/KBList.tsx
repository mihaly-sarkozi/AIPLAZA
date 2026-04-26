import { useEffect, useState, useMemo, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { SavedModal } from "../../../components/SavedModal";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import PageHeader from "../../../components/ui/PageHeader";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  useKbList,
  useCreateKbMutation,
  useUpdateKbMutation,
  useDeleteKbMutation,
  useClearKbMutation,
  useKbPermissions,
  useSetKbPermissionsMutation,
  type KbItem,
} from "../hooks/useKb";
import { useUsers } from "../../users/hooks/useUsers";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview } from "../../billing/hooks/useBilling";

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
  const [clearConfirmKb, setClearConfirmKb] = useState<KbItem | null>(null);
  const [clearTypeName, setClearTypeName] = useState("");
  const [savedModalOpen, setSavedModalOpen] = useState(false);
  const [showDemoKbLimitModal, setShowDemoKbLimitModal] = useState(false);

  const { data: billingOverview, isPending: billingOverviewPending } = useBillingOverview({
    enabled: isOwner,
  });
  const canDeleteKb = isOwner && import.meta.env.DEV;
  const canClearKb = isOwner && (import.meta.env.DEV || Boolean(billingOverview?.demo_mode));

  /** Tudástár-létrehozás helyett csomag / korlát felugró, ha a csomag szerinti limit elérve (pl. demo: 1 db). */
  const kbPackageLimitBlocked = useMemo(() => {
    if (!isOwner || billingOverviewPending || !billingOverview) return false;
    const kbMaxRaw = billingOverview.limits?.knowledge_bases;
    const resources = billingOverview.usage?.resources as { knowledge_bases?: number } | undefined;
    const kbUsedRaw = resources?.knowledge_bases;
    const kbMax = typeof kbMaxRaw === "number" ? kbMaxRaw : Number.NaN;
    const kbUsed = typeof kbUsedRaw === "number" ? kbUsedRaw : items.length;
    const atPlanKbLimit = Number.isFinite(kbMax) && kbMax > 0 && kbUsed >= kbMax;
    const demoSecondKb = Boolean(billingOverview.demo_mode && items.length >= 1);
    return atPlanKbLimit || demoSecondKb;
  }, [isOwner, billingOverviewPending, billingOverview, items.length]);

  const createKbMutation = useCreateKbMutation();
  const updateKbMutation = useUpdateKbMutation();
  const deleteKbMutation = useDeleteKbMutation();
  const clearKbMutation = useClearKbMutation();
  const setPermissionsMutation = useSetKbPermissionsMutation();
  const actionLoading =
    createKbMutation.isPending ||
    updateKbMutation.isPending ||
    deleteKbMutation.isPending ||
    clearKbMutation.isPending ||
    setPermissionsMutation.isPending;

  const [formData, setFormData] = useState({ name: "", description: "" });
  /** Create modal: user_id -> permission (none/use/train) */
  const [createPermissions, setCreatePermissions] = useState<Record<number, string>>({});
  /** Beállítás modál: user_id -> permission; API-ból szinkronizálva */
  const [settingsPermissions, setSettingsPermissions] = useState<Record<number, string>>({});
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
  const totalKnowledgeBases = items.length;
  const knowledgeBasesWithDescription = items.filter((kb) => (kb.description ?? "").trim().length > 0).length;
  const knowledgeBasesWithoutDescription = totalKnowledgeBases - knowledgeBasesWithDescription;

  useEffect(() => {
    const openKbCreate = Boolean((location.state as { openKbCreate?: boolean })?.openKbCreate);
    if (!openKbCreate) return;
    if (isOwner && billingOverviewPending) return;
    navigate(location.pathname, { replace: true, state: {} });
    if (kbPackageLimitBlocked) {
      setShowDemoKbLimitModal(true);
    } else {
      resetForm();
      setShowCreateModal(true);
    }
  }, [
    location.state,
    location.pathname,
    navigate,
    isOwner,
    billingOverviewPending,
    kbPackageLimitBlocked,
  ]);

  const resetForm = () => {
    setFormData({ name: "", description: "" });
    setCreatePermissions({});
    setCreateFormError(null);
    setEditFormError(null);
  };

  const openCreateModal = () => {
    if (kbPackageLimitBlocked) {
      setShowDemoKbLimitModal(true);
      return;
    }
    resetForm();
    setShowCreateModal(true);
  };

  const openEditModal = (kb: KbItem) => {
    setEditingKb(kb);
    setEditFormError(null);
    setFormData({ name: kb.name, description: kb.description ?? "" });
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
    if (!canDeleteKb) {
      toast.error("A tudástár törlése csak fejlesztői módban érhető el.");
      return;
    }
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

  const handleClear = () => {
    if (!clearConfirmKb) return;
    if (!canClearKb) {
      toast.error("A tudástár kiürítése csak fejlesztői módban vagy ingyenes teszt üzemmódban érhető el.");
      return;
    }
    if (clearTypeName.trim() !== clearConfirmKb.name) {
      toast.error("A megerősítő név nem egyezik a tudástár nevével.");
      return;
    }
    clearKbMutation.mutate(
      { uuid: clearConfirmKb.uuid, confirm_name: clearTypeName.trim() },
      {
        onSuccess: () => {
          toast.success("A tudástár tartalma kiürítve.");
          setClearConfirmKb(null);
          setClearTypeName("");
        },
        onError: (err: unknown) => {
          toast.error(getApiErrorMessage(err) ?? "A tudástár kiürítése sikertelen.");
        },
      }
    );
  };

  if (loading) {
    return (
      <div className="app-page text-[var(--color-foreground)]">
        {t("common.loading")}
      </div>
    );
  }

  return (
    <div className="app-page">
      <div className="app-page-container">
        <PageHeader
          eyebrow={t("kb.collectionLabel")}
          title={t("kb.title")}
          description={t("kb.pageIntro")}
          actions={
            isOwner ? (
              <Button onClick={openCreateModal} disabled={actionLoading || billingOverviewPending}>
                {t("kb.newKb")}
              </Button>
            ) : null
          }
        />

        {error && (
          <Alert tone="error">{error}</Alert>
        )}

        <div className="grid gap-4 md:grid-cols-3">
          <div className="app-surface p-5">
            <p className="text-sm text-[var(--color-muted)]">{t("kb.summaryTotal")}</p>
            <p className="mt-2 text-2xl font-semibold text-[var(--color-foreground)]">{totalKnowledgeBases}</p>
          </div>
          <div className="app-surface p-5">
            <p className="text-sm text-[var(--color-muted)]">{t("kb.summaryWithDescription")}</p>
            <p className="mt-2 text-2xl font-semibold text-[var(--color-foreground)]">{knowledgeBasesWithDescription}</p>
          </div>
          <div className="app-surface p-5">
            <p className="text-sm text-[var(--color-muted)]">{t("kb.summaryWithoutDescription")}</p>
            <p className="mt-2 text-2xl font-semibold text-[var(--color-foreground)]">{knowledgeBasesWithoutDescription}</p>
          </div>
        </div>

        <section className="app-surface p-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-medium text-[var(--color-muted)]">{t("kb.listSectionLabel")}</p>
              <h2 className="mt-1 text-xl font-semibold text-[var(--color-foreground)]">{t("kb.listSectionTitle")}</h2>
            </div>
            <div className="badge-soft">
              {t("kb.liveListLabel")}
            </div>
          </div>

          <div className="app-table-wrap mt-6">
            <div className="app-table-head hidden grid-cols-[1fr_1.5fr_1fr] gap-4 px-5 py-3 text-sm font-medium md:grid">
              <div>{t("kb.tableName")}</div>
              <div>{t("kb.tableDescription")}</div>
              <div>{t("kb.tableActions")}</div>
            </div>

            <div className="divide-y divide-[var(--color-border)]">
              {items.map((kb) => (
                <div key={kb.uuid} className="grid gap-4 px-5 py-4 md:grid-cols-[1fr_1.5fr_1fr] md:items-center">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--color-card-muted)] text-sm font-medium text-[var(--color-muted-foreground)]">
                      {kb.name.trim().charAt(0).toUpperCase() || "?"}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-medium text-[var(--color-foreground)]">{kb.name}</p>
                      <span className="mt-1 inline-block rounded-lg bg-[var(--color-card-muted)] px-2 py-0.5 text-xs font-medium text-[var(--color-muted-foreground)]">
                        {t("kb.itemLabel")}
                      </span>
                    </div>
                  </div>

                  <div className="text-sm text-[var(--color-muted)]">{kb.description?.trim() ? kb.description : "—"}</div>

                  <div className="flex flex-wrap items-center gap-2 md:justify-start">
                    {canClearKb && (
                      <Button
                        type="button"
                        title="Tudástár kiürítése"
                        variant="danger"
                        onClick={() => {
                          setClearConfirmKb(kb);
                          setClearTypeName("");
                        }}
                        disabled={actionLoading}
                        aria-label="Tudástár kiürítése"
                      >
                        Kiürítés
                      </Button>
                    )}
                    {canDeleteKb && (
                      <Button
                        type="button"
                        title={t("kb.actionDelete")}
                        variant="danger"
                        onClick={() => {
                          setDeleteConfirmKb(kb);
                          setDeleteTypeName("");
                        }}
                        disabled={actionLoading}
                        aria-label={t("kb.actionDelete")}
                      >
                        {t("kb.actionDelete")}
                      </Button>
                    )}
                    {canManage && (
                      <Button
                        type="button"
                        title={t("kb.actionPermissions")}
                        variant="secondary"
                        onClick={() => openSettingsModal(kb)}
                        disabled={actionLoading}
                        aria-label={t("kb.actionPermissions")}
                      >
                        {t("kb.actionPermissions")}
                      </Button>
                    )}
                    {canManage && (
                      <Button
                        type="button"
                        title="Ingest"
                        variant="primary"
                        onClick={() => navigate(`/kb/ingest/${kb.uuid}`)}
                        disabled={actionLoading}
                        aria-label="Ingest"
                      >
                        Ingest
                      </Button>
                    )}
                    {canManage && (
                      <Button
                        type="button"
                        title={t("kb.actionEdit")}
                        variant="secondary"
                        onClick={() => openEditModal(kb)}
                        disabled={actionLoading}
                        aria-label={t("kb.actionEdit")}
                      >
                        {t("kb.actionSettings")}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <Modal open={showCreateModal} onClose={() => setShowCreateModal(false)} panelClassName="max-w-2xl">
            <ModalHeader title={t("kb.modalNewTitle")} description={t("kb.modalNewHint")} />
            {createFormError && (
              <Alert tone="error" className="mb-4">{createFormError}</Alert>
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
              <ModalFooter>
                <Button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    resetForm();
                  }}
                  variant="secondary"
                  disabled={actionLoading}
                >
                  {t("common.cancel")}
                </Button>
                <Button
                  type="submit"
                  disabled={actionLoading}
                >
                  {actionLoading ? t("common.loading") : t("common.save")}
                </Button>
              </ModalFooter>
            </form>
        </Modal>
      )}

      {/* Edit Modal – név és leírás */}
      {editingKb && (
        <Modal open={Boolean(editingKb)} onClose={() => setEditingKb(null)} panelClassName="max-w-lg">
            <ModalHeader title={t("kb.modalEditTitle")} />
            {editFormError && (
              <Alert tone="error" className="mb-4">{editFormError}</Alert>
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
            <ModalFooter>
              <Button
                type="button"
                onClick={() => {
                  setEditingKb(null);
                  resetForm();
                }}
                variant="secondary"
                disabled={actionLoading}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="button"
                onClick={handleUpdate}
                disabled={actionLoading}
              >
                {actionLoading ? t("common.loading") : t("common.save")}
              </Button>
            </ModalFooter>
        </Modal>
      )}

      {/* Beállítás modál – jogosultságok (csak train joggal nyitható) */}
      {settingsKb && (
        <Modal open={Boolean(settingsKb)} onClose={() => setSettingsKb(null)} panelClassName="max-w-2xl">
            <ModalHeader
              eyebrow={t("nav.knowledgeBase")}
              title={settingsKb.name}
              description={t("kb.settingsUsageHint")}
            />

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
                <ModalFooter className="mt-4">
                  <Button
                    type="button"
                    onClick={() => setSettingsKb(null)}
                    variant="secondary"
                    disabled={actionLoading}
                  >
                    {t("common.cancel")}
                  </Button>
                  <Button
                    type="button"
                    onClick={handleSaveSettings}
                    disabled={setPermissionsMutation.isPending}
                  >
                    {setPermissionsMutation.isPending
                      ? t("common.loading")
                      : t("common.save")}
                  </Button>
                </ModalFooter>
              </>
            )}
        </Modal>
      )}

      {showDemoKbLimitModal && (
        <Modal
          open={showDemoKbLimitModal}
          onClose={() => setShowDemoKbLimitModal(false)}
          closeOnOverlay
          panelClassName="max-w-md"
        >
            <h2 id="demo-kb-limit-title" className="text-xl font-bold text-[var(--color-foreground)] mb-3">
              Demo korlát elérve
            </h2>
            <div className="space-y-3 text-sm text-[var(--color-muted-foreground)]">
              <p>A demo verzióban egy tudástár hozható létre.</p>
              <p>
                A teljes verzióban több tudástárat is kezelhetsz, és bővítheted a rendszered a saját igényeid
                szerint.
              </p>
              <p>A jelenlegi tudástárad természetesen megmarad.</p>
            </div>
            <div className="mt-6 flex flex-col-reverse sm:flex-row gap-2 sm:justify-end">
              <Button
                type="button"
                variant="secondary"
                size="lg"
                className="w-full sm:w-auto"
                onClick={() => setShowDemoKbLimitModal(false)}
              >
                {t("common.back")}
              </Button>
              <Button
                type="button"
                size="lg"
                className="w-full sm:w-auto"
                onClick={() => {
                  setShowDemoKbLimitModal(false);
                  navigate("/admin/csomagok");
                }}
              >
                {"\u{1F449}"} Csomagok megtekintése
              </Button>
            </div>
        </Modal>
      )}

      <SavedModal
        open={savedModalOpen}
        onClose={() => setSavedModalOpen(false)}
      />

      {canClearKb && clearConfirmKb && (
        <Modal open={Boolean(clearConfirmKb)} onClose={() => setClearConfirmKb(null)} panelClassName="max-w-md">
            <ModalHeader title="Tudástár kiürítése" />
            <p className="text-sm text-[var(--color-muted)] mb-3">
              Írd be a tudástár nevét a kiürítés megerősítéséhez. A tudástár megmarad, de a betöltött elemek,
              ingest naplók és kapcsolódó index adatok törlődnek.
            </p>
            <input
              type="text"
              value={clearTypeName}
              onChange={(e) => setClearTypeName(e.target.value)}
              placeholder={clearConfirmKb.name}
              className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded mb-4"
            />
            <ModalFooter>
              <Button
                type="button"
                onClick={() => {
                  setClearConfirmKb(null);
                  setClearTypeName("");
                }}
                variant="secondary"
                disabled={actionLoading}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="button"
                onClick={handleClear}
                variant="danger"
                disabled={actionLoading || clearTypeName.trim() !== clearConfirmKb.name}
              >
                {actionLoading ? t("common.loading") : "Kiürítés"}
              </Button>
            </ModalFooter>
        </Modal>
      )}

      {/* Delete confirm */}
      {canDeleteKb && deleteConfirmKb && (
        <Modal open={Boolean(deleteConfirmKb)} onClose={() => setDeleteConfirmKb(null)} panelClassName="max-w-md">
            <ModalHeader title={t("kb.confirmDelete")} />
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
            <ModalFooter>
              <Button
                type="button"
                onClick={() => {
                  setDeleteConfirmKb(null);
                  setDeleteTypeName("");
                }}
                variant="secondary"
                disabled={actionLoading}
              >
                {t("common.cancel")}
              </Button>
              <Button
                type="button"
                onClick={handleDelete}
                variant="danger"
                disabled={actionLoading || deleteTypeName.trim() !== deleteConfirmKb.name}
              >
                {actionLoading ? t("common.loading") : t("common.delete")}
              </Button>
            </ModalFooter>
        </Modal>
      )}
    </div>
  );
}
