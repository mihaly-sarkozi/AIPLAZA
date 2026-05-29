import type { RoleUser } from "./rolesTypes";
import UserRoleCard from "./UserRoleCard";

type UserRoleListProps = {
  users: RoleUser[];
  currentUser: { id?: number; role?: string } | null | undefined;
  actionLoading: boolean;
  loadMoreRef: React.RefObject<HTMLDivElement | null>;
  t: (key: string) => string;
  onDelete: (user: RoleUser) => void;
  onKbPermissions: (user: RoleUser) => void;
  onEdit: (user: RoleUser) => void;
  onResendInvite: (user: RoleUser) => void;
  onToggleActive: (user: RoleUser) => void;
};

export default function UserRoleList({
  users,
  currentUser,
  actionLoading,
  loadMoreRef,
  t,
  onDelete,
  onKbPermissions,
  onEdit,
  onResendInvite,
  onToggleActive,
}: UserRoleListProps) {
  return (
    <section>
      <div className="app-table-wrap">
        <div className="app-table-head hidden grid-cols-[5rem_minmax(12rem,1fr)_minmax(14rem,1.2fr)_minmax(8rem,0.7fr)_minmax(18rem,1.5fr)] gap-4 !bg-[#efefef] px-5 py-3 text-sm font-medium !text-black md:grid">
          <div>{t("roles.labelActive")}</div>
          <div>{t("roles.tableName")}</div>
          <div>{t("roles.tableEmail")}</div>
          <div>{t("roles.tableRole")}</div>
          <div />
        </div>
        <div className="divide-y divide-[var(--color-border)]">
          {users.map((user) => (
            <UserRoleCard
              key={user.id}
              user={user}
              currentUser={currentUser}
              actionLoading={actionLoading}
              t={t}
              onDelete={onDelete}
              onKbPermissions={onKbPermissions}
              onEdit={onEdit}
              onResendInvite={onResendInvite}
              onToggleActive={onToggleActive}
            />
          ))}
        </div>
        <div ref={loadMoreRef} className="h-8" />
      </div>
    </section>
  );
}
