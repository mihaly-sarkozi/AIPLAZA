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
}: UserRoleListProps) {
  return (
    <section>
      <div className="app-table-wrap">
        <div className="app-table-head hidden grid-cols-[1.3fr_0.9fr_1.6fr_1.5fr] gap-4 !bg-[#efefef] px-5 py-3 text-sm font-medium !text-[var(--color-foreground)] md:grid">
          <div>{t("roles.tableName")}</div>
          <div>{t("roles.tableRole")}</div>
          <div>{t("roles.tableEmail")}</div>
          <div>{t("roles.tableActions")}</div>
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
            />
          ))}
        </div>
        <div ref={loadMoreRef} className="h-8" />
      </div>
    </section>
  );
}
