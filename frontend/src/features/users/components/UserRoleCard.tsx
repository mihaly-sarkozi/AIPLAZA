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
}: UserRoleCardProps) {
  const statusLabel = isDeletedUser(user)
    ? t("roles.statusDeleted")
    : user.is_active
      ? t("roles.statusActive")
      : user.pending_registration
        ? t("roles.statusPending")
        : t("roles.statusInactive");
  const roleLabel = user.role === "owner" ? t("roles.roleOwner") : user.role === "admin" ? t("roles.roleAdmin") : t("roles.roleUser");
  const displayName = user.name || "—";

  return (
    <div className="grid gap-3 px-5 py-4 md:grid-cols-[1.3fr_0.9fr_1.6fr_1.5fr] md:items-center md:gap-4">
      <div>
        <p className="text-sm font-medium text-[var(--color-foreground)]">{displayName}</p>
        <span className={`mt-1 inline-block rounded-lg px-2 py-0.5 text-xs font-medium ${getStatusClasses(user)}`}>
          {statusLabel}
        </span>
      </div>
      <div className="text-sm text-[var(--color-muted-foreground)]">{roleLabel}</div>
      <div className="break-all text-sm text-[var(--color-muted)]">{user.email}</div>
      <div className="grid grid-cols-3 gap-2">
        {user.id !== currentUser?.id && user.role !== "owner" ? (
          <Button type="button" onClick={() => onDelete(user)} disabled={actionLoading} variant="danger" className="w-full">
            {t("common.delete")}
          </Button>
        ) : null}
        {user.role !== "owner" && user.id !== currentUser?.id ? (
          <Button type="button" onClick={() => onKbPermissions(user)} disabled={actionLoading} variant="secondary" className="w-full">
            {t("kb.actionPermissions")}
          </Button>
        ) : null}
        {user.role === "owner" && currentUser?.role !== "owner" ? (
          <span className="col-span-3 text-xs text-slate-400" title={t("roles.ownerOnlyEdit")}>
            {t("roles.ownerOnlyEdit")}
          </span>
        ) : (
          <Button type="button" onClick={() => onEdit(user)} disabled={actionLoading} variant="secondary" className="w-full">
            {t("roles.actionSettings")}
          </Button>
        )}
        {user.pending_registration && user.role !== "owner" ? (
          <Button
            type="button"
            onClick={() => onResendInvite(user)}
            disabled={actionLoading}
            variant="secondary"
            className="col-span-3 w-full !bg-[#efefef] !text-[var(--color-foreground)] hover:!bg-[#e5e5e5]"
          >
            {t("roles.resendInvite")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
