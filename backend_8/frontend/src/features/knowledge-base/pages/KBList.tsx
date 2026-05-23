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
const KB_NAME_MAX_LENGTH = 200;
const LIST_PAGE_SIZE = 10;

function formatBytes(value: number | null | undefined): string {
  const bytes = Math.max(0, Number(value || 0));
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = bytes / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${new Intl.NumberFormat("hu-HU", { maximumFractionDigits: size >= 10 ? 1 : 2 }).format(size)} ${units[unitIndex]}`;
}

function formatInteger(value: number | null | undefined): string {
  return new Intl.NumberFormat("hu-HU").format(Math.max(0, Number(value || 0)));
}

function formatThousands(value: number | null | undefined): string {
  const safeValue = Math.max(0, Number(value || 0));
  if (safeValue < 1000) return formatInteger(safeValue);
  return `${new Intl.NumberFormat("hu-HU", { maximumFractionDigits: 1 }).format(safeValue / 1000)}E`;
}

function metricValue(
  kb: KbItem,
  key: "file_bytes" | "database_bytes" | "qdrant_bytes" | "total_bytes" | "training_char_count"
): number {
  const value = kb.storage_metrics?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function isDeletedKb(kb: KbItem): boolean {
  return kb.status === "deleted" || Boolean(kb.deleted_at);
}

function nameMaxLengthMessage(t: (key: string) => string): string {
  return t("kb.nameMaxLength").replace("{{count}}", String(KB_NAME_MAX_LENGTH));
}

export default function KBList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const currentUserId = useAuthStore((s) => s.user?.id);
  const canManage = useAuthStore((s) => s.user?.role === "admin" || s.user?.role === "owner");
  const isOwner = useAuthStore((s) => s.user?.role === "owner");
  const { data: items = [], isLoading: loading, error: listError } = useKbList({
    refetchOnMount: "always",
  });
  const { data: users = [] } = useUsers({ enabled: canManage });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createFormError, setCreateFormError] = useState<string | null>(null);
  const [editFormError, setEditFormError] = useState<string | null>(null);
  const [settingsKb, setSettingsKb] = useState<KbItem | null>(null);
  const [piiDepersonalizationEnabled, setPiiDepersonalizationEnabled] = useState(true);
  const [deleteConfirmKb, setDeleteConfirmKb] = useState<KbItem | null>(null);
  const [deleteTypeName, setDeleteTypeName] = useState("");
  const [savedModalOpen, setSavedModalOpen] = useState(false);
  const [showKbLimitModal, setShowKbLimitModal] = useState(false);
  const [visibleCount, setVisibleCount] = useState(LIST_PAGE_SIZE);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  const { data: billingOverview, isPending: billingOverviewPending } = useBillingOverview({
    enabled: isOwner,
    refetchOnMount: "always",
  });
  const paymentWarning = (billingOverview?.payment_warning as Record<string, unknown> | null | undefined) ?? null;
  const billingRestricted =
    String((billingOverview?.subscription as Record<string, unknown> | undefined)?.status ?? "").toLowerCase() === "restricted" ||
    paymentWarning?.is_expired === true;
  const demoMode = Boolean(billingOverview?.demo_mode);
  const canDeleteKb = isOwner && (import.meta.env.DEV || demoMode);
  const activeKnowledgeBaseCount = useMemo(() => items.filter((kb) => !isDeletedKb(kb)).length, [items]);
  const visibleItems = useMemo(() => {
    return [...items]
      .filter((kb) => !isDeletedKb(kb) || metricValue(kb, "training_char_count") > 0)
      .sort((left, right) => Number(isDeletedKb(left)) - Number(isDeletedKb(right)));
  }, [items]);
  const displayedItems = useMemo(() => visibleItems.slice(0, visibleCount), [visibleItems, visibleCount]);

  useEffect(() => {
    setVisibleCount(LIST_PAGE_SIZE);
  }, [visibleItems.length]);

  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node || visibleCount >= visibleItems.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisibleCount((count) => Math.min(count + LIST_PAGE_SIZE, visibleItems.length));
        }
      },
      { rootMargin: "320px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [visibleCount, visibleItems.length]);

  /** Tudástár-létrehozás helyett csomag / korlát felugró, ha az aktuális csomag szerinti limit elérve. */
  const kbPackageLimitBlocked = useMemo(() => {
    if (!isOwner || billingOverviewPending || !billingOverview) return false;
    const kbMaxRaw = billingOverview.limits?.knowledge_bases;
    const kbMax = typeof kbMaxRaw === "number" ? kbMaxRaw : Number.NaN;
    return Number.isFinite(kbMax) && kbMax > 0 && activeKnowledgeBaseCount >= kbMax;
  }, [isOwner, billingOverviewPending, billingOverview, activeKnowledgeBaseCount]);

  const kbLimitDetails = useMemo(() => {
    const kbMaxRaw = billingOverview?.limits?.knowledge_bases;
    return {
      max: typeof kbMaxRaw === "number" ? kbMaxRaw : null,
      used: activeKnowledgeBaseCount,
    };
  }, [billingOverview, activeKnowledgeBaseCount]);

  const createKbMutation = useCreateKbMutation();
  const updateKbMutation = useUpdateKbMutation();
  const deleteKbMutation = useDeleteKbMutation();
  const setPermissionsMutation = useSetKbPermissionsMutation();
  const actionLoading =
    createKbMutation.isPending ||
    updateKbMutation.isPending ||
    deleteKbMutation.isPending ||
    setPermissionsMutation.isPending;
  const settingsSaveLoading = updateKbMutation.isPending || setPermissionsMutation.isPending;

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
  }, [settingsKb, settingsPermsList]);


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
  const totalKnowledgeBases = activeKnowledgeBaseCount;
  const totalFileBytes = visibleItems.reduce((sum, kb) => sum + metricValue(kb, "file_bytes"), 0);
  const totalDatabaseBytes = visibleItems.reduce((sum, kb) => sum + metricValue(kb, "database_bytes"), 0);
  const totalTrainingChars = visibleItems.reduce((sum, kb) => sum + metricValue(kb, "training_char_count"), 0);
  const totalStorageBytes = visibleItems.reduce((sum, kb) => sum + metricValue(kb, "total_bytes"), 0);

  useEffect(() => {
    const openKbCreate = Boolean((location.state as { openKbCreate?: boolean })?.openKbCreate);
    if (!openKbCreate) return;
    if (isOwner && billingOverviewPending) return;
    navigate(location.pathname, { replace: true, state: {} });
    if (kbPackageLimitBlocked) {
      setShowKbLimitModal(true);
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
      setShowKbLimitModal(true);
      return;
    }
    resetForm();
    setShowCreateModal(true);
  };

  const openSettingsModal = (kb: KbItem) => {
    setSettingsKb(kb);
    setSettingsPermissions({});
    setPiiDepersonalizationEnabled(kb.pii_depersonalization_enabled !== false);
    settingsPermsSyncedUuid.current = null;
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
    if (nameTrim.length > KB_NAME_MAX_LENGTH) {
      setCreateFormError(nameMaxLengthMessage(t));
      return;
    }
    const permissions = usersWithPermsCreate
      .filter((u) => u.permission && u.permission !== PERM_NONE)
      .map((u) => ({ user_id: u.id, permission: u.permission }));
    createKbMutation.mutate(
      {
        name: nameTrim,
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

  const handleSaveSettings = () => {
    if (!settingsKb) return;
    const nameTrim = formData.name?.trim() ?? "";
    setEditFormError(null);
    if (!nameTrim) {
      setEditFormError(t("common.fieldRequired"));
      return;
    }
    if (nameTrim.length > KB_NAME_MAX_LENGTH) {
      setEditFormError(nameMaxLengthMessage(t));
      return;
    }
    const permissions = usersWithPermsSettings.map((u) => ({ user_id: u.id, permission: u.permission }));
    updateKbMutation.mutate(
      {
        uuid: settingsKb.uuid,
        name: nameTrim,
        description: settingsKb.description?.trim() || undefined,
        pii_depersonalization_enabled: piiDepersonalizationEnabled,
      },
      {
        onSuccess: () => {
          setPermissionsMutation.mutate(
            { uuid: settingsKb.uuid, permissions },
            {
              onSuccess: () => {
                setSavedModalOpen(true);
                setSettingsKb(null);
                resetForm();
              },
              onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("kb.errorPermissions")),
            }
          );
        },
        onError: (err: unknown) => {
          toast.error(getApiErrorMessage(err) ?? t("kb.errorUpdate"));
        },
      }
    );
  };

  const handleDelete = () => {
    if (!deleteConfirmKb) return;
    if (!canDeleteKb) {
      toast.error("A tudástár törlése csak fejlesztői vagy tesztüzemmódban érhető el.");
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
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="secondary" onClick={() => navigate("/admin/forgalom")}>
                  {t("nav.traffic")}
                </Button>
                {!billingRestricted ? (
                <Button onClick={openCreateModal} disabled={actionLoading || billingOverviewPending}>
                  {t("kb.newKb")}
                </Button>
                ) : null}
              </div>
            ) : null
          }
        />

        {error && (
          <Alert tone="error">{error}</Alert>
        )}

        <dl className="grid grid-cols-3 gap-x-3 gap-y-2 rounded-2xl bg-[var(--color-card-muted)]/60 px-3 py-2 md:grid-cols-5 md:px-4">
          <div className="min-w-0">
            <dt className="truncate text-[10px] font-medium uppercase tracking-wide text-[var(--color-muted)] md:text-xs">{t("kb.summaryTotal")}</dt>
            <dd className="mt-0.5 truncate text-sm font-semibold text-[var(--color-foreground)] md:text-base">{totalKnowledgeBases}</dd>
          </div>
          <div className="min-w-0">
            <dt className="truncate text-[10px] font-medium uppercase tracking-wide text-[var(--color-muted)] md:text-xs">{t("kb.summaryTotalSize")}</dt>
            <dd className="mt-0.5 truncate text-sm font-semibold text-[var(--color-foreground)] md:text-base">{formatBytes(totalStorageBytes)}</dd>
          </div>
          <div className="min-w-0">
            <dt className="truncate text-[10px] font-medium uppercase tracking-wide text-[var(--color-muted)] md:text-xs">{t("kb.summaryFiles")}</dt>
            <dd className="mt-0.5 truncate text-sm font-semibold text-[var(--color-foreground)] md:text-base">{formatBytes(totalFileBytes)}</dd>
          </div>
          <div className="min-w-0">
            <dt className="truncate text-[10px] font-medium uppercase tracking-wide text-[var(--color-muted)] md:text-xs">{t("kb.summaryDatabaseSize")}</dt>
            <dd className="mt-0.5 truncate text-sm font-semibold text-[var(--color-foreground)] md:text-base">{formatBytes(totalDatabaseBytes)}</dd>
          </div>
          <div className="min-w-0">
            <dt className="truncate text-[10px] font-medium uppercase tracking-wide text-[var(--color-muted)] md:text-xs">{t("kb.summaryCharacters")}</dt>
            <dd className="mt-0.5 truncate text-sm font-semibold text-[var(--color-foreground)] md:text-base">{formatThousands(totalTrainingChars)}</dd>
          </div>
        </dl>

        <section>
          <div className="app-table-wrap">
            <div className="app-table-head hidden grid-cols-[0.75fr_2fr_0.6fr] gap-4 !bg-[#efefef] px-5 py-3 text-sm font-medium !text-[var(--color-foreground)] md:grid">
              <div>{t("kb.tableName")}</div>
              <div>{t("kb.tableTraffic")}</div>
              <div>{t("kb.tableActions")}</div>
            </div>

            <div className="divide-y divide-[var(--color-border)]">
              {displayedItems.map((kb) => {
                const deleted = isDeletedKb(kb);
                return (
                <div key={kb.uuid} className={`grid gap-4 px-5 py-4 md:grid-cols-[0.75fr_2fr_0.6fr] md:items-center ${deleted ? "text-[var(--color-muted)]" : ""}`}>
                  <div className="min-w-0">
                    <p className={`truncate font-medium ${deleted ? "text-[var(--color-muted)]" : "text-[var(--color-foreground)]"}`}>
                      {kb.name}
                    </p>
                    {deleted ? (
                      <span className="mt-1 inline-block rounded-lg bg-[var(--color-danger-text)] px-2 py-0.5 text-xs font-medium text-white">
                        {t("kb.statusDeleted")}
                      </span>
                    ) : (
                      <span className="mt-1 inline-block rounded-lg bg-[var(--color-success-text)] px-2 py-0.5 text-xs font-medium text-white">
                        {t("kb.statusActive")}
                      </span>
                    )}
                  </div>

                  <div className={`text-sm ${deleted ? "text-[var(--color-muted)]" : "text-[var(--color-muted)]"}`}>
                    <div className="rounded-lg bg-[var(--color-card-muted)] px-3 py-2 text-xs leading-5 text-[var(--color-muted-foreground)]">
                      <span className={`font-medium ${deleted ? "text-[var(--color-muted)]" : "text-[var(--color-foreground)]"}`}>{t("kb.metricCharacters")}: {formatThousands(metricValue(kb, "training_char_count"))}</span>
                      <span className="mx-2">|</span>
                      {t("kb.metricSize")}: {formatBytes(metricValue(kb, "total_bytes"))}
                      <span className="mx-2">|</span>
                      {t("kb.metricFile")}: {formatBytes(metricValue(kb, "file_bytes"))}
                      <span className="mx-2">|</span>
                      {t("kb.metricDatabase")}: {formatBytes(metricValue(kb, "database_bytes"))}
                      {canManage && !deleted ? (
                        <div className="mt-1">
                          <button
                            type="button"
                            onClick={() => navigate(`/kb/ingest/${kb.uuid}`)}
                            className="font-medium text-[var(--color-muted)] hover:text-[var(--color-muted-foreground)] hover:underline"
                            title={t("kb.actionTrainingLog")}
                            aria-label={t("kb.actionTrainingLog")}
                          >
                            {t("kb.actionLog")} →
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>

                  <div className="flex flex-wrap justify-end gap-2">
                    {deleted ? (
                      <div className="w-full rounded-lg bg-[var(--color-card-muted)] px-3 py-2 text-center text-sm font-medium text-[var(--color-muted-foreground)]">
                        {t("kb.deletedNoActions")}
                      </div>
                    ) : null}
                    {canManage && !billingRestricted && !deleted && (
                      <Button
                        type="button"
                        title={t("kb.actionSettings")}
                        variant="secondary"
                        onClick={() => openSettingsModal(kb)}
                        disabled={actionLoading}
                        aria-label={t("kb.actionSettings")}
                        size="sm"
                      >
                        {t("kb.actionSettings")}
                      </Button>
                    )}
                    {canDeleteKb && !billingRestricted && !deleted && (
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
                        size="sm"
                      >
                        {t("kb.actionDelete")}
                      </Button>
                    )}
                  </div>
                </div>
                );
              })}
            </div>
            <div ref={loadMoreRef} className="h-8" />
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
                  maxLength={KB_NAME_MAX_LENGTH}
                  required
                />
              </div>
              {canManage && usersWithPermsCreate.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-[var(--color-foreground)] mb-1">{t("kb.permissionsTitle")}</h3>
                  <p className="text-xs text-[var(--color-muted)] mb-2">{t("kb.permissionsHint")}</p>
                  <div className="border border-[var(--color-border)] rounded overflow-hidden max-h-48 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-[#efefef]">
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

      {/* Beállítás modál – alapadatok és jogosultságok */}
      {settingsKb && (
        <Modal open={Boolean(settingsKb)} onClose={() => setSettingsKb(null)} panelClassName="max-w-2xl">
            <ModalHeader
              eyebrow={t("nav.knowledgeBase")}
              title={t("kb.actionSettings")}
              description={t("kb.settingsUsageHint")}
            />
            {editFormError && (
              <Alert tone="error" className="mb-4">{editFormError}</Alert>
            )}

            <div className="mb-5 space-y-4">
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
                  maxLength={KB_NAME_MAX_LENGTH}
                  required
                />
              </div>
              <label
                className="!mb-0 !inline-flex !items-center rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-foreground)]"
                style={{ gap: "8px" }}
              >
                <input
                  type="checkbox"
                  checked={piiDepersonalizationEnabled}
                  onChange={(event) => setPiiDepersonalizationEnabled(event.target.checked)}
                  className="kb-perm-checkbox !mt-0 self-center"
                />
                <span className="leading-5 align-middle">PII deperszonalizáció az LLM felé (ajánlott)</span>
              </label>
            </div>

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
                      <tr className="border-b border-[var(--color-border)] bg-[#efefef]">
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
                    onClick={() => {
                      setSettingsKb(null);
                      resetForm();
                    }}
                    variant="secondary"
                    disabled={actionLoading}
                  >
                    {t("common.cancel")}
                  </Button>
                  <Button
                    type="button"
                    onClick={handleSaveSettings}
                    disabled={settingsSaveLoading}
                  >
                    {settingsSaveLoading
                      ? t("common.loading")
                      : t("common.save")}
                  </Button>
                </ModalFooter>
              </>
            )}
        </Modal>
      )}

      {showKbLimitModal && (
        <Modal
          open={showKbLimitModal}
          onClose={() => setShowKbLimitModal(false)}
          closeOnOverlay
          panelClassName="max-w-md"
        >
            <h2 id="kb-limit-title" className="text-xl font-bold text-[var(--color-foreground)] mb-3">
              {t("kb.limitReachedTitle")}
            </h2>
            <div className="space-y-3 text-sm text-[var(--color-muted-foreground)]">
              <p>
                {t("kb.limitReachedMessage")
                  .replace("{{max}}", String(kbLimitDetails.max ?? t("kb.limitByPlan")))
                  .replace("{{used}}", String(kbLimitDetails.used))}
              </p>
              <p>
                {t("kb.limitReachedHint")}
              </p>
            </div>
            <div className="mt-6 flex flex-col-reverse sm:flex-row gap-2 sm:justify-end">
              <Button
                type="button"
                variant="secondary"
                size="lg"
                className="w-full sm:w-auto"
                onClick={() => setShowKbLimitModal(false)}
              >
                {t("common.back")}
              </Button>
              <Button
                type="button"
                size="lg"
                className="w-full sm:w-auto"
                onClick={() => {
                  setShowKbLimitModal(false);
                  navigate("/admin/csomagok");
                }}
              >
                {t("kb.viewPackages")}
              </Button>
            </div>
        </Modal>
      )}

      <SavedModal
        open={savedModalOpen}
        onClose={() => setSavedModalOpen(false)}
      />

      {/* Delete confirm */}
      {canDeleteKb && deleteConfirmKb && (
        <Modal open={Boolean(deleteConfirmKb)} onClose={() => setDeleteConfirmKb(null)} panelClassName="max-w-md">
            <ModalHeader title={t("kb.confirmDelete")} />
            <p className="text-sm text-[var(--color-muted)] mb-3">
              {t("kb.confirmDeleteTypeName").replace("{{name}}", deleteConfirmKb.name)}
            </p>
            <div className="mb-4 rounded-lg border border-[var(--color-danger-border)] bg-[var(--color-danger-bg)] px-3 py-2 text-sm leading-relaxed text-[var(--color-danger-text)]">
              {t("kb.confirmDeleteTrainingFilesWarning")}
            </div>
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
