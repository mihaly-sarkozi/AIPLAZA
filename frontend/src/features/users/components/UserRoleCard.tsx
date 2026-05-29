import Button from "../../../components/ui/Button";
import type { RoleUser } from "./rolesTypes";
import { getStatusClasses, isDeletedUser } from "./rolesTypes";

type UserRoleCardProps = {
  user: RoleUser;
  currentUser: { id?: number; role?: string } | null | undefined;
  actionLoading: boolean;
  t: (key: string) => string;
  onDelete: (user: RoleUser) => void;
  onKbPermissions: (user: RoleUser) => void;
  onEdit: (user: RoleUser) => void;
  onResendInvite: (user: RoleUser) => void;
  onToggleActive: (user: RoleUser) => void;
};

export default function UserRoleCard({
  user,
  currentUser,
  actionLoading,
  t,
  onDelete,
  onKbPermissions,
  onEdit,
  onResendInvite,
  onToggleActive,
}: UserRoleCardProps) {
  const statusLabel = isDeletedUser(user)
    ? t("roles.statusDeleted")
    : !user.is_active
      ? t("roles.statusInactive")
      : user.pending_registration
        ? t("roles.statusPending")
        : t("roles.statusActive");
  const roleLabel = user.role === "owner" ? t("roles.roleOwner") : user.role === "admin" ? t("roles.roleAdmin") : t("roles.roleUser");
  const displayName = user.name || "—";
  const targetEditable =
    (user.role !== "owner" || currentUser?.role === "owner" || user.id === currentUser?.id);
  const targetBlockedMessageKey = user.role === "admin" ? "roles.adminOnlyEdit" : "roles.ownerOnlyEdit";
  const canToggleActive =
    targetEditable && user.id !== currentUser?.id && user.role !== "owner" && !isDeletedUser(user);
  const inactiveDarkTextClass = !user.is_active && !isDeletedUser(user) ? "role-inactive-dark-text" : "";

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-3 px-5 py-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,0.8fr)] md:grid-cols-[5rem_minmax(12rem,1fr)_minmax(14rem,1.2fr)_minmax(8rem,0.7fr)_minmax(18rem,1.5fr)] md:items-center md:gap-4">
      <div className="self-center md:flex md:items-center md:justify-start">
        {canToggleActive ? (
          <button
            type="button"
            role="switch"
            aria-checked={user.is_active}
            aria-label={t("roles.labelActive")}
            disabled={actionLoading}
            onClick={() => onToggleActive(user)}
            className={`role-active-switch ${user.is_active ? "" : "role-active-switch-off"} relative inline-flex h-6 w-11 shrink-0 rounded-full border border-transparent p-0.5 transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-neutral-600 disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none dark:border-white ${user.is_active ? "bg-black" : "bg-[var(--color-border)]"}`}
          >
            <span
              className={`role-active-switch-knob inline-block h-5 w-5 rounded-full bg-white shadow-sm ring-0 transform transition-transform duration-200 ease-in-out ${user.is_active ? "translate-x-5" : "translate-x-0"}`}
              aria-hidden
            />
          </button>
        ) : (
          <span aria-hidden />
        )}
      </div>
      <div className="min-w-0">
        <p className={`text-base font-semibold text-[var(--color-foreground)] ${inactiveDarkTextClass}`}>{displayName}</p>
        <span className={`role-status-label mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium ${getStatusClasses(user)}`}>
          {statusLabel}
        </span>
      </div>
      <div className="min-w-0 text-sm">
        <span className={`min-w-0 break-all text-[var(--color-muted)] md:break-words ${inactiveDarkTextClass}`}>{user.email}</span>
      </div>
      <div className={`text-sm text-[var(--color-muted-foreground)] ${inactiveDarkTextClass}`}>{roleLabel}</div>
      <div className="flex flex-col items-end gap-2 sm:col-span-2 md:col-span-1">
        <div className="flex w-full flex-nowrap justify-end gap-2 overflow-x-auto md:overflow-visible">
          {targetEditable && user.id !== currentUser?.id && user.role !== "owner" ? (
            <Button type="button" onClick={() => onDelete(user)} disabled={actionLoading} variant="danger" size="sm" className="!px-3 !py-1.5 text-xs font-semibold">
              {t("common.delete")}
            </Button>
          ) : null}
          {targetEditable && user.role !== "owner" && user.role !== "admin" && user.id !== currentUser?.id ? (
            <Button type="button" onClick={() => onKbPermissions(user)} disabled={actionLoading} variant="secondary" size="sm" className="!px-3 !py-1.5 text-xs font-semibold">
              {t("kb.actionPermissions")}
            </Button>
          ) : null}
          {!targetEditable ? (
            <span className="w-full text-right text-xs text-slate-400" title={t(targetBlockedMessageKey)}>
              {t(targetBlockedMessageKey)}
            </span>
          ) : (
            <Button type="button" onClick={() => onEdit(user)} disabled={actionLoading} variant="secondary" size="sm" className="!px-3 !py-1.5 text-xs font-semibold">
              {t("roles.actionSettings")}
            </Button>
          )}
        </div>
        {user.pending_registration && user.role !== "owner" ? (
          <Button
            type="button"
            onClick={() => onResendInvite(user)}
            disabled={actionLoading}
            variant="secondary"
            size="sm"
            className="self-end !bg-[#efefef] !px-3 !py-1.5 text-xs font-semibold !text-black hover:!bg-[#e5e5e5]"
          >
            {t("roles.resendInvite")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
