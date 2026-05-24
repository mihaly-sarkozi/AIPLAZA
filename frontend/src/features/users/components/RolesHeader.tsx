import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";

type RolesHeaderProps = {
  t: (key: string) => string;
  actionLoading: boolean;
  onCreate: () => void;
};

export default function RolesHeader({ t, actionLoading, onCreate }: RolesHeaderProps) {
  return (
    <PageHeader
      eyebrow={t("roles.teamLabel")}
      title={t("roles.title")}
      description={t("roles.pageIntro")}
      actions={
        <Button onClick={onCreate} disabled={actionLoading}>
          {t("roles.newUser")}
        </Button>
      }
    />
  );
}
